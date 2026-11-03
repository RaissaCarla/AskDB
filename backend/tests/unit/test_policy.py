import pytest

from askdb.queries.policy import SqlPolicyValidator


@pytest.mark.parametrize("sql", [
    "SELECT nome FROM public.produtos LIMIT 5",
    "SELECT p.nome, SUM(i.quantidade) AS total FROM produtos p JOIN itens_pedido i ON i.produto_id=p.id GROUP BY p.nome HAVING SUM(i.quantidade)>0 ORDER BY total DESC LIMIT 5 OFFSET 0",
    "SELECT DISTINCT LOWER(nome), UPPER(nome), COALESCE(preco,0) FROM produtos WHERE preco BETWEEN 1 AND 30 AND nome IS NOT NULL",
    "SELECT COUNT(*), AVG(preco), MIN(preco), MAX(preco) FROM produtos",
    "SELECT nome FROM produtos WHERE id IN (1,2) OR nome LIKE 'C%'",
])
def test_allowed(sql):
    assert SqlPolicyValidator().validate(sql).status == "approved"


@pytest.mark.parametrize("sql", [
    "", "SELECT FROM", "isto não é SQL", "SELECT 1; DELETE FROM produtos",
    "DELETE FROM produtos", "INSERT INTO produtos VALUES (1)", "UPDATE produtos SET nome='x'",
    "DROP TABLE produtos", "SELECT * INTO copia FROM produtos", "SELECT * FROM produtos FOR UPDATE",
    "SELECT pg_sleep(10)", "SELECT COALESCE(pg_sleep(1),0)", "SELECT public.lower(nome) FROM produtos",
    "SELECT * FROM pg_catalog.pg_roles", "SELECT * FROM information_schema.tables", "SELECT * FROM pg_roles",
    "WITH x AS (SELECT 1) SELECT * FROM x", "WITH x AS (DELETE FROM produtos RETURNING *) SELECT * FROM x",
    "WITH RECURSIVE x AS (SELECT 1) SELECT * FROM x", "SELECT 1 UNION SELECT 2",
    "SELECT * FROM (SELECT * FROM produtos) p", "SELECT (SELECT 1)",
    "SELECT * FROM produtos WHERE EXISTS (SELECT 1)", "SELECT * FROM generate_series(1,10)",
    "SELECT row_number() OVER () FROM produtos", "SELECT CAST(preco AS text) FROM produtos",
])
def test_blocked_and_deterministic(sql):
    validator = SqlPolicyValidator()
    result = validator.validate(sql)
    assert result.status == "blocked" and result.reasons
    assert result == validator.validate(sql)
