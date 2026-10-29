
import sqlglot
from sqlglot import exp
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.main import engine


def executar_consulta_segura(sql: str) -> list[dict]:
    """
    Executa uma única consulta SELECT, sem permitir
    operações de escrita ou múltiplas instruções.
    """
    try:
        instrucoes = [
            instrucao
            for instrucao in sqlglot.parse(sql, read="postgres")
            if instrucao is not None
        ]
    except sqlglot.errors.ParseError as erro:
        raise ValueError("SQL inválido.") from erro

    if len(instrucoes) != 1:
        raise ValueError("Envie apenas uma consulta SQL por vez.")

    consulta = instrucoes[0]

    if not isinstance(consulta, exp.Select):
        raise ValueError("Somente consultas SELECT são permitidas.")

    # Bloqueia SELECT INTO e cláusulas que podem alterar dados.
    if consulta.find(exp.Into):
        raise ValueError("SELECT INTO não é permitido.")

    # Bloqueia operações de escrita escondidas em CTEs ou subconsultas.
    for no in consulta.walk():
        if isinstance(no, (exp.Insert, exp.Update, exp.Delete, exp.Merge, exp.Command)):
            raise ValueError("A consulta contém uma operação não permitida.")

    try:
        with engine.connect() as conexao:
            resultado = conexao.execute(text(sql))
            return [dict(linha) for linha in resultado.mappings().all()]
    except SQLAlchemyError as erro:
        raise ValueError("Não foi possível executar a consulta.") from erro
