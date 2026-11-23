import json
import os
from pathlib import Path

import pytest

from askdb.bootstrap import build_cli_session
from askdb.entrypoints.cli import run
from askdb.llm.credentials import read_api_key
from askdb.settings import Settings

pytestmark = pytest.mark.integration


def test_real_provider_cli_confirmation_and_local_results(tmp_path):
    provider = os.getenv("ASKDB_REAL_LLM_PROVIDER")
    url = os.getenv("ASKDB_TEST_DATABASE_URL")
    if not provider or not url:
        pytest.skip("Prova real opt-in: use verify_v0.py --real-provider com serviço/chave runtime disponíveis.")
    settings = Settings.from_env({"DATABASE_URL": url, "ASKDB_APP_DATA_DIR": str(tmp_path / "app"),
                                  "LLM_PROVIDER": provider, "LLM_TIMEOUT": "180"})
    profile = settings.profile()
    key = read_api_key(provider) if provider != "ollama" else None
    generation, execution, context_path = build_cli_session(settings, profile=profile, api_key=key)
    example = Path(__file__).parents[2] / "examples/context.md"
    context_path.write_bytes(example.read_bytes())
    payloads, usages, results = [], [], []
    original_generate = generation.llm.generate
    original_execute = execution.query.execute

    def generate(context):
        payloads.append(json.dumps(context.messages, ensure_ascii=False))
        response = original_generate(context)
        if response.input_tokens is not None:
            assert response.input_tokens <= context.input_tokens_estimate
        usages.append((context.input_tokens_estimate, response.input_tokens, response.output_tokens))
        return response

    def execute(connection_id, sql):
        result = original_execute(connection_id, sql)
        results.append(result)
        return result

    generation.llm.generate = generate
    execution.query.execute = execute
    entries = iter(["Quais são os cinco produtos mais vendidos por quantidade? Retorne nome e soma da quantidade em ordem decrescente.",
                    "sim", "Liste os nomes dos produtos.", "não", "sair"])
    output = []
    run(generation, read=lambda prompt: next(entries), write=output.append, executor=execution,
        context_path=context_path, destination=settings.connection.label)
    assert len(results) == 1 and results[0].rows == [("Caneta",12),("Caderno",2),("Pasta",1)]
    assert "Execução cancelada" in "\n".join(output)
    assert "Caneta" in "\n".join(output)
    for value in ("Caneta", "Caderno", "Pasta"):
        assert all(value not in payload for payload in payloads)
    assert 2 <= len(payloads) <= 6
    assert generation.session.question_sql_pairs == []
    from fastapi.testclient import TestClient
    from askdb.entrypoints.api import create_app
    api = TestClient(create_app(generation))
    assert api.get("/docs").status_code == 200 and api.get("/health").json() == {"status":"ok"}
    response = api.post("/queries/generate",json={"question":"Liste os nomes dos produtos."})
    assert response.status_code == 200 and response.json()["validation"]["status"] == "approved"
    assert len(results) == 1
    data = json.loads(json.loads(payloads[-1])[1]["content"])
    assert data["session_pairs"] == []
    print(f"Prova real: provedor={provider}, modelo={profile.model}, chamadas={len(payloads)}, execuções=1, cancelamentos=1, API=200")
    print(f"Uso agregado por chamada (estimativa, entrada real, saída): {usages}")
