import os
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from askdb.databases.postgres import PostgresDatabaseAdapter
from askdb.entrypoints.api import create_app
from askdb.entrypoints.cli import run
from askdb.queries.generate import GenerateSqlUseCase
from askdb.queries.policy import SqlPolicyValidator

pytestmark = pytest.mark.integration


def test_real_catalog_with_simulated_llm():
    url = os.getenv("ASKDB_TEST_DATABASE_URL")
    if not url:
        pytest.skip("Defina ASKDB_TEST_DATABASE_URL para o banco de teste.")
    catalog = Mock(wraps=PostgresDatabaseAdapter(url))
    llm = Mock()
    llm.generate.return_value = "SELECT nome FROM public.produtos LIMIT 5"
    use_case = GenerateSqlUseCase(catalog, llm, SqlPolicyValidator())
    response = TestClient(create_app(use_case)).post("/queries/generate", json={"question": "produtos"})
    assert response.status_code == 200 and response.json()["validation"]["status"] == "approved"
    output = []
    entries = iter(["produtos", "sair"])
    run(use_case, lambda p: next(entries), output.append)
    assert response.json()["sql"] in "\n".join(output)
    assert "aprovada" in "\n".join(output)
    assert len(catalog.mock_calls) == 2
    assert all(call[0] == "discover" for call in catalog.mock_calls)
    for call in llm.generate.call_args_list:
        context = call.args[0]
        assert '"name": "restrita"' not in context and '"name": "privado"' not in context
