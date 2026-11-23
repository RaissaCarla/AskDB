import json

from fastapi.testclient import TestClient
import pytest

from askdb.entrypoints.api import create_app
from askdb.llm.models import LLMResponse
from askdb.queries.models import SqlGenerationRequest
from test_cli_v0 import runtime


def test_api_does_not_inherit_injected_cli_session(tmp_path, monkeypatch):
    settings, generation, execution, path, calls = runtime(tmp_path, monkeypatch)
    generation.execute(SqlGenerationRequest(question="pergunta privada da CLI"))
    client = TestClient(create_app(generation))
    for question in ("pergunta http A", "pergunta http B"):
        response = client.post("/queries/generate",json={"question":question})
        assert response.status_code == 200 and response.json()["validation"]["status"] == "approved"
        data = json.loads(calls[-1]["messages"][1]["content"])
        assert data["session_pairs"] == [] and "pergunta privada da CLI" not in json.dumps(data)
    assert len(generation.session.question_sql_pairs) == 1
    execution.query.execute.assert_not_called()
    assert client.post("/queries/execute",json={}).status_code == 404
    assert client.get("/health").json() == {"status":"ok"}
    assert client.get("/docs").status_code == 200
    assert "access-control-allow-origin" not in client.get("/health",headers={"Origin":"https://example.org"}).headers


@pytest.mark.parametrize("code,status", [("llm_authentication_failed",503),("llm_rate_limited",503),
    ("knowledge_unavailable",503),("context_budget_unavailable",503),("context_limit_exceeded",422),
    ("generation_attempts_exhausted",502)])
def test_new_safe_http_errors(code, status):
    from unittest.mock import Mock
    from askdb.queries.errors import ApplicationError
    use_case = Mock()
    use_case.execute.side_effect = ApplicationError(code,"Mensagem pública fixa.")
    response = TestClient(create_app(use_case)).post("/queries/generate",json={"question":"produtos"})
    assert response.status_code == status and response.json() == {"error":{"code":code,"message":"Mensagem pública fixa."}}
