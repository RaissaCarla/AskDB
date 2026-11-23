from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class DataModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, hide_input_in_errors=True, revalidate_instances="always")


class SqlGenerationRequest(DataModel):
    question: str = Field(min_length=1, max_length=2000)

    @field_validator("question", mode="before")
    @classmethod
    def normalize(cls, value):
        return value.strip() if isinstance(value, str) else value


class ValidationReason(DataModel):
    code: str
    message: str


class ValidationResult(DataModel):
    status: Literal["approved", "blocked"]
    reasons: list[ValidationReason] = Field(default_factory=list)

    @model_validator(mode="after")
    def consistent(self):
        if (self.status == "blocked") != bool(self.reasons):
            raise ValueError("Decisão e motivos incompatíveis.")
        return self


class SqlProposal(DataModel):
    sql: str
    validation: ValidationResult
    id: str = Field(default_factory=lambda: uuid4().hex)
    connection_id: str = ""
    session_id: str = ""
    question_id: str = ""
    attempt: int = Field(default=1, ge=1, le=3)


class SqlGenerationState(DataModel):
    id: str = Field(default_factory=lambda: uuid4().hex)
    question: str
    attempts: int = Field(default=0, ge=0, le=3)
    terminal: bool = False
    last_sql: str = Field(default="", repr=False)
    feedback_code: str = ""
    history_index: int | None = None


class SessionContext(DataModel):
    id: str = Field(default_factory=lambda: uuid4().hex)
    connection_id: str
    question_sql_pairs: list[tuple[str, str]] = Field(default_factory=list)
    active_question: SqlGenerationState | None = None

    def reset(self, connection_id: str):
        self.connection_id = connection_id
        self.question_sql_pairs.clear()
        self.active_question = None
        self.id = uuid4().hex


class ExecuteSqlRequest(DataModel):
    proposal_id: str
    connection_id: str
    session_id: str
    confirmed: Literal[True]

    @field_validator("confirmed", mode="before")
    @classmethod
    def explicit_confirmation(cls, value):
        if value is not True:
            raise ValueError("A confirmação deve ser explicitamente verdadeira.")
        return value


class QueryResult(DataModel):
    columns: list[str]
    rows: list[tuple[Any, ...]]
    duration_ms: float = Field(ge=0)
    truncated: bool = False
