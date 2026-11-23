from typing import Literal

from pydantic import Field, field_validator, model_validator

from askdb.queries.models import DataModel


class LLMProfile(DataModel):
    provider: Literal["ollama", "deepseek", "openai"] = "ollama"
    endpoint: str = "http://127.0.0.1:11434"
    model: str = Field(default="qwen3.5:9b", min_length=1)
    context_window: int = Field(default=16384, gt=2048)
    output_reserve: int = Field(default=2048, gt=0)

    @field_validator("endpoint")
    @classmethod
    def valid_endpoint(cls, value):
        from urllib.parse import urlsplit
        parsed = urlsplit(value)
        if (parsed.scheme not in {"https", "http"} or not parsed.hostname
                or parsed.username or parsed.password or parsed.query or parsed.fragment):
            raise ValueError("Endpoint inválido.")
        return value.rstrip("/")

    @model_validator(mode="after")
    def valid_profile(self):
        endpoints = {"deepseek": "https://api.deepseek.com", "openai": "https://api.openai.com/v1"}
        if self.provider in endpoints and self.endpoint != endpoints[self.provider]:
            raise ValueError("Use o endpoint oficial do provedor remoto.")
        if self.output_reserve >= self.context_window:
            raise ValueError("Reserva de saída incompatível com a janela.")
        return self


class LLMContext(DataModel):
    messages: list[dict[str, str]]
    input_tokens_estimate: int = 0
    memory_tokens_estimate: int = 0
    budget_method: str = "utf8_upper_bound_v1"


class LLMResponse(DataModel):
    sql: str
    input_tokens: int | None = Field(default=None, ge=0)
    output_tokens: int | None = Field(default=None, ge=0)
