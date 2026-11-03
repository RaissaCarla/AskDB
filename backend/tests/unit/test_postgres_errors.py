from unittest.mock import MagicMock

import psycopg
import pytest

from askdb.databases.postgres import PostgresDatabaseAdapter
from askdb.queries.errors import ApplicationError


@pytest.mark.parametrize("failure", [psycopg.OperationalError, psycopg.errors.InvalidPassword])
def test_connection_error_sanitized(monkeypatch, failure):
    def fail(*args, **kwargs):
        assert kwargs["connect_timeout"] == 10
        assert "statement_timeout=10000" in kwargs["options"]
        raise failure("senha-secreta")
    monkeypatch.setattr(psycopg, "connect", fail)
    with pytest.raises(ApplicationError) as error:
        PostgresDatabaseAdapter("dsn-secreta").discover()
    assert error.value.code == "database_unavailable"
    assert "secreta" not in str(error.value)


@pytest.mark.parametrize("role", [{"rolsuper": True, "rolbypassrls": False},
                                {"rolsuper": False, "rolbypassrls": True}])
def test_unsafe_role_closes_connection(monkeypatch, role):
    manager = MagicMock()
    connection = manager.__enter__.return_value
    connection.execute.return_value.fetchone.return_value = role
    monkeypatch.setattr(psycopg, "connect", lambda *a, **k: manager)
    with pytest.raises(ApplicationError) as error:
        PostgresDatabaseAdapter("dsn").discover()
    assert error.value.code == "configuration_error"
    manager.__exit__.assert_called_once()


def test_metadata_failure_closes_connection(monkeypatch):
    manager = MagicMock()
    connection = manager.__enter__.return_value
    connection.execute.side_effect = psycopg.errors.QueryCanceled("senha-secreta")
    monkeypatch.setattr(psycopg, "connect", lambda *a, **k: manager)
    with pytest.raises(ApplicationError) as error:
        PostgresDatabaseAdapter("dsn").discover()
    assert error.value.code == "database_unavailable"
    assert "secreta" not in str(error.value)
    manager.__exit__.assert_called_once()
