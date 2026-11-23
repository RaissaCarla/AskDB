import json
from collections.abc import Callable

from askdb.llm.models import LLMContext, LLMProfile
from askdb.queries.errors import ApplicationError

# Lista deliberadamente fechada: novos modelos exigem validar o método antes do uso.
SUPPORTED_BUDGET_MODELS = {
    ("ollama", "qwen3.5:9b"),
    ("deepseek", "deepseek-flash"),
    ("deepseek", "deepseek-v4-pro"),
    ("openai", "gpt-4.1-mini"),
}


def utf8_upper_bound(text: str) -> int:
    """Limite conservador do texto em tokenizadores BPE de bytes validados; não é contagem exata."""
    return len(text.encode("utf-8"))


class TokenBudgetPolicy:
    def __init__(self, profile: LLMProfile, count: Callable[[str], int] | None = None):
        self.profile = profile
        self.count = count or utf8_upper_bound
        self.compatible = count is not None or (profile.provider, profile.model) in SUPPORTED_BUDGET_MODELS

    def validate(self, memory: str, context: LLMContext) -> LLMContext:
        if not self.compatible:
            raise ApplicationError("context_budget_unavailable", "O modelo não possui método de orçamento validado.")
        try:
            memory_tokens = self.count(memory)
            serialized = json.dumps(context.messages, ensure_ascii=False, separators=(",", ":"))
            # Margem para marcadores especiais, template de chat e cabeçalho de geração.
            input_tokens = self.count(serialized) + 512 + 64 * len(context.messages)
        except (UnicodeError, ValueError):
            raise ApplicationError("context_budget_unavailable", "Não foi possível avaliar o orçamento do contexto.") from None
        available = min(16000, self.profile.context_window - self.profile.output_reserve)
        if memory_tokens > 8000 or input_tokens > available:
            raise ApplicationError("context_limit_exceeded", "O contexto excede o orçamento; reduza o arquivo ou inicie nova sessão.")
        return context.model_copy(update={"memory_tokens_estimate": memory_tokens,
                                          "input_tokens_estimate": input_tokens})
