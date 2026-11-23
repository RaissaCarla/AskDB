import json

import httpx
import pytest
from pydantic import SecretStr

from askdb.llm.credentials import read_api_key
from askdb.llm.deepseek import DeepSeekLLMClientAdapter
from askdb.llm.models import LLMContext, LLMProfile
from askdb.queries.errors import ApplicationError


def profile():
    return LLMProfile(provider="deepseek", endpoint="https://api.deepseek.com", model="deepseek-flash")


def context():
    return LLMContext(messages=[{"role": "system", "content": "Gere SQL."}, {"role": "user", "content": "produtos"}])


def adapter(handler):
    return DeepSeekLLMClientAdapter(profile(), SecretStr("chave-sentinela"), transport=httpx.MockTransport(handler))


def envelope(content="SELECT 1", **extras):
    return {"choices": [{"finish_reason": "stop", "message": {"content": content, **extras}}],
            "usage": {"prompt_tokens": 12, "completion_tokens": 3}}


def test_deepseek_final_response_and_authentication(caplog):
    def handler(request):
        assert str(request.url) == "https://api.deepseek.com/chat/completions"
        assert request.headers["authorization"] == "Bearer chave-sentinela"
        payload = json.loads(request.content)
        assert payload["model"] == "deepseek-flash"
        assert payload["thinking"] == {"type": "disabled"} and not payload["stream"]
        assert "chave-sentinela" not in request.content.decode()
        return httpx.Response(200, json=envelope("```sql\nSELECT 1\n```", reasoning_content="raciocínio-sentinela"))
    result = adapter(handler).generate(context())
    assert result.sql == "SELECT 1" and result.input_tokens == 12
    assert "raciocínio-sentinela" not in repr(result) and "chave-sentinela" not in caplog.text


@pytest.mark.parametrize("result", [{}, {"choices": []}, {"choices": [{"finish_reason": "length", "message": {"content": "SELECT 1"}}]},
    envelope(""), envelope("x" * 16001), envelope("x" * 70000), envelope(None), envelope(tool_calls=[{}]),
    {"choices": [{"finish_reason": "stop", "message": {"reasoning_content": "SELECT 1"}}]}, []])
def test_invalid_remote_responses(result):
    with pytest.raises(ApplicationError) as error:
        adapter(lambda r: httpx.Response(200, json=result)).generate(context())
    assert error.value.code == "llm_invalid_response"


@pytest.mark.parametrize("status,code", [(401,"llm_authentication_failed"), (403,"llm_authentication_failed"),
    (402,"llm_rate_limited"), (429,"llm_rate_limited"), (500,"llm_unavailable"), (404,"llm_unavailable"), (302,"llm_unavailable")])
def test_errors_without_retry_or_redirect(status, code):
    calls = []
    def handler(request):
        calls.append(request)
        return httpx.Response(status, text="chave-sentinela", headers={"Location": "https://evil.invalid"})
    with pytest.raises(ApplicationError) as error:
        adapter(handler).generate(context())
    assert error.value.code == code and len(calls) == 1
    assert "sentinela" not in str(error.value)


@pytest.mark.parametrize("failure,code", [(httpx.ReadTimeout("secret"),"llm_timeout"), (httpx.ConnectError("secret"),"llm_unavailable")])
def test_connection_failure(failure, code):
    calls = []
    def handler(request):
        calls.append(request)
        raise failure
    with pytest.raises(ApplicationError) as error:
        adapter(handler).generate(context())
    assert error.value.code == code and len(calls) == 1 and "secret" not in str(error.value)


def test_full_text_reaches_policy_without_extraction():
    content = "Explicação: SELECT 1; DELETE FROM produtos"
    assert adapter(lambda r: httpx.Response(200, json=envelope(content))).generate(context()).sql == content


def test_runtime_key_hidden_and_never_read_from_dotenv(tmp_path, monkeypatch):
    file = tmp_path / ".env"
    file.write_text("DEEPSEEK_API_KEY=segredo-em-arquivo", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    calls = []
    def ask(prompt):
        calls.append(prompt)
        return "chave-oculta"
    key = read_api_key("deepseek", environ={}, ask_secret=ask)
    assert key.get_secret_value() == "chave-oculta" and len(calls) == 1
    assert "chave-oculta" not in repr(key)
    assert read_api_key("deepseek", environ={"DEEPSEEK_API_KEY": "ambiente"}).get_secret_value() == "ambiente"
    for env in ({}, {"DEEPSEEK_API_KEY": "\r\n"}):
        with pytest.raises(ApplicationError):
            read_api_key("deepseek", environ=env)
