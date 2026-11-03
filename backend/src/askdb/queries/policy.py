import sqlglot
from sqlglot import expressions as exp
from sqlglot.errors import SqlglotError

from askdb.queries.models import ValidationReason, ValidationResult


# Cada novo tipo de expressão exige decisão explícita e testes.
ALLOWED_NODES = frozenset({
    exp.Select, exp.From, exp.Table, exp.Column, exp.Identifier, exp.Star,
    exp.Alias, exp.TableAlias, exp.Literal, exp.Null, exp.Boolean,
    exp.Where, exp.Join, exp.Group, exp.Having, exp.Order, exp.Ordered,
    exp.Limit, exp.Offset, exp.Distinct, exp.Paren,
    exp.EQ, exp.NEQ, exp.GT, exp.GTE, exp.LT, exp.LTE,
    exp.And, exp.Or, exp.Not, exp.Is, exp.In, exp.Between, exp.Like, exp.ILike,
    exp.Add, exp.Sub, exp.Mul, exp.Div, exp.Mod, exp.Neg,
    exp.Count, exp.Sum, exp.Avg, exp.Min, exp.Max, exp.Lower, exp.Upper, exp.Coalesce,
})


class SqlPolicyValidator:
    def validate(self, sql: str) -> ValidationResult:
        def blocked(code, message):
            return ValidationResult(status="blocked", reasons=[ValidationReason(code=code, message=message)])

        if not sql.strip() or len(sql) > 16000:
            return blocked("invalid_sql", "SQL vazia ou acima do limite.")
        try:
            statements = sqlglot.parse(sql, read="postgres", error_level=sqlglot.ErrorLevel.RAISE)
        except (SqlglotError, ValueError, RecursionError):
            return blocked("invalid_sql", "SQL não reconhecida integralmente no dialeto PostgreSQL.")
        if len(statements) != 1 or not isinstance(statements[0], exp.Select):
            return blocked("statement_not_allowed", "É permitida somente uma instrução SELECT.")
        tree = statements[0]
        if not tree.expressions:
            return blocked("invalid_sql", "SELECT sem projeção válida.")
        for node in tree.walk():
            if type(node) not in ALLOWED_NODES:
                return blocked("unsupported_structure", "A SQL contém uma construção fora da política inicial.")
            if isinstance(node, exp.Table):
                if (not isinstance(node.this, exp.Identifier) or node.catalog
                    or node.db.lower().startswith("pg_") or node.db.lower() == "information_schema"
                    or node.name.lower().startswith("pg_")):
                    return blocked("restricted_relation", "Referência a objeto de sistema ou tabela não suportada.")
        return ValidationResult(status="approved")
