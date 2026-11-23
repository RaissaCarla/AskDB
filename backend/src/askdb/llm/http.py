import json
import re
import time

import httpx

from askdb.queries.errors import ApplicationError


def invalid_response() -> ApplicationError:
    return ApplicationError("llm_invalid_response", "O modelo não retornou uma proposta final completa utilizável.")


def normalize_sql(content) -> str:
    if not isinstance(content, str) or not content.strip() or len(content) > 16000:
        raise invalid_response()
    content = content.strip()
    block = re.fullmatch(r"```(?:sql|postgresql)?\s*\n(.*?)\n```", content, flags=re.DOTALL | re.IGNORECASE)
    if block:
        content = block.group(1).strip()
    if not content:
        raise invalid_response()
    return content


def request_json(url: str, payload: dict, *, headers=None, timeout=120.0,
                 connect_timeout=5.0, transport=None) -> dict:
    try:
        started = time.monotonic()
        with (httpx.Client(timeout=httpx.Timeout(timeout, connect=connect_timeout), transport=transport,
                           trust_env=False, follow_redirects=False) as client,
              client.stream("POST", url, json=payload, headers=headers) as response):
            if response.status_code in {401, 403}:
                raise ApplicationError("llm_authentication_failed", "O provedor rejeitou a chave; confira a credencial em execução.")
            if response.status_code in {402, 429}:
                raise ApplicationError("llm_rate_limited", "Confira a cota e o limite de requisições do provedor.")
            if response.status_code != 200:
                raise ApplicationError("llm_unavailable", "O provedor ou modelo configurado não está disponível.")
            body = bytearray()
            for chunk in response.iter_bytes():
                if time.monotonic() - started > timeout:
                    raise httpx.ReadTimeout("Tempo total excedido")
                if len(body) + len(chunk) > 65536:
                    raise invalid_response()
                body.extend(chunk)
        result = json.loads(body)
        if not isinstance(result, dict):
            raise invalid_response()
        return result
    except httpx.TimeoutException:
        raise ApplicationError("llm_timeout", "A inferência excedeu o tempo limite configurado.") from None
    except httpx.HTTPError:
        raise ApplicationError("llm_unavailable", "Não foi possível acessar o provedor de IA configurado.") from None
    except (ValueError, UnicodeError):
        raise invalid_response() from None


def completion_content(result: dict):
    choices = result.get("choices")
    if not isinstance(choices, list) or len(choices) != 1 or not isinstance(choices[0], dict):
        raise invalid_response()
    choice = choices[0]
    message = choice.get("message")
    if (choice.get("finish_reason") != "stop" or not isinstance(message, dict)
            or message.get("tool_calls") or message.get("refusal")):
        raise invalid_response()
    return normalize_sql(message.get("content"))


def usage_counts(result: dict):
    usage = result.get("usage", {})
    if not isinstance(usage, dict):
        raise invalid_response()
    counts = (usage.get("prompt_tokens"), usage.get("completion_tokens"))
    if any(v is not None and (type(v) is not int or v < 0) for v in counts):
        raise invalid_response()
    return counts
