import json
import logging
import time

from askdb.databases.catalog import SchemaCatalogPort
from askdb.llm.port import LLMClientPort
from askdb.queries.errors import ApplicationError
from askdb.queries.models import SqlGenerationRequest, SqlProposal
from askdb.queries.policy import SqlPolicyValidator

logger = logging.getLogger("askdb")


class GenerateSqlUseCase:
    def __init__(self, catalog: SchemaCatalogPort, llm: LLMClientPort, validator: SqlPolicyValidator):
        self.catalog = catalog
        self.llm = llm
        self.validator = validator

    def execute(self, request: SqlGenerationRequest) -> SqlProposal:
        started = time.monotonic()
        phase = "input"
        code = "unexpected_error"
        try:
            request = SqlGenerationRequest.model_validate(request)
            phase = "schema"
            schema = self.catalog.discover()
            if not schema.tables:
                raise ApplicationError("schema_unavailable", "Nenhuma tabela consultável foi descoberta.")
            context = json.dumps({"schema": schema.model_dump(), "question": request.question}, ensure_ascii=False)
            if len(context) > 32000:
                raise ApplicationError("schema_unavailable", "O esquema excede o limite inicial de contexto.")
            phase = "llm"
            sql = self.llm.generate(context)
            phase = "policy"
            result = self.validator.validate(sql)
            code = result.status
            return SqlProposal(sql=sql, validation=result)
        except ApplicationError as error:
            code = error.code
            raise
        finally:
            logger.info(json.dumps({"phase": phase, "code": code,
                                   "duration_ms": round((time.monotonic()-started)*1000)}))
