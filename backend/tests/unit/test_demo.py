import json
from pathlib import Path
from runpy import run_path
from unittest.mock import Mock
from urllib.parse import unquote, urlsplit

import httpx
import pytest

from askdb.bootstrap import build_cli_session
from askdb.databases.catalog import Column, SchemaCatalog, Table
from askdb.entrypoints.cli import app as cli
from askdb.entrypoints.cli.demo import check_demo_connection, demo_connections
from askdb.queries.errors import ApplicationError
from askdb.queries.models import QueryResult


DEMO_DIR = Path(__file__).resolve().parents[2] / "demo"
TEMPLATES = DEMO_DIR / "contexts"


@pytest.fixture(scope="module")
def prepare_demo_context():
    return run_path(str(DEMO_DIR / "prepare.py"))["prepare_demo_context"]


def source(app_dir):
    return {
        "ASKDB_APP_DATA_DIR": str(app_dir),
        "ASKDB_DEMO_POSTGRES_PORT": "15434",
        "ASKDB_READER_PASSWORD": "local@:%/#?%$42",
        "DATABASE_URL": "valor ignorado pela demo",
    }


def test_demo_context_depends_on_destination_and_preserves_edits(tmp_path, prepare_demo_context):
    env = source(tmp_path)
    cases = demo_connections(env)
    paths = [prepare_demo_context(case, TEMPLATES) for case in cases]

    assert [case.name for case in cases] == ["Vendas", "Suporte", "Estoque"]
    assert len(set(paths)) == 3
    for case, path in zip(cases, paths, strict=True):
        connection = case.settings.connection
        assert path == tmp_path / "demo" / "connections" / connection.id / "context.md"
        assert path.read_bytes() == (TEMPLATES / f"{connection.database}.md").read_bytes()
        assert connection.port == 15434
        assert unquote(urlsplit(case.settings.database_url.get_secret_value()).password) == env["ASKDB_READER_PASSWORD"]
        assert env["ASKDB_READER_PASSWORD"] not in str(case)

    paths[0].write_text("# Meu ensaio", encoding="utf-8")
    paths[1].unlink()
    assert [prepare_demo_context(case, TEMPLATES) for case in cases] == paths
    assert paths[0].read_text(encoding="utf-8") == "# Meu ensaio"
    assert paths[1].is_file()

    moved = demo_connections({**env, "ASKDB_DEMO_POSTGRES_PORT": "25434"})
    assert {case.settings.connection.id for case in moved}.isdisjoint(
        case.settings.connection.id for case in cases
    )


@pytest.mark.parametrize(("name", "value"), [
    ("ASKDB_DEMO_POSTGRES_PORT", "senha-ficticia"),
    ("ASKDB_DEMO_POSTGRES_PORT", "65536"),
    ("ASKDB_READER_PASSWORD", ""),
])
def test_invalid_demo_configuration_is_reported_without_values(tmp_path, name, value):
    with pytest.raises(ApplicationError, match=name) as error:
        demo_connections({**source(tmp_path), name: value})
    assert "senha-ficticia" not in str(error.value)
    assert "local@:" not in str(error.value)


def test_demo_rejects_legacy_or_incomplete_catalog(tmp_path):
    support = demo_connections(source(tmp_path))[1]
    catalog = Mock()
    catalog.discover.return_value = SchemaCatalog(tables=[
        Table(schema_name="public", name="chamados", columns=[]),
        Table(schema_name="outro", name="equipes", columns=[]),
    ])

    with pytest.raises(ApplicationError, match="categorias, equipes") as error:
        check_demo_connection(support, catalog)
    assert error.value.code == "demo_schema_missing"


def test_preparation_replaces_only_the_shipped_first_context(tmp_path, prepare_demo_context):
    support = demo_connections(source(tmp_path))[1]
    path = prepare_demo_context(support, TEMPLATES)
    old_context = (
        "# Suporte\r\n\r\nRegra de negócio para o ensaio\r\n\r\n"
        "- Use a tabela `public.chamados`. Cada linha representa um chamado.\r\n"
        "- A **fila ativa** reúne chamados com `status` igual a `OPEN` ou `IN_PROGRESS`.\r\n"
        "- Chamados resolvidos ou cancelados ficam fora da fila ativa.\r\n"
    )
    path.write_bytes(old_context.encode("utf-8-sig"))
    assert prepare_demo_context(support, TEMPLATES).read_bytes() == (TEMPLATES / "demo_suporte.md").read_bytes()

    custom = old_context + "\r\nPolítica local da equipe."
    path.write_bytes(custom.encode("utf-8"))
    assert prepare_demo_context(support, TEMPLATES).read_bytes() == custom.encode("utf-8")


def test_cli_demo_keeps_the_model_and_opens_an_isolated_session_on_each_choice(
    tmp_path, monkeypatch, prepare_demo_context,
):
    env = source(tmp_path)
    cases = demo_connections(env)
    for case in cases:
        prepare_demo_context(case, TEMPLATES)
    monkeypatch.setattr(cli, "read_environment", lambda: env)
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    sessions, payloads, queries, secrets = [], [], [], []

    def build(settings, *, profile, api_key):
        case = next(case for case in cases if case.settings.connection.id == settings.connection.id)
        sql = f"SELECT id FROM {case.tables[0]}"

        def respond(request):
            payloads.append(json.loads(request.content))
            return httpx.Response(200, json={
                "choices": [{"finish_reason": "stop", "message": {"content": sql}}],
            })

        generation, execution, path = build_cli_session(settings, profile=profile, api_key=api_key,
                                                        transport=httpx.MockTransport(respond))
        sessions.append(generation)
        monkeypatch.setattr(generation.catalog, "discover", lambda: SchemaCatalog(tables=[
            Table(schema_name="public", name=table, columns=[
                Column(name="id", data_type="integer", nullable=False),
            ]) for table in case.tables
        ]))
        execution.query = Mock()
        execution.query.execute.return_value = QueryResult(columns=["id"], rows=[(1,)], duration_ms=1)
        queries.append(execution.query)
        return generation, execution, path

    def secret(prompt):
        secrets.append(prompt)
        return "chave-do-teste"

    monkeypatch.setattr(cli, "build_cli_session", build)
    # Inclui uma tentativa inacessível e o retorno a Vendas.
    check = cli.check_demo_connection
    errors = iter([True, False, False, False, False])

    def check_once(case, adapter):
        if next(errors):
            raise ApplicationError("database_unavailable", "Servidor indisponível.")
        check(case, adapter)

    monkeypatch.setattr(cli, "check_demo_connection", check_once)
    answers = iter([
        "inválido", "1", "fora-da-lista", "2", "vendas", "qual id em vendas?", "sim",
        "trocar", "estoque", "qual id em estoque?", "não",
        "trocar", "suporte", "qual id em suporte?", "sim",
        "trocar", "1", "qual id em vendas de novo?", "sim", "sair",
    ])
    output = []
    assert cli.main(demo=True, read=lambda _: next(answers), write=output.append, ask_secret=secret) == 0
    text = "\n".join(output)
    assert "Servidor indisponível" in text and "Escolha 1, 2 ou 3" in text
    assert "deepseek-flash" in text and "demo_vendas" in text and "askdb_reader" in text
    assert "Contexto carregado: Vendas" in text
    assert env["ASKDB_READER_PASSWORD"] not in text and "chave-do-teste" not in text
    assert len(secrets) == 1
    assert len({session.session.id for session in sessions}) == len(sessions) == 5
    assert len({id(session.pending) for session in sessions}) == len(sessions)
    assert all(session.session.question_sql_pairs == [] for session in sessions)
    assert [query.execute.call_count for query in queries] == [0, 1, 0, 1, 1]
    expected = [cases[0], cases[2], cases[1], cases[0]]
    assert len(payloads) == len(expected)
    for payload, case in zip(payloads, expected, strict=True):
        content = json.loads(payload["messages"][1]["content"])
        assert content["session_pairs"] == []
        assert case.name in str(content)
        assert payload["model"] == "deepseek-flash"
