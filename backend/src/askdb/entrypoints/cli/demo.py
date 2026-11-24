from collections.abc import Mapping
from dataclasses import dataclass
from urllib.parse import quote

from askdb.databases.catalog import SchemaCatalogPort
from askdb.queries.errors import ApplicationError
from askdb.settings import Settings


@dataclass(frozen=True)
class DemoConnection:
    name: str
    tables: tuple[str, ...]
    settings: Settings


def demo_connections(source: Mapping[str, str | None]) -> tuple[DemoConnection, ...]:
    password = source.get("ASKDB_READER_PASSWORD")
    if not password:
        raise ApplicationError("configuration_error", "Defina ASKDB_READER_PASSWORD no backend/.env.")
    try:
        port = int(source.get("ASKDB_DEMO_POSTGRES_PORT") or "5434")
        if not 1 <= port <= 65535:
            raise ValueError()
    except ValueError:
        raise ApplicationError("configuration_error", "ASKDB_DEMO_POSTGRES_PORT deve ser uma porta entre 1 e 65535.") from None

    cases = (
        ("Vendas", "demo_vendas", ("pedidos", "clientes", "pagamentos")),
        ("Suporte", "demo_suporte", ("chamados", "categorias", "equipes")),
        ("Estoque", "demo_estoque", ("posicoes_estoque", "depositos", "produtos")),
    )
    connections = []
    for name, database, tables in cases:
        url = f"postgresql://askdb_reader:{quote(password, safe='')}@127.0.0.1:{port}/{database}"
        settings = Settings.from_env({**source, "DATABASE_URL": url})
        connections.append(DemoConnection(name, tables, settings.model_copy(
            update={"app_data_dir": settings.app_data_dir / "demo"},
        )))
    return tuple(connections)


def check_demo_connection(case: DemoConnection, catalog: SchemaCatalogPort) -> None:
    readable_tables = {table.name for table in catalog.discover().tables if table.schema_name == "public"}
    missing = sorted(set(case.tables) - readable_tables)
    if missing:
        raise ApplicationError(
            "demo_schema_missing",
            f"Tabelas sem acesso de leitura em public: {', '.join(missing)}. "
            "Confira as permissões e se o banco já contém a carga atual da demo.",
        )
