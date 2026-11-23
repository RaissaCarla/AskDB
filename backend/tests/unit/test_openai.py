import json

import httpx
import pytest
from pydantic import SecretStr

from askdb.llm.openai import OpenAILLMClientAdapter
from askdb.llm.models import LLMProfile
from askdb.queries.errors import ApplicationError
from test_deepseek import context, envelope


def adapter(handler):
    profile = LLMProfile(provider="openai", endpoint="https://api.openai.com/v1", model="gpt-4.1-mini")
    return OpenAILLMClientAdapter(profile, SecretStr("chave-openai-sentinela"), transport=httpx.MockTransport(handler))


def test_openai_own_profile_key_and_parameters():
    def handler(request):
        payload = json.loads(request.content)
        assert str(request.url) == "https://api.openai.com/v1/chat/completions"
        assert request.headers["authorization"] == "Bearer chave-openai-sentinela"
        assert payload["model"] == "gpt-4.1-mini" and payload["max_completion_tokens"] == 2048
        assert payload["store"] is False and "thinking" not in payload and "max_tokens" not in payload
        assert "chave-openai-sentinela" not in request.content.decode()
        return httpx.Response(200, json=envelope("SELECT 1", reasoning_content="não usar"))
    assert adapter(handler).generate(context()).sql == "SELECT 1"


@pytest.mark.parametrize("status,code", [(401,"llm_authentication_failed"),(402,"llm_rate_limited"),
    (429,"llm_rate_limited"),(500,"llm_unavailable"),(307,"llm_unavailable")])
def test_openai_no_retry_or_redirect(status, code):
    calls = []
    def handler(request):
        calls.append(request)
        return httpx.Response(status,text="chave-openai-sentinela",headers={"Location":"https://evil.invalid"})
    with pytest.raises(ApplicationError) as error:
        adapter(handler).generate(context())
    assert error.value.code == code and len(calls) == 1 and "sentinela" not in str(error.value)


@pytest.mark.parametrize("response", [httpx.Response(200,text="inválido"), httpx.Response(200,json={}),
    httpx.Response(200,json=envelope("x"*70000)), httpx.Response(200,json=envelope(tool_calls=[{}])),
    httpx.Response(200,json={"choices":[{"finish_reason":"length","message":{"content":"SELECT 1"}}]})])
def test_openai_invalid_outputs(response):
    with pytest.raises(ApplicationError) as error:
        adapter(lambda r: response).generate(context())
    assert error.value.code == "llm_invalid_response"


@pytest.mark.parametrize("failure,code", [(httpx.ReadTimeout("secret"),"llm_timeout"),(httpx.ConnectError("secret"),"llm_unavailable")])
def test_openai_transport_errors(failure, code):
    def handler(request):
        raise failure
    with pytest.raises(ApplicationError) as error:
        adapter(handler).generate(context())
    assert error.value.code == code and "secret" not in str(error.value)
