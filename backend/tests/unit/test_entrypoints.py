from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from askdb.entrypoints.api import create_app
from askdb.entrypoints.cli import run
from askdb.queries.errors import ApplicationError
from askdb.queries.models import SqlProposal
from askdb.queries.policy import SqlPolicyValidator


def proposal(sql):
    return SqlProposal(sql=sql, validation=SqlPolicyValidator().validate(sql))


@pytest.mark.parametrize("sql,status", [("SELECT nome FROM produtos", "approved"), ("DELETE FROM produtos", "blocked")])
def test_api_and_cli_equivalent(sql, status):
    use_case = Mock()
    use_case.execute.return_value = proposal(sql)
    client = TestClient(create_app(use_case))
    response = client.post("/queries/generate", json={"question": "produtos"})
    assert response.status_code == 200
    assert response.json()["validation"]["status"] == status
    entries = iter(["produtos", "sair"])
    output = []
    run(use_case, lambda prompt: next(entries), output.append)
    assert sql in "\n".join(output)
    for reason in response.json()["validation"]["reasons"]:
        assert reason["code"] in "\n".join(output)


@pytest.mark.parametrize("payload", [{}, {"question": " "}, {"question": 1},
    {"question": "x" * 2001}, {"question": "credencial-secreta", "password": "secreta"}])
def test_api_invalid(payload):
    use_case = Mock()
    response = TestClient(create_app(use_case)).post("/queries/generate", json=payload)
    assert response.status_code == 422 and "secreta" not in response.text
    use_case.execute.assert_not_called()


@pytest.mark.parametrize("code,status", [("database_unavailable", 503), ("schema_unavailable", 503),
    ("llm_unavailable", 503), ("llm_timeout", 504), ("llm_invalid_response", 502), ("configuration_error", 503)])
def test_api_errors(code, status):
    use_case = Mock()
    use_case.execute.side_effect = ApplicationError(code, "Mensagem segura.")
    response = TestClient(create_app(use_case)).post("/queries/generate", json={"question": "produtos"})
    assert response.status_code == status and response.json()["error"]["code"] == code


def test_api_unexpected_and_health():
    use_case = Mock()
    use_case.execute.side_effect = RuntimeError("senha-secreta")
    client = TestClient(create_app(use_case), raise_server_exceptions=False)
    response = client.post("/queries/generate", json={"question": "produtos"})
    assert response.status_code == 500 and "secreta" not in response.text
    assert client.get("/health").json() == {"status": "ok"}
    assert client.get("/docs").status_code == 200
    assert "/queries/generate" in client.get("/openapi.json").json()["paths"]
    assert "access-control-allow-origin" not in client.get("/health", headers={"Origin": "http://example.org"}).headers


@pytest.mark.parametrize("ending", [EOFError, KeyboardInterrupt])
def test_cli_end_and_recover(ending):
    values = iter([" ", "produtos", "produtos", ending])
    def read(prompt):
        item = next(values)
        if isinstance(item, type):
            raise item()
        return item
    use_case = Mock()
    use_case.execute.side_effect = [ApplicationError("llm_unavailable", "Confira Ollama."), proposal("SELECT 1")]
    output = []
    run(use_case, read, output.append)
    text = "\n".join(output)
    assert "invalid_input" in text and "llm_unavailable" in text and "SELECT 1" in text
    assert "Sessão encerrada" in text and "Traceback" not in text
