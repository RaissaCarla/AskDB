from concurrent.futures import ThreadPoolExecutor
from unittest.mock import Mock

import pytest
from pydantic import ValidationError

from askdb.queries.errors import ApplicationError
from askdb.queries.execute import ExecuteSqlUseCase
from askdb.queries.models import ExecuteSqlRequest, QueryResult, SqlProposal, ValidationResult
from askdb.queries.pending import PendingSqlRegistry
from askdb.queries.policy import SqlPolicyValidator


def setup():
    pending = PendingSqlRegistry()
    proposal = SqlProposal(sql="SELECT 1", validation=ValidationResult(status="approved"), connection_id="c", session_id="s")
    pending.register(proposal)
    query = Mock()
    query.execute.return_value = QueryResult(columns=["x"], rows=[(1,)], duration_ms=1.0)
    request = ExecuteSqlRequest(proposal_id=proposal.id, connection_id="c", session_id="s", confirmed=True)
    return ExecuteSqlUseCase(pending, SqlPolicyValidator(), query), proposal, request


def test_exact_sql_revalidation_and_failure_consumes(caplog):
    use_case, proposal, request = setup()
    use_case.query.execute.side_effect = ApplicationError("query_resolution_error", "Mensagem fixa.")
    with pytest.raises(ApplicationError):
        use_case.execute(request)
    use_case.query.execute.assert_called_once_with("c", "SELECT 1")
    with pytest.raises(ApplicationError):
        use_case.execute(request)
    assert use_case.query.execute.call_count == 1 and "SELECT 1" not in caplog.text


def test_invalid_confirmation_connection_and_policy():
    use_case, proposal, request = setup()
    data = request.model_dump()
    for fields in ({**data, "confirmed": False}, {k:v for k,v in data.items() if k != "confirmed"}, {**data,"sql":"SELECT 2"}):
        with pytest.raises(ValidationError):
            use_case.execute(fields)
    with pytest.raises(ValidationError):
        use_case.execute(request.model_copy(update={"confirmed": False}))
    with pytest.raises(ApplicationError):
        use_case.execute(request.model_copy(update={"connection_id": "other"}))
    use_case.query.execute.assert_not_called()
    use_case.validator = Mock()
    use_case.validator.validate.return_value = SqlPolicyValidator().validate("DELETE FROM produtos")
    with pytest.raises(ApplicationError):
        use_case.execute(request)
    use_case.query.execute.assert_not_called()


def test_expired_and_cancelled_proposal():
    use_case, proposal, request = setup()
    use_case.pending.invalidate_session("s")
    with pytest.raises(ApplicationError):
        use_case.execute(request)
    use_case.query.execute.assert_not_called()


def test_concurrent_execution_only_once():
    use_case, proposal, request = setup()
    def attempt(_):
        try:
            return use_case.execute(request)
        except ApplicationError:
            return None
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(attempt, range(16)))
    assert sum(r is not None for r in results) == 1
    use_case.query.execute.assert_called_once_with("c", "SELECT 1")
