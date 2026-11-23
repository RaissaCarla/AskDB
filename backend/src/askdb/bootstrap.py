from askdb.databases.postgres import PostgresDatabaseAdapter
from askdb.llm.ollama import OllamaLLMClientAdapter
from askdb.llm.credentials import read_api_key
from askdb.llm.deepseek import DeepSeekLLMClientAdapter
from askdb.llm.openai import OpenAILLMClientAdapter
from askdb.llm.models import LLMProfile
from askdb.knowledge.files import MarkdownKnowledgeAdapter
from askdb.knowledge.budget import TokenBudgetPolicy
from askdb.knowledge.context import ContextBuilder
from askdb.queries.generate import GenerateSqlUseCase
from askdb.queries.policy import SqlPolicyValidator
from askdb.settings import Settings
from askdb.queries.errors import ApplicationError
from askdb.queries.execute import ExecuteSqlUseCase
from askdb.queries.models import SessionContext
from askdb.queries.pending import PendingSqlRegistry


def prepare_knowledge(settings: Settings) -> MarkdownKnowledgeAdapter:
    knowledge = MarkdownKnowledgeAdapter(settings.app_data_dir / "connections")
    knowledge.prepare(settings.connection.id)
    return knowledge


def build_llm(settings: Settings, profile: LLMProfile, *, api_key=None, transport=None):
    if profile.provider == "deepseek":
        return DeepSeekLLMClientAdapter(profile, api_key or read_api_key("deepseek"),
                                        timeout=settings.llm_timeout, connect_timeout=settings.connect_timeout,
                                        transport=transport)
    if profile.provider == "ollama":
        local = settings.model_copy(update={"ollama_url": profile.endpoint, "ollama_model": profile.model,
                                           "llm_context_window": profile.context_window, "output_reserve": profile.output_reserve})
        return OllamaLLMClientAdapter(local, transport=transport)
    if profile.provider == "openai":
        return OpenAILLMClientAdapter(profile, api_key or read_api_key("openai"),
                                      timeout=settings.llm_timeout, connect_timeout=settings.connect_timeout,
                                      transport=transport)
    raise ApplicationError("configuration_error", "A integração desse provedor ainda não está disponível.")


def build_use_case(settings: Settings | None = None, *, profile=None, api_key=None, transport=None,
                   session=None, pending=None) -> GenerateSqlUseCase:
    settings = settings or Settings.from_env()
    catalog = PostgresDatabaseAdapter(settings.database_url.get_secret_value(), max_rows=settings.max_rows)
    profile = profile or settings.profile()
    llm = build_llm(settings, profile, api_key=api_key, transport=transport)
    context = ContextBuilder(catalog, prepare_knowledge(settings), TokenBudgetPolicy(profile))
    return GenerateSqlUseCase(catalog, llm, SqlPolicyValidator(),
                              context_builder=context, connection_id=settings.connection.id,
                              session=session, pending=pending)


def build_cli_session(settings: Settings, *, profile=None, api_key=None, transport=None):
    session = SessionContext(connection_id=settings.connection.id)
    pending = PendingSqlRegistry()
    generation = build_use_case(settings, profile=profile, api_key=api_key, transport=transport,
                                 session=session, pending=pending)
    execution = ExecuteSqlUseCase(pending, generation.validator, generation.catalog)
    path = generation.context_builder.knowledge.path(settings.connection.id)
    return generation, execution, path
