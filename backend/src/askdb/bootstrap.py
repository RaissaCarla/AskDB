from askdb.databases.postgres import PostgresDatabaseAdapter
from askdb.llm.ollama import OllamaLLMClientAdapter
from askdb.queries.generate import GenerateSqlUseCase
from askdb.queries.policy import SqlPolicyValidator
from askdb.settings import Settings


def build_use_case(settings: Settings | None = None) -> GenerateSqlUseCase:
    settings = settings or Settings.from_env()
    return GenerateSqlUseCase(PostgresDatabaseAdapter(settings.database_url.get_secret_value()),
                              OllamaLLMClientAdapter(settings), SqlPolicyValidator())
