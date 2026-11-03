from time import perf_counter

from pydantic import ValidationError

from askdb.bootstrap import build_use_case
from askdb.queries.errors import ApplicationError
from askdb.queries.models import SqlGenerationRequest

SEPARATOR = "-" * 60
ERROR_HINTS = {
    "database_unavailable": "Confira se o PostgreSQL está ativo e revise DATABASE_URL no backend/.env.",
    "configuration_error": "Confira os valores do arquivo backend/.env.",
    "llm_unavailable": "Confira se o Ollama está ativo e se o modelo está instalado.",
    "llm_timeout": "Tente novamente ou ajuste LLM_TIMEOUT no backend/.env.",
    "llm_invalid_response": "Tente reformular a pergunta para obter uma nova proposta.",
}


def show_error(code, message, write):
    write(f"\n[Erro] {message}")
    write(f"Código: {code}")
    if code in ERROR_HINTS:
        write("Dica: " + ERROR_HINTS[code])
    write("Você pode tentar outra pergunta.\n")


def run(use_case, read=input, write=print):
    write("\n" + SEPARATOR)
    write("  AskDB | Assistente de consultas PostgreSQL")
    write(SEPARATOR)
    write("Escreva sua pergunta em português para gerar uma proposta SQL.")
    write("Exemplo: Quais são os cinco produtos mais vendidos?")
    write("A SQL será validada e exibida, sem execução no banco.")
    write("Digite sair ou pressione Ctrl+C para encerrar.\n")
    while True:
        try:
            text = read("Sua pergunta > ")
            if text.strip().lower() == "sair":
                write("\nSessão encerrada. Até a próxima!")
                return
            request = SqlGenerationRequest(question=text)
            write("\nConsultando o esquema, gerando e validando a SQL... Aguarde.")
            started = perf_counter()
            proposal = use_case.execute(request)
            elapsed = perf_counter() - started
            write("\n" + SEPARATOR)
            write("SQL proposta\n")
            write(proposal.sql)
            write("\n" + SEPARATOR)
            if proposal.validation.status == "approved":
                write("[OK] Proposta aprovada pela política inicial.")
                write("Você pode inspecionar e copiar a SQL acima.")
            else:
                write("[Bloqueada] A proposta não passou pela política de segurança.")
                write("Motivos:")
            for reason in proposal.validation.reasons:
                write(f"  - {reason.message} ({reason.code})")
            write(f"Tempo total: {elapsed:.1f} s | SQL não executada.")
            write(SEPARATOR + "\n")
        except (EOFError, KeyboardInterrupt):
            write("\nSessão encerrada. Até a próxima!")
            return
        except ValidationError:
            show_error("invalid_input", "Informe uma pergunta com 1 a 2000 caracteres.", write)
        except ApplicationError as error:
            show_error(error.code, error.message, write)
        except Exception:
            show_error("unexpected_error", "Não foi possível processar a pergunta.", write)


def main():
    import logging
    # Mantém eventos técnicos fora da interação normal no terminal.
    logging.basicConfig(level=logging.WARNING, format="%(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    try:
        run(build_use_case())
    except ApplicationError as error:
        print(f"\n[Erro ao iniciar] {error.message}")
        print(f"Código: {error.code}")
        print("Confira o arquivo backend/.env e execute a CLI novamente.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
