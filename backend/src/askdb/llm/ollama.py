import json
import re
import time

import httpx

from askdb.llm.models import LLMContext, LLMResponse
from askdb.knowledge.context import SYSTEM_PROMPT
from askdb.queries.errors import ApplicationError
from askdb.settings import Settings

class OllamaLLMClientAdapter:
    def __init__(self, settings: Settings, transport=None):
        self.settings = settings
        self.transport = transport

    def generate(self, context: LLMContext) -> LLMResponse:
        def invalid():
            return ApplicationError(
                "llm_invalid_response",
                "O modelo não retornou uma proposta completa utilizável.",
            )

        payload = {
            "model": self.settings.ollama_model,
            "stream": False,
            "think": False,
            "messages": context.messages,
            "options": {"temperature": 0, "num_predict": self.settings.output_reserve,
                        "num_ctx": self.settings.llm_context_window},
        }
        try:
            started = time.monotonic()
            with (
                httpx.Client(
                    timeout=httpx.Timeout(
                        self.settings.llm_timeout, connect=self.settings.connect_timeout
                    ),
                    transport=self.transport,
                    trust_env=False,
                ) as client,
                client.stream(
                    "POST", self.settings.ollama_url + "/api/chat", json=payload
                ) as response,
            ):
                response.raise_for_status()
                body = bytearray()
                for chunk in response.iter_bytes():
                    if time.monotonic() - started > self.settings.llm_timeout:
                        raise httpx.ReadTimeout("Tempo total excedido")
                    if len(body) + len(chunk) > 65536:
                        raise invalid()
                    body.extend(chunk)
            result = json.loads(body)
            if (
                not isinstance(result, dict)
                or result.get("done") is not True
                or result.get("done_reason") == "length"
            ):
                raise invalid()
            message = result.get("message")
            content = message.get("content") if isinstance(message, dict) else None
            if (
                not isinstance(content, str)
                or not content.strip()
                or len(content) > 16000
            ):
                raise invalid()
            content = content.strip()
            block = re.fullmatch(
                r"```(?:sql|postgresql)?\s*\n(.*?)\n```",
                content,
                flags=re.DOTALL | re.IGNORECASE,
            )
            if block:
                content = block.group(1).strip()
            if not content:
                raise invalid()
            return LLMResponse(sql=content, input_tokens=result.get("prompt_eval_count"),
                               output_tokens=result.get("eval_count"))
        except httpx.TimeoutException:
            raise ApplicationError(
                "llm_timeout", "A inferência excedeu o tempo limite configurado."
            ) from None
        except httpx.HTTPError:
            raise ApplicationError(
                "llm_unavailable",
                "Confira o Ollama e a disponibilidade do modelo configurado.",
            ) from None
        except (ValueError, UnicodeError):
            raise invalid() from None
