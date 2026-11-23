import os
from collections.abc import Callable, Mapping

from pydantic import SecretStr

from askdb.queries.errors import ApplicationError


def read_api_key(provider: str, *, environ: Mapping[str, str] | None = None,
                 ask_secret: Callable[[str], str] | None = None) -> SecretStr:
    names = {"deepseek": "DEEPSEEK_API_KEY", "openai": "OPENAI_API_KEY"}
    if provider not in names:
        raise ApplicationError("configuration_error", "O perfil não utiliza chave de API remota.")
    source = os.environ if environ is None else environ
    value = source.get(names[provider], "")
    if not value and ask_secret is not None:
        value = ask_secret(f"Chave API {provider} (entrada oculta) > ")
    if (not isinstance(value, str) or not value.strip()
            or any(ord(c) < 33 or ord(c) > 126 for c in value.strip())):
        raise ApplicationError("llm_authentication_failed", "Informe a chave no ambiente do processo ou na entrada oculta.")
    return SecretStr(value.strip())
