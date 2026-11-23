from datetime import date
from decimal import Decimal
import os

import pytest

from askdb.databases.postgres import PostgresDatabaseAdapter
from askdb.queries.errors import ApplicationError
from askdb.queries.execute import ExecuteSqlUseCase
from askdb.queries.models import ExecuteSqlRequest, SqlProposal
from askdb.queries.pending import PendingSqlRegistry
from askdb.queries.policy import SqlPolicyValidator

pytestmark = pytest.mark.integration


@pytest.fixture
def adapter():
    url = os.getenv("ASKDB_TEST_DATABASE_URL")
    if not url:
        pytest.skip("Defina ASKDB_TEST_DATABASE_URL para o banco sintético isolado.")
    return PostgresDatabaseAdapter(url)


def execute(adapter, sql):
    policy = SqlPolicyValidator()
    pending = PendingSqlRegistry()
    proposal = SqlProposal(sql=sql, validation=policy.validate(sql), connection_id=adapter.identity.id, session_id="test")
    pending.register(proposal)
    request = ExecuteSqlRequest(proposal_id=proposal.id, connection_id=adapter.identity.id, session_id="test", confirmed=True)
    return ExecuteSqlUseCase(pending, policy, adapter).execute(request)


def test_real_execution_limit_empty_and_duplicate_columns(adapter):
    result = execute(adapter, "SELECT id, rotulo FROM public.serie_teste ORDER BY id")
    assert len(result.rows) == 100 and result.truncated and result.rows[-1][0] == 100
    empty = execute(adapter, "SELECT nome FROM produtos WHERE id = -1")
    assert empty.columns == ["nome"] and not empty.rows and not empty.truncated
    duplicate = execute(adapter, "SELECT 1 AS nome, 2 AS nome, NULL AS vazio")
    assert duplicate.columns == ["nome","nome","vazio"] and duplicate.rows == [(1,2,None)]
    typed = execute(adapter, "SELECT data, valor, nota FROM tipos_teste")
    assert typed.rows == [(date(2026,11,17), Decimal("12.50"), None)]


def test_rls_column_privileges_and_no_write(adapter):
    assert execute(adapter, "SELECT id, valor FROM movimentos_rls").rows == [(1,Decimal("10.00"))]
    for sql in ("SELECT privado FROM parcial", "SELECT * FROM restrita"):
        with pytest.raises(ApplicationError) as error:
            execute(adapter, sql)
        assert error.value.code == "query_permission_denied"
    # Exercita também a barreira do PostgreSQL diretamente, fora do caso de uso.
    with pytest.raises(ApplicationError):
        adapter.execute(adapter.identity.id, "UPDATE produtos SET nome = 'não autorizado'")
    assert execute(adapter, "SELECT nome FROM produtos WHERE id = 1").rows == [("Caderno",)]


@pytest.mark.parametrize("sql,code", [("SELECT missing FROM produtos","query_resolution_error"),
    ("SELECT nome FROM tabela_inexistente","query_resolution_error")])
def test_real_resolution_errors_are_sanitized(adapter, sql, code):
    with pytest.raises(ApplicationError) as error:
        execute(adapter, sql)
    assert error.value.code == code
    assert "missing" not in str(error.value) and "tabela_inexistente" not in str(error.value)


def test_read_only_settings_and_server_timeout(adapter):
    # SQL técnica de fixture: não é uma proposta aceita pelo validador da aplicação.
    result = adapter.execute(adapter.identity.id,
        "SELECT current_setting('transaction_read_only'), current_setting('statement_timeout'), current_setting('search_path')")
    assert result.rows == [("on", "30s", "pg_catalog,public")]
    fast = PostgresDatabaseAdapter(os.environ["ASKDB_TEST_DATABASE_URL"], statement_timeout_ms=30)
    with pytest.raises(ApplicationError) as error:
        fast.execute(fast.identity.id, "SELECT pg_sleep(0.2)")
    assert error.value.code == "query_timeout"
    assert execute(adapter, "SELECT 1").rows == [(1,)]


def test_real_server_error_does_not_leak_values(adapter, caplog):
    with pytest.raises(ApplicationError) as error:
        adapter.execute(adapter.identity.id, "SELECT CAST('valor_sentinela_privado' AS integer)")
    assert error.value.code == "query_failed"
    assert "sentinela" not in str(error.value) and "sentinela" not in caplog.text


def test_executor_rejects_admin_and_changed_effective_identity(adapter):
    from askdb.connections.models import DBConnection
    admin_url = os.getenv("ASKDB_TEST_ADMIN_URL")
    if not admin_url:
        pytest.skip("Defina ASKDB_TEST_ADMIN_URL para a fixture privilegiada.")
    admin = PostgresDatabaseAdapter(admin_url)
    with pytest.raises(ApplicationError) as error:
        admin.execute(admin.identity.id, "SELECT 1")
    assert error.value.code == "configuration_error"
    original = adapter.identity
    adapter.identity = DBConnection(host=original.host, port=original.port, database=original.database, role="outra_role")
    with pytest.raises(ApplicationError) as error:
        adapter.execute(adapter.identity.id, "SELECT 1")
    assert error.value.code == "connection_mismatch"
