import os

import pytest

from askdb.databases.postgres import PostgresDatabaseAdapter
from askdb.queries.errors import ApplicationError

pytestmark = pytest.mark.integration


@pytest.fixture
def catalog():
    url = os.getenv("ASKDB_TEST_DATABASE_URL")
    if not url:
        pytest.skip("Defina ASKDB_TEST_DATABASE_URL para o banco de teste.")
    return PostgresDatabaseAdapter(url).discover()


def test_catalog_and_composite_keys(catalog):
    tables = {table.name: table for table in catalog.tables}
    assert {"clientes", "produtos", "pedidos", "itens_pedido"} <= tables.keys()
    assert tables["itens_pedido"].primary_key == ["pedido_id", "produto_id"]
    fk = tables["referencia_composta"].foreign_keys[0]
    assert fk.columns == ["x", "y"] and fk.target_columns == ["a", "b"]


def test_permissions(catalog):
    tables = {table.name: table for table in catalog.tables}
    assert "restrita" not in tables
    assert [c.name for c in tables["parcial"].columns] == ["id", "publico"]
    assert tables["referencia_restrita"].foreign_keys == []
    assert all(t.schema_name == "public" for t in catalog.tables)


def test_reject_admin():
    url = os.getenv("ASKDB_TEST_ADMIN_URL")
    if not url:
        pytest.skip("Defina ASKDB_TEST_ADMIN_URL.")
    with pytest.raises(ApplicationError, match="role") as error:
        PostgresDatabaseAdapter(url).discover()
    assert error.value.code == "configuration_error"
