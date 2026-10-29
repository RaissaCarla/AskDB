
import os
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from sqlalchemy import URL, create_engine, text
from sqlalchemy.exc import SQLAlchemyError

# Carrega o .env que está na pasta backend
env_path = Path(__file__).resolve().parents[1] / ".env"
load_dotenv(env_path)

# Configura a conexão com PostgreSQL
database_url = URL.create(
    drivername="postgresql+psycopg",
    username=os.getenv("DB_USER"),
    password=os.getenv("DB_PASSWORD"),
    host=os.getenv("DB_HOST", "localhost"),
    port=int(os.getenv("DB_PORT", "5432")),
    database=os.getenv("DB_NAME", "askdb_test"),
)

engine = create_engine(database_url, pool_pre_ping=True)

app = FastAPI(
    title="AskDB API",
    description="API do sistema AskDB para consultas em linguagem natural.",
    version="0.1.0",
)


@app.get("/")
def inicio():
    return {
        "sistema": "AskDB",
        "mensagem": "API iniciada com sucesso!"
    }


@app.get("/health")
def verificar_saude():
    return {"status": "ok"}


@app.get("/db-health")
def verificar_banco():
    try:
        with engine.connect() as conexao:
            conexao.execute(text("SELECT 1"))

        return {
            "status": "ok",
            "banco": os.getenv("DB_NAME", "askdb_test"),
            "mensagem": "Conexão com PostgreSQL funcionando!"
        }
    except SQLAlchemyError:
        raise HTTPException(
            status_code=503,
            detail="Não foi possível conectar ao banco de dados."
        )


@app.get("/clientes")
def listar_clientes():
    try:
        with engine.connect() as conexao:
            resultado = conexao.execute(
                text(
                    "SELECT id, nome, cidade, idade "
                    "FROM clientes ORDER BY id"
                )
            )
            return [dict(linha) for linha in resultado.mappings().all()]

    except SQLAlchemyError:
        raise HTTPException(
            status_code=503,
            detail="Não foi possível consultar os clientes."
        )
