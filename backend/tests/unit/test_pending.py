from concurrent.futures import ThreadPoolExecutor

import pytest

from askdb.queries.errors import ApplicationError
from askdb.queries.models import SqlProposal, ValidationResult
from askdb.queries.pending import PendingSqlRegistry
from askdb.queries.policy import SqlPolicyValidator


def proposal():
    return SqlProposal(sql="SELECT 1", validation=ValidationResult(status="approved"), connection_id="c", session_id="s")


def test_snapshot_expiry_session_and_cancellation():
    now = [0.0]
    registry = PendingSqlRegistry(clock=lambda: now[0])
    item = proposal()
    registry.register(item)
    item.sql = "DELETE FROM produtos"
    snapshot = registry.get(item.id, "c", "s")
    snapshot.validation.status = "blocked"
    assert registry.get(item.id, "c", "s").sql == "SELECT 1"
    assert registry.get(item.id, "c", "s").validation.status == "approved"
    for connection, session in (("other", "s"), ("c", "other")):
        with pytest.raises(ApplicationError):
            registry.get(item.id, connection, session)
    now[0] = 600.0
    with pytest.raises(ApplicationError):
        registry.get(item.id, "c", "s")
    first, second = proposal(), proposal()
    registry.register(first)
    registry.register(second)
    with pytest.raises(ApplicationError):
        registry.get(first.id, "c", "s")
    registry.invalidate_session("s")
    with pytest.raises(ApplicationError):
        registry.get(second.id, "c", "s")


def test_blocked_proposal_cannot_register():
    item = proposal()
    item.validation = SqlPolicyValidator().validate("DELETE FROM produtos")
    with pytest.raises(ApplicationError):
        PendingSqlRegistry().register(item)


def test_consume_is_atomic():
    registry = PendingSqlRegistry()
    item = proposal()
    registry.register(item)
    def consume(_):
        try:
            return registry.consume(item.id, "c", "s").sql
        except ApplicationError:
            return None
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(consume, range(16)))
    assert results.count("SELECT 1") == 1
