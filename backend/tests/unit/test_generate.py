import json
from unittest.mock import Mock

import pytest
from pydantic import ValidationError

from askdb.databases.catalog import Column, SchemaCatalog, Table
from askdb.queries.errors import ApplicationError
from askdb.queries.generate import GenerateSqlUseCase
from askdb.queries.models import SqlGenerationRequest
from askdb.queries.policy import SqlPolicyValidator


def make_use_case(sql="SELECT nome FROM produtos"):
    catalog = Mock()
    catalog.discover.return_value = SchemaCatalog(tables=[Table(schema_name="public", name="produtos",
        columns=[Column(name="nome", data_type="text", nullable=False)])])
    llm = Mock()
    llm.generate.return_value = sql
    return GenerateSqlUseCase(catalog, llm, SqlPolicyValidator())


@pytest.mark.parametrize("sql,status", [("SELECT nome FROM produtos", "approved"), ("DELETE FROM produtos", "blocked")])
def test_generation_and_no_execution(sql, status, caplog):
    use_case = make_use_case(sql)
    with caplog.at_level("INFO", logger="askdb"):
        result = use_case.execute(SqlGenerationRequest(question="pergunta confidencial"))
    assert result.validation.status == status
    use_case.catalog.discover.assert_called_once_with()
    assert len(use_case.catalog.mock_calls) == 1
    use_case.llm.generate.assert_called_once()
    context = json.loads(use_case.llm.generate.call_args.args[0])
    assert context["schema"]["tables"][0]["name"] == "produtos"
    assert "pergunta confidencial" not in caplog.text and sql not in caplog.text


def test_invalid_input_before_dependencies():
    use_case = make_use_case()
    with pytest.raises(ValidationError):
        use_case.execute({"question": " "})
    use_case.catalog.discover.assert_not_called()
    use_case.llm.generate.assert_not_called()


@pytest.mark.parametrize("mode", ["empty", "large", "failure"])
def test_schema_failure_before_llm(mode):
    use_case = make_use_case()
    if mode == "empty":
        use_case.catalog.discover.return_value = SchemaCatalog(tables=[])
    elif mode == "large":
        use_case.catalog.discover.return_value.tables[0].name = "x" * 33000
    else:
        use_case.catalog.discover.side_effect = ApplicationError("database_unavailable", "Banco indisponível.")
    with pytest.raises(ApplicationError):
        use_case.execute(SqlGenerationRequest(question="produtos"))
    use_case.llm.generate.assert_not_called()
