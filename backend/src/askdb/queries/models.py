from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class DataModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


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
