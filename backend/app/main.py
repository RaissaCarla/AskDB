
from fastapi import FastAPI

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
    return {
        "status": "ok"
    }
