import json

import httpx
import pytest

from askdb.llm.ollama import OllamaLLMClientAdapter
from askdb.queries.errors import ApplicationError
from askdb.settings import Settings


def adapter(handler):
    return OllamaLLMClientAdapter(Settings(database_url="postgresql://u:secret@localhost/db"),
                                  transport=httpx.MockTransport(handler))


@pytest.mark.parametrize("content,expected", [
    ("SELECT 1", "SELECT 1"), ("```sql\nSELECT 1\n```", "SELECT 1"),
    ("Explicação: SELECT 1", "Explicação: SELECT 1"),
    ("SELECT 1; DELETE FROM produtos", "SELECT 1; DELETE FROM produtos")])
def test_final_content_only(content, expected):
    def handler(request):
        payload = json.loads(request.content)
        assert payload["model"] == "qwen3.5:9b" and payload["stream"] is False
        assert "secret" not in request.content.decode()
        assert payload["messages"][0]["role"] == "system"
        return httpx.Response(200, json={"done": True, "message": {"content": content, "thinking": "DELETE FROM produtos"}})
    assert adapter(handler).generate('{"question":"produtos","schema":[]}') == expected


@pytest.mark.parametrize("result", [{}, {"done": True, "message": {}},
    {"done": False, "message": {"content": "SELECT 1"}},
    {"done": True, "done_reason": "length", "message": {"content": "SELECT 1"}},
    {"done": True, "message": {"thinking": "SELECT 1"}},
    {"done": True, "message": {"content": " "}},
    {"done": True, "message": {"content": "x" * 16001}},
    {"done": True, "message": {"content": "x" * 70000}}, []])
def test_invalid_responses(result):
    with pytest.raises(ApplicationError) as error:
        adapter(lambda r: httpx.Response(200, json=result)).generate("pergunta")
    assert error.value.code == "llm_invalid_response"


@pytest.mark.parametrize("failure,code", [(httpx.ReadTimeout("secret"), "llm_timeout"),
    (httpx.ConnectError("secret"), "llm_unavailable")])
def test_transport_errors(failure, code):
    calls = []
    def handler(request):
        calls.append(request)
        raise failure
    with pytest.raises(ApplicationError) as error:
        adapter(handler).generate("pergunta")
    assert len(calls) == 1 and error.value.code == code and "secret" not in str(error.value)


@pytest.mark.parametrize("response,code", [(httpx.Response(404, text="secret"), "llm_unavailable"),
    (httpx.Response(200, text="invalido"), "llm_invalid_response")])
def test_http_errors(response, code):
    with pytest.raises(ApplicationError) as error:
        adapter(lambda r: response).generate("pergunta")
    assert error.value.code == code
