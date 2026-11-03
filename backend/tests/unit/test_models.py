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
