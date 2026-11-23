import pytest
from pydantic import ValidationError

from askdb.databases.catalog import Column, SchemaCatalog, Table
from askdb.queries.models import SqlGenerationRequest, SqlProposal, ValidationResult


@pytest.mark.parametrize("question", ["", "  ", 1, None, "x" * 2001])
def test_invalid_question(question):
    with pytest.raises(ValidationError):
        SqlGenerationRequest(question=question)


def test_request_boundaries():
    assert SqlGenerationRequest(question=" a ").question == "a"
    assert len(SqlGenerationRequest(question="x" * 2000).question) == 2000
    for fields in ({}, {"question": "oi", "extra": True}):
        with pytest.raises(ValidationError):
            SqlGenerationRequest(**fields)


def test_catalog_and_proposal():
    catalog = SchemaCatalog(tables=[Table(schema_name="public", name="produtos", columns=[
        Column(name="id", data_type="integer", nullable=False)
    ], primary_key=["id"])])
    assert catalog.tables[0].primary_key == ["id"]
    proposal = SqlProposal(sql="SELECT 1", validation=ValidationResult(status="approved"))
    assert proposal.model_dump()["validation"] == {"status": "approved", "reasons": []}
    with pytest.raises(ValidationError):
        ValidationResult(status="blocked")


def test_v0_confirmation_and_session_do_not_carry_results():
    from askdb.llm.models import LLMContext, LLMResponse
    from askdb.queries.models import ExecuteSqlRequest, QueryResult, SessionContext, SqlGenerationState
    for value in (False, 1, "sim", None):
        with pytest.raises(ValidationError):
            ExecuteSqlRequest(proposal_id="p", connection_id="c", session_id="s", confirmed=value)
    with pytest.raises(ValidationError):
        ExecuteSqlRequest(proposal_id="p", connection_id="c", session_id="s", confirmed=True, sql="SELECT 2")
    session = SessionContext(connection_id="c", question_sql_pairs=[("pergunta", "SELECT 1")])
    session.active_question = SqlGenerationState(question="pergunta", attempts=2)
    with pytest.raises(ValidationError):
        SqlGenerationState(question="pergunta", attempts=4)
    old_id = session.id
    session.reset("other")
    assert session.id != old_id and session.question_sql_pairs == [] and session.active_question is None
    result = QueryResult(columns=["nome", "nome"], rows=[("a", "b")], duration_ms=1.0)
    assert result.rows[0] == ("a", "b")
    assert "rows" not in SessionContext.model_fields and "rows" not in LLMContext.model_fields
    assert LLMResponse(sql="SELECT 1").input_tokens is None
