import os
from collections.abc import Mapping
from pathlib import Path

from dotenv import dotenv_values
from pydantic import BaseModel, ConfigDict, Field, SecretStr, ValidationError, field_validator

from askdb.connections.models import DBConnection
from askdb.llm.models import LLMProfile
from askdb.queries.errors import ApplicationError

ENV_FILE = Path(__file__).resolve().parents[2] / ".env"


def read_environment(env_file: Path = ENV_FILE) -> dict[str, str | None]:
    return {**dotenv_values(env_file, encoding="utf-8-sig", interpolate=False), **os.environ}


def default_app_data_dir() -> Path:
    override = os.getenv("ASKDB_APP_DATA_DIR")
    base = os.getenv("LOCALAPPDATA")
    if override:
        path = Path(override)
    elif base:
        path = Path(base) / "AskDB"
    else:
        raise ApplicationError("configuration_error", "Defina ASKDB_APP_DATA_DIR absoluto para os arquivos do aplicativo.")
    if not path.is_absolute():
        raise ApplicationError("configuration_error", "A pasta de dados do aplicativo deve ser absoluta.")
    return path


class Settings(BaseModel):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)
    database_url: SecretStr
    ollama_url: str = "http://127.0.0.1:11434"
    ollama_model: str = Field(default="qwen3.5:9b", min_length=1)
    llm_provider: str = "ollama"
    llm_model: str | None = None
    llm_context_window: int = Field(default=16384, gt=2048)
    output_reserve: int = Field(default=2048, gt=0)
    llm_timeout: float = Field(default=120, gt=0, le=600)
    connect_timeout: float = Field(default=5, gt=0, le=60)
    max_rows: int = Field(default=100, ge=1, le=1000)
    app_data_dir: Path = Field(default_factory=default_app_data_dir)

    @field_validator("database_url")
    @classmethod
    def validate_database(cls, value):
        DBConnection.from_url(value.get_secret_value())
        return value

    @field_validator("ollama_url")
    @classmethod
    def validate_endpoint(cls, value):
        return LLMProfile(endpoint=value).endpoint

    @field_validator("app_data_dir")
    @classmethod
    def validate_app_data_dir(cls, value):
        if not value.is_absolute():
            raise ValueError("A pasta de dados deve ser absoluta.")
        return value

    @field_validator("llm_provider")
    @classmethod
    def validate_provider(cls, value):
        if value not in {"ollama", "deepseek", "openai"}:
            raise ValueError("Provedor não suportado.")
        return value

    @property
    def connection(self) -> DBConnection:
        return DBConnection.from_url(self.database_url.get_secret_value())

    def profile(self, provider: str | None = None) -> LLMProfile:
        provider = provider or self.llm_provider
        defaults = {
            "ollama": (self.ollama_url, self.ollama_model),
            "deepseek": ("https://api.deepseek.com", "deepseek-flash"),
            "openai": ("https://api.openai.com/v1", "gpt-4.1-mini"),
        }
        try:
            endpoint, model = defaults[provider]
            return LLMProfile(provider=provider, endpoint=endpoint,
                              model=(self.llm_model if provider == self.llm_provider else None) or model,
                              context_window=self.llm_context_window,
                              output_reserve=self.output_reserve)
        except (KeyError, ValidationError):
            raise ApplicationError("configuration_error", "Confira o perfil de IA e os limites de contexto.") from None

    @classmethod
    def from_env(cls, environ: Mapping[str, str] | None = None, *, env_file: Path = ENV_FILE):
        names = {"DATABASE_URL": "database_url", "OLLAMA_URL": "ollama_url",
                 "OLLAMA_MODEL": "ollama_model", "LLM_TIMEOUT": "llm_timeout",
                 "CONNECT_TIMEOUT": "connect_timeout", "LLM_PROVIDER": "llm_provider",
                 "LLM_MODEL": "llm_model", "LLM_CONTEXT_WINDOW": "llm_context_window",
                 "LLM_OUTPUT_RESERVE": "output_reserve", "ASKDB_MAX_ROWS": "max_rows",
                 "ASKDB_APP_DATA_DIR": "app_data_dir"}
        try:
            # O .env legado continua válido; chaves remotas não são lidas dele.
            source = environ if environ is not None else read_environment(env_file)
            fields = {field: source[name] for name, field in names.items() if name in source}
            if "app_data_dir" not in fields and source.get("LOCALAPPDATA"):
                fields["app_data_dir"] = Path(source["LOCALAPPDATA"]) / "AskDB"
            settings = cls(**fields)
            settings.profile()
            return settings
        except (ValidationError, ValueError, OSError):
            raise ApplicationError("configuration_error", "Confira banco, perfil de IA e pasta de dados do aplicativo.") from None
