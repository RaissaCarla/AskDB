from datetime import date
from decimal import Decimal
import json
from unittest.mock import Mock

import httpx
import pytest
from pydantic import SecretStr

from askdb.bootstrap import build_cli_session
from askdb.databases.catalog import Column, SchemaCatalog, Table
from askdb.entrypoints import cli
from askdb.llm.models import LLMResponse
from askdb.queries.errors import ApplicationError
from askdb.queries.models import QueryResult
from askdb.settings import Settings


def runtime(tmp_path, monkeypatch):
    settings = Settings(database_url="postgresql://reader:p@localhost/demo", app_data_dir=tmp_path / "app")
    profile = settings.profile("deepseek")
    calls = []
    def handler(request):
        calls.append(json.loads(request.content))
        return httpx.Response(200, json={"choices":[{"finish_reason":"stop","message":{"content":"SELECT nome FROM produtos"}}]})
    generation, execution, path = build_cli_session(settings, profile=profile, api_key=SecretStr("chave-sentinela"),
                                                   transport=httpx.MockTransport(handler))
    catalog = SchemaCatalog(tables=[Table(schema_name="public", name="produtos", columns=[Column(name="nome",data_type="text",nullable=False)])])
    monkeypatch.setattr(generation.catalog, "discover", lambda: catalog)
    query = Mock()
    query.execute.return_value = QueryResult(columns=["nome"], rows=[("resultado-privado-sentinela",)], duration_ms=1.0)
    execution.query = query
    return settings, generation, execution, path, calls


def read_entries(values, output=None):
    sequence = iter(values)
    def read(prompt):
        if output is not None:
            output.append(prompt)
        value = next(sequence)
        if isinstance(value, type) and issubclass(value, BaseException):
            raise value()
        return value
    return read


@pytest.mark.parametrize("confirmation", ["", "não", EOFError, KeyboardInterrupt])
def test_cancellation_and_confirmation_interrupt_never_execute(tmp_path, monkeypatch, confirmation):
    settings, generation, execution, path, calls = runtime(tmp_path, monkeypatch)
    entries = ["produtos", confirmation] + ([] if isinstance(confirmation,type) else ["sair"])
    output = []
    cli.run(generation, read=read_entries(entries, output), write=output.append, executor=execution,
            context_path=path, destination=settings.connection.label)
    execution.query.execute.assert_not_called()
    assert len(calls) == 1 and generation.session.question_sql_pairs == []
    assert str(path) in "\n".join(output)


def test_sql_and_destination_before_confirmation_and_no_results_to_llm(tmp_path, monkeypatch):
    settings, generation, execution, path, calls = runtime(tmp_path, monkeypatch)
    output = []
    cli.run(generation, read=read_entries(["produtos","sim","outra pergunta","não","sair"], output),
            write=output.append, executor=execution, context_path=path, destination=settings.connection.label)
    text = "\n".join(output)
    assert text.index("SELECT nome FROM produtos") < text.index("Executar exatamente")
    assert text.index(settings.connection.label) < text.index("Executar exatamente")
    assert "resultado-privado-sentinela" in text and "chave-sentinela" not in text
    assert "resultado-privado-sentinela" not in json.dumps(calls)
    assert len(json.loads(calls[1]["messages"][1]["content"])["session_pairs"]) == 1
    execution.query.execute.assert_called_once_with(settings.connection.id, "SELECT nome FROM produtos")


def test_corrected_query_requires_fresh_confirmation_and_max_three_calls(tmp_path, monkeypatch):
    settings, generation, execution, path, calls = runtime(tmp_path, monkeypatch)
    execution.query.execute.side_effect = [ApplicationError("query_resolution_error","Mensagem fixa."),
        ApplicationError("query_resolution_error","Mensagem fixa."), QueryResult(columns=["x"],rows=[(1,)],duration_ms=1.0)]
    output = []
    cli.run(generation, read=read_entries(["produtos","sim","sim","sim","sair"], output),
            write=output.append, executor=execution, destination=settings.connection.label)
    assert len(calls) == 3 and execution.query.execute.call_count == 3
    assert sum("Executar exatamente" in line for line in output) == 3
    assert "tentativa 3/3" in "\n".join(output)
    assert generation.session.active_question is None


def test_table_format_preserves_positions_types_and_empty():
    result = QueryResult(columns=["nome","nome","valor","data","nota"],
        rows=[("a","b",Decimal("12.50"),date(2026,11,17),None)],duration_ms=1.0,truncated=True)
    text = "\n".join(cli.format_result(result))
    assert "12.50" in text and "2026-11-17" in text and "NULL" in text and "truncado" in text
    assert cli.format_result(QueryResult(columns=["nome"],rows=[],duration_ms=0.0))[-1].startswith("0 linha")


def test_main_key_input_and_profile_selection(tmp_path, monkeypatch):
    settings, generation, execution, path, calls = runtime(tmp_path, monkeypatch)
    monkeypatch.setenv("DATABASE_URL", "postgresql://reader:p@localhost/demo")
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    received = []
    def build(settings, **kwargs):
        received.append(kwargs)
        return generation, execution, path
    monkeypatch.setattr(cli, "build_cli_session", build)
    output, prompts = [], []
    def secret(prompt):
        prompts.append(prompt)
        return "chave-oculta"
    assert cli.main(read=read_entries(["inválido","1","produtos","não","sair"]), write=output.append, ask_secret=secret) == 0
    assert len(prompts) == 1 and received[0]["api_key"].get_secret_value() == "chave-oculta"
    assert "chave-oculta" not in "\n".join(output) and "Traceback" not in "\n".join(output)
    changed = settings.model_copy(update={"llm_model":"modelo-ollama-personalizado"})
    assert cli.select_profile(changed, read=read_entries(["1"]), write=lambda x: None).model == "deepseek-flash"


def test_invalid_configuration_and_error_recovery(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "configuração inválida secreta")
    output = []
    assert cli.main(read=read_entries([]), write=output.append) == 1
    assert "secreta" not in "\n".join(output)
    settings, generation, execution, path, calls = runtime(tmp_path, monkeypatch)
    generation.llm = Mock()
    generation.llm.generate.side_effect = [ApplicationError("llm_unavailable","Falha pública."), LLMResponse(sql="SELECT nome FROM produtos")]
    cli.run(generation, read=read_entries([" ","produtos","produtos","não","sair"]), write=output.append, executor=execution)
    assert generation.llm.generate.call_count == 2 and "llm_unavailable" in "\n".join(output)


def test_terminal_without_hidden_input_never_falls_back_to_echo(monkeypatch):
    import getpass
    import warnings
    monkeypatch.setenv("DATABASE_URL", "postgresql://reader:p@localhost/demo")
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    def fallback(prompt):
        warnings.warn("entrada sem proteção", getpass.GetPassWarning)
        raise AssertionError("Não pode chegar ao fallback que ecoaria o segredo")
    monkeypatch.setattr(getpass, "getpass", fallback)
    output = []
    assert cli.main(read=read_entries(["1"]), write=output.append) == 1
    assert "entrada oculta" in "\n".join(output)
