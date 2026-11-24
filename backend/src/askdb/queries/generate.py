import json
import logging
import time

from askdb.databases.catalog import SchemaCatalogPort
from askdb.llm.port import LLMClientPort
from askdb.llm.models import LLMProfile
from askdb.knowledge.budget import TokenBudgetPolicy
from askdb.knowledge.context import ContextBuilder
from askdb.queries.errors import ApplicationError
from askdb.queries.models import SessionContext, SqlGenerationRequest, SqlGenerationState, SqlProposal
from askdb.queries.policy import RETRYABLE_PROPOSAL_CODES, SqlPolicyValidator
from askdb.queries.pending import PendingSqlRegistry

logger = logging.getLogger("askdb")


class GenerateSqlUseCase:
    def __init__(self, catalog: SchemaCatalogPort, llm: LLMClientPort, validator: SqlPolicyValidator,
                 *, context_builder: ContextBuilder | None = None, connection_id: str = "",
                 session: SessionContext | None = None, pending: PendingSqlRegistry | None = None):
        self.catalog = catalog
        self.llm = llm
        self.validator = validator
        self.context_builder = context_builder or ContextBuilder(catalog, None, TokenBudgetPolicy(LLMProfile()))
        self.connection_id = connection_id
        self.session = session
        self.pending = pending if pending is not None else PendingSqlRegistry()
        self.last_usage: dict = {}

    def execute(self, request: SqlGenerationRequest) -> SqlProposal:
        request = SqlGenerationRequest.model_validate(request)
        session = self.session if self.session is not None else SessionContext(connection_id=self.connection_id)
        self.pending.invalidate_session(session.id)
        if session.connection_id != self.connection_id:
            session.reset(self.connection_id)
        state = SqlGenerationState(question=request.question)
        session.active_question = state
        return self._generate(session, state)

    def correct(self, proposal: SqlProposal, error: ApplicationError) -> SqlProposal:
        session = self.session
        state = session.active_question if session is not None else None
        if (session is None or state is None or state.terminal or state.id != proposal.question_id
                or session.id != proposal.session_id or session.connection_id != proposal.connection_id
                or state.last_sql != proposal.sql or state.attempts != proposal.attempt
                or error.code not in {"query_syntax_error", "query_resolution_error"}):
            raise ApplicationError("correction_not_allowed", "Essa proposta ou falha não permite correção automática.")
        self.pending.invalidate_session(session.id)
        if state.history_index is not None:
            session.question_sql_pairs.pop(state.history_index)
            state.history_index = None
        state.feedback_code = error.code
        return self._generate(session, state)

    def _generate(self, session: SessionContext, state: SqlGenerationState) -> SqlProposal:
        started = time.monotonic()
        phase = "input"
        code = "unexpected_error"
        try:
            while state.attempts < 3:
                phase = "context"
                context = self.context_builder.build(self.connection_id, state.question, session,
                    feedback_code=state.feedback_code, failed_sql=state.last_sql)
                phase = "llm"
                state.attempts += 1
                try:
                    response = self.llm.generate(context)
                except ApplicationError as error:
                    if error.code == "llm_invalid_response":
                        state.feedback_code = error.code
                        state.last_sql = ""
                        continue
                    raise
                self.last_usage = {"input_tokens": response.input_tokens, "output_tokens": response.output_tokens,
                                   "input_tokens_estimate": context.input_tokens_estimate,
                                   "budget_method": context.budget_method}
                state.last_sql = response.sql
                phase = "policy"
                result = self.validator.validate(response.sql)
                code = result.status
                reasons = {reason.code for reason in result.reasons}
                if (result.status == "blocked" and len(reasons) == 1
                        and reasons <= RETRYABLE_PROPOSAL_CODES and state.attempts < 3):
                    state.feedback_code = reasons.pop()
                    continue
                proposal = SqlProposal(sql=response.sql, validation=result, connection_id=self.connection_id,
                    session_id=session.id, question_id=state.id, attempt=state.attempts)
                if result.status == "approved":
                    self.pending.register(proposal)
                    state.history_index = len(session.question_sql_pairs)
                    session.question_sql_pairs.append((state.question, response.sql))
                else:
                    state.terminal = True
                return proposal
            state.terminal = True
            raise ApplicationError("generation_attempts_exhausted", "O limite de três tentativas para esta pergunta foi atingido.")
        except ApplicationError as error:
            state.terminal = True
            code = error.code
            raise
        finally:
            logger.info(json.dumps({"phase": phase, "code": code,
                                   "attempts": state.attempts,
                                   "duration_ms": round((time.monotonic()-started)*1000)}))
