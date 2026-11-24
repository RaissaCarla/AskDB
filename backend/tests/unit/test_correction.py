import json

import pytest

from askdb.llm.models import LLMResponse
from askdb.queries.errors import ApplicationError
from askdb.queries.models import SessionContext, SqlGenerationRequest
from test_generate import make_use_case


def session_use_case():
    use_case = make_use_case()
    use_case.connection_id = "c"
    use_case.session = SessionContext(connection_id="c")
    return use_case


def test_approved_registration_and_invalidation_on_new_question():
    use_case = session_use_case()
    first = use_case.execute(SqlGenerationRequest(question="produtos"))
    assert use_case.pending.get(first.id, "c", use_case.session.id).sql == first.sql
    second = use_case.execute(SqlGenerationRequest(question="outra pergunta"))
    assert first.id != second.id
    with pytest.raises(ApplicationError):
        use_case.pending.get(first.id, "c", use_case.session.id)
    use_case.llm.generate.return_value = LLMResponse(sql="DELETE FROM produtos")
    blocked = use_case.execute(SqlGenerationRequest(question="bloqueio"))
    with pytest.raises(ApplicationError):
        use_case.pending.get(blocked.id, "c", use_case.session.id)


def test_single_counter_across_generation_and_execution_error():
    use_case = session_use_case()
    use_case.llm.generate.side_effect = [LLMResponse(sql="SELECT FROM"),
        LLMResponse(sql="SELECT missing FROM produtos"), LLMResponse(sql="SELECT nome FROM produtos")]
    first = use_case.execute(SqlGenerationRequest(question="produtos"))
    assert first.attempt == 2
    corrected = use_case.correct(first, ApplicationError("query_resolution_error", "valor-sentinela-privado"))
    assert corrected.attempt == 3 and corrected.id != first.id
    payload = json.loads(use_case.llm.generate.call_args.args[0].messages[1]["content"])
    assert payload["correction"]["category"] == "query_resolution_error"
    assert "valor-sentinela" not in json.dumps(payload)
    assert "rows" not in json.dumps(payload)
    with pytest.raises(ApplicationError) as error:
        use_case.correct(corrected, ApplicationError("query_syntax_error", "não enviar"))
    assert error.value.code == "generation_attempts_exhausted" and use_case.llm.generate.call_count == 3


@pytest.mark.parametrize("code", ["llm_timeout", "llm_authentication_failed", "llm_rate_limited", "llm_unavailable", "database_unavailable"])
def test_infrastructure_failure_never_retries(code, caplog):
    use_case = session_use_case()
    use_case.llm.generate.side_effect = ApplicationError(code, "Mensagem pública fixa.")
    with pytest.raises(ApplicationError):
        use_case.execute(SqlGenerationRequest(question="pergunta-privada"))
    assert use_case.llm.generate.call_count == 1
    assert "pergunta-privada" not in caplog.text


@pytest.mark.parametrize("sql", ["DELETE FROM produtos", "SELECT 1; DELETE FROM produtos", "SELECT pg_sleep(1)",
    "WITH x AS (SELECT 1) SELECT * FROM x", "SELECT COUNT(*)::text, pg_sleep(1) FROM chamados",
    "SELECT COUNT(*)::text FROM pg_catalog.pg_roles"])
def test_security_blocks_never_retry(sql):
    use_case = session_use_case()
    use_case.llm.generate.return_value = LLMResponse(sql=sql)
    item = use_case.execute(SqlGenerationRequest(question="pergunta"))
    assert item.validation.status == "blocked" and use_case.llm.generate.call_count == 1
    with pytest.raises(ApplicationError):
        use_case.correct(item, ApplicationError("query_syntax_error", ""))


def test_scalar_cast_is_retried_without_registering_the_blocked_sql():
    use_case = session_use_case()
    monthly = ("SELECT COUNT(*) FROM chamados WHERE EXTRACT(MONTH FROM created_at) = "
               "EXTRACT(MONTH FROM CURRENT_DATE) AND EXTRACT(YEAR FROM created_at) = "
               "EXTRACT(YEAR FROM CURRENT_DATE)")
    rejected = monthly.replace("COUNT(*)", "COUNT(*)::text")
    use_case.llm.generate.side_effect = [LLMResponse(sql=rejected), LLMResponse(sql=monthly)]

    proposal = use_case.execute(SqlGenerationRequest(question="quantos chamados temos esse mês?"))
    assert proposal.attempt == 2 and proposal.sql == monthly
    assert use_case.session.question_sql_pairs == [("quantos chamados temos esse mês?", monthly)]
    payload = json.loads(use_case.llm.generate.call_args.args[0].messages[1]["content"])
    assert payload["correction"] == {"category": "unsupported_cast", "previous_sql": rejected}


def test_invalid_final_response_caps_at_three_and_new_budget_per_correction():
    use_case = session_use_case()
    use_case.llm.generate.side_effect = ApplicationError("llm_invalid_response", "saída inválida")
    with pytest.raises(ApplicationError) as error:
        use_case.execute(SqlGenerationRequest(question="pergunta"))
    assert error.value.code == "generation_attempts_exhausted" and use_case.llm.generate.call_count == 3
    assert use_case.catalog.discover.call_count == 3
    fresh = session_use_case()
    first = fresh.execute(SqlGenerationRequest(question="pergunta"))
    fresh.catalog.discover.return_value.tables[0].name = "x" * 20000
    with pytest.raises(ApplicationError) as error:
        fresh.correct(first, ApplicationError("query_resolution_error", ""))
    assert error.value.code == "context_limit_exceeded" and fresh.llm.generate.call_count == 1


@pytest.mark.parametrize("code", ["query_permission_denied", "query_timeout", "query_failed", "database_unavailable"])
def test_execution_failures_outside_positive_list(code):
    use_case = session_use_case()
    first = use_case.execute(SqlGenerationRequest(question="produtos"))
    with pytest.raises(ApplicationError):
        use_case.correct(first, ApplicationError(code, "valor-sentinela"))
    assert use_case.llm.generate.call_count == 1
