from types import SimpleNamespace
from unittest.mock import MagicMock

import psycopg
import pytest

from askdb.databases.postgres import PostgresDatabaseAdapter
from askdb.queries.errors import ApplicationError


def setup(monkeypatch):
    adapter = PostgresDatabaseAdapter("postgresql://reader:secret@localhost/demo", max_rows=2)
    connection = MagicMock()
    connection.execute.return_value.fetchone.return_value = {"rolsuper": False, "rolbypassrls": False,
        "effective_role": "reader", "effective_database": "demo"}
    cursor = connection.cursor.return_value.__enter__.return_value
    cursor.description = [SimpleNamespace(name="nome"), SimpleNamespace(name="nome")]
    cursor.fetchmany.return_value = [("a","b"), ("c",None), ("truncar","linha")]
    def connect(url, **options):
        assert "statement_timeout=30000" in options["options"] and "read_only=on" in options["options"]
        assert "search_path=pg_catalog,public" in options["options"]
        return connection
    monkeypatch.setattr(psycopg, "connect", connect)
    return adapter, connection, cursor


def test_server_cursor_bound_and_exact_sql(monkeypatch):
    adapter, connection, cursor = setup(monkeypatch)
    result = adapter.execute(adapter.identity.id, "SELECT nome, nome FROM produtos")
    cursor.execute.assert_called_once_with("SELECT nome, nome FROM produtos")
    cursor.fetchmany.assert_called_once_with(3)
    assert result.columns == ["nome","nome"] and len(result.rows) == 2 and result.truncated
    assert connection.cursor.call_args.kwargs["name"].startswith("askdb_")
    connection.rollback.assert_called_once()
    connection.close.assert_called_once()


@pytest.mark.parametrize("failure,code", [(psycopg.errors.UndefinedColumn,"query_resolution_error"),
    (psycopg.errors.UndefinedTable,"query_resolution_error"), (psycopg.errors.SyntaxError,"query_syntax_error"),
    (psycopg.errors.InsufficientPrivilege,"query_permission_denied"), (psycopg.errors.QueryCanceled,"query_timeout"),
    (psycopg.OperationalError,"database_unavailable"), (psycopg.DataError,"query_failed")])
def test_error_categories_without_raw_values(monkeypatch, failure, code):
    adapter, connection, cursor = setup(monkeypatch)
    cursor.execute.side_effect = failure("valor-secreto-sentinela")
    with pytest.raises(ApplicationError) as error:
        adapter.execute(adapter.identity.id, "SELECT nome FROM produtos")
    assert error.value.code == code and "sentinela" not in str(error.value)
    connection.rollback.assert_called_once()
    connection.close.assert_called_once()


def test_identity_privilege_and_interruption(monkeypatch):
    adapter, connection, cursor = setup(monkeypatch)
    with pytest.raises(ApplicationError):
        adapter.execute("other", "SELECT 1")
    connection.cursor.assert_not_called()
    connection.execute.return_value.fetchone.return_value["effective_role"] = "other"
    with pytest.raises(ApplicationError):
        adapter.execute(adapter.identity.id, "SELECT 1")
    connection.close.assert_called_once()
    adapter, connection, cursor = setup(monkeypatch)
    cursor.fetchmany.side_effect = KeyboardInterrupt()
    with pytest.raises(KeyboardInterrupt):
        adapter.execute(adapter.identity.id, "SELECT 1")
    connection.rollback.assert_called_once()
    connection.close.assert_called_once()
