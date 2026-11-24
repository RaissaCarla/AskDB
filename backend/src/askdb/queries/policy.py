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
    exp.CurrentDate, exp.Extract,
})
RETRYABLE_PROPOSAL_CODES = frozenset({"invalid_sql", "unsupported_cast"})


def _is_primitive_cast(node):
    return (
        type(node) is exp.Cast
        and isinstance(node.to, exp.DataType)
        and node.to.this in {exp.DataType.Type.TEXT, exp.DataType.Type.INT, exp.DataType.Type.BIGINT}
        and not node.to.expressions
    )


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
        has_primitive_cast = False
        for node in tree.walk():
            # A conversão continua bloqueada. Só é elegível para nova geração se o restante passar.
            if _is_primitive_cast(node):
                has_primitive_cast = True
                continue
            if type(node) is exp.DataType and _is_primitive_cast(node.parent) and node is node.parent.to:
                continue
            if type(node) is exp.Var and type(node.parent) is exp.Extract and node is node.parent.this:
                continue
            if type(node) not in ALLOWED_NODES:
                return blocked("unsupported_structure", "A SQL contém uma construção fora da política inicial.")
            if isinstance(node, exp.Extract) and (
                node.this.name.upper() not in {"MONTH", "YEAR"}
                or not isinstance(node.expression, (exp.Column, exp.CurrentDate))
            ):
                return blocked("unsupported_structure", "EXTRACT aceita mês ou ano de uma coluna de data ou de CURRENT_DATE.")
            if isinstance(node, exp.CurrentDate) and node.args:
                return blocked("unsupported_structure", "Use CURRENT_DATE sem argumentos.")
            if isinstance(node, exp.Table):
                if (not isinstance(node.this, exp.Identifier) or node.catalog
                    or node.db.lower().startswith("pg_") or node.db.lower() == "information_schema"
                    or node.name.lower().startswith("pg_")):
                    return blocked("restricted_relation", "Referência a objeto de sistema ou tabela não suportada.")
        if has_primitive_cast:
            return blocked("unsupported_cast", "Remova CAST ou ::. A consulta deve retornar o tipo original do valor.")
        return ValidationResult(status="approved")
