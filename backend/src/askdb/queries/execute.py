import json
import logging
import time

from askdb.databases.query import ReadOnlyQueryPort
from askdb.queries.errors import ApplicationError
from askdb.queries.models import ExecuteSqlRequest, QueryResult
from askdb.queries.pending import PendingSqlRegistry
from askdb.queries.policy import SqlPolicyValidator

logger = logging.getLogger("askdb")


class ExecuteSqlUseCase:
    def __init__(self, pending: PendingSqlRegistry, validator: SqlPolicyValidator, query: ReadOnlyQueryPort):
        self.pending = pending
        self.validator = validator
        self.query = query

    def execute(self, request: ExecuteSqlRequest) -> QueryResult:
        request = ExecuteSqlRequest.model_validate(request)
        started = time.monotonic()
        code = "unexpected_error"
        try:
            proposal = self.pending.get(request.proposal_id, request.connection_id, request.session_id)
            if proposal.validation.status != "approved" or self.validator.validate(proposal.sql).status != "approved":
                self.pending.invalidate_session(request.session_id)
                raise ApplicationError("proposal_not_approved", "A proposta foi bloqueada na revalidação.")
            # O consume é atômico: solicitações concorrentes não podem executar o mesmo ID.
            exact = self.pending.consume(request.proposal_id, request.connection_id, request.session_id)
            result = self.query.execute(exact.connection_id, exact.sql)
            code = "executed"
            return result
        except ApplicationError as error:
            code = error.code
            raise
        finally:
            logger.info(json.dumps({"phase": "execution", "code": code,
                                   "duration_ms": round((time.monotonic() - started) * 1000)}))
