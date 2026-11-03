from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from askdb.bootstrap import build_use_case
from askdb.queries.errors import ApplicationError
from askdb.queries.models import SqlGenerationRequest, SqlProposal


def create_app(use_case=None) -> FastAPI:
    application = FastAPI(title="AskDB — marco de 20%", description="Geração e validação; não executa SQL.")

    @application.exception_handler(RequestValidationError)
    async def invalid_input(request, error):
        return JSONResponse(status_code=422, content={"error": {
            "code": "invalid_input", "message": "Informe somente question textual com 1 a 2000 caracteres."}})

    @application.exception_handler(ApplicationError)
    async def application_error(request, error):
        statuses = {"llm_timeout": 504, "llm_invalid_response": 502,
                    "database_unavailable": 503, "schema_unavailable": 503,
                    "llm_unavailable": 503, "configuration_error": 503}
        return JSONResponse(status_code=statuses.get(error.code, 500), content={
            "error": {"code": error.code, "message": error.message}})

    @application.exception_handler(Exception)
    async def unexpected_error(request, error):
        return JSONResponse(status_code=500, content={"error": {
            "code": "unexpected_error", "message": "Não foi possível processar a pergunta."}})

    @application.get("/health")
    def health():
        return {"status": "ok"}

    @application.post("/queries/generate", response_model=SqlProposal)
    def generate(request: SqlGenerationRequest):
        try:
            return (use_case if use_case is not None else build_use_case()).execute(request)
        except ApplicationError:
            raise
        except Exception:
            # Evita que o servidor registre traceback com detalhes de dependências.
            return JSONResponse(status_code=500, content={"error": {
                "code": "unexpected_error", "message": "Não foi possível processar a pergunta."}})

    return application


app = create_app()


def main():
    import logging
    import uvicorn
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    uvicorn.run("askdb.entrypoints.api:app", host="127.0.0.1", port=8000)


if __name__ == "__main__":
    main()
