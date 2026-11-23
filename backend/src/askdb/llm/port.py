from typing import Protocol

from askdb.llm.models import LLMContext, LLMResponse


class LLMClientPort(Protocol):
    def generate(self, context: LLMContext) -> LLMResponse: ...
