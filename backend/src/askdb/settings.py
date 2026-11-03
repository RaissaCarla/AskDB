import os
from collections.abc import Mapping
from pathlib import Path
from urllib.parse import urlsplit

from dotenv import dotenv_values
from pydantic import BaseModel, ConfigDict, Field, SecretStr, ValidationError, field_validator

from askdb.queries.errors import ApplicationError

ENV_FILE = Path(__file__).resolve().parents[2] / ".env"

class Settings(BaseModel):
    model_config = ConfigDict(extra="forbid")
    database_url: SecretStr
    ollama_url: str = "http://127.0.0.1:11434"
    ollama_model: str = Field(default="qwen3.5:9b", min_length=1)
    llm_timeout: float = Field(default=120, gt=0, le=600)
    connect_timeout: float = Field(default=5, gt=0, le=60)

    @field_validator("database_url")
    @classmethod
    def validate_database(cls, value):
        parsed = urlsplit(value.get_secret_value())
        if parsed.scheme not in {"postgresql", "postgres"} or not parsed.hostname or not parsed.path.strip("/"):
            raise ValueError("Conexão PostgreSQL inválida.")
        return value

    @field_validator("ollama_url")
    @classmethod
    def validate_endpoint(cls, value):
        parsed = urlsplit(value)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ValueError("Endpoint Ollama inválido.")
        return value.rstrip("/")

    @classmethod
    def from_env(cls, environ: Mapping[str, str] | None = None, *, env_file: Path = ENV_FILE):
        names = {"DATABASE_URL": "database_url", "OLLAMA_URL": "ollama_url",
                 "OLLAMA_MODEL": "ollama_model", "LLM_TIMEOUT": "llm_timeout",
                 "CONNECT_TIMEOUT": "connect_timeout"}
        try:
            # Ambiente explícito isola testes; variáveis do terminal prevalecem sobre o arquivo.
            source = environ if environ is not None else {
                **dotenv_values(env_file, encoding="utf-8-sig", interpolate=False), **os.environ
            }
            return cls(**{field: source[name] for name, field in names.items() if name in source})
        except (ValidationError, ValueError, OSError):
            raise ApplicationError("configuration_error", "Confira as variáveis de configuração do banco e do Ollama.") from None
