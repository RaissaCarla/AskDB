from typing import Protocol


class LLMClientPort(Protocol):
    def generate(self, context: str) -> str: ...
