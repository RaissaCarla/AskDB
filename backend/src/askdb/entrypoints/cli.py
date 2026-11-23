from time import perf_counter

from pydantic import ValidationError

from askdb.bootstrap import build_cli_session
from askdb.llm.credentials import read_api_key
from askdb.queries.errors import ApplicationError
from askdb.queries.models import ExecuteSqlRequest, QueryResult, SessionContext, SqlGenerationRequest
from askdb.settings import Settings

SEPARATOR = "-" * 60
ERROR_HINTS = {
    "database_unavailable": "Confira se o PostgreSQL está ativo e revise DATABASE_URL no backend/.env.",
    "configuration_error": "Confira os valores do arquivo backend/.env.",
    "llm_unavailable": "Confira o provedor e a disponibilidade do modelo selecionado.",
    "llm_timeout": "Tente novamente ou ajuste LLM_TIMEOUT no backend/.env.",
    "llm_invalid_response": "Tente reformular a pergunta para obter uma nova proposta.",
    "llm_authentication_failed": "Confira a chave no ambiente do processo ou na entrada oculta; não a grave no contexto.",
    "llm_rate_limited": "Confira o saldo e o limite de requisições do provedor selecionado.",
    "context_limit_exceeded": "Reduza o Markdown explicitamente ou inicie outra sessão.",
    "context_budget_unavailable": "Escolha um modelo com orçamento validado.",
    "knowledge_unavailable": "Confira acesso, UTF-8 e caminho do arquivo de contexto.",
}


def show_error(code, message, write):
    write(f"\n[Erro] {message}")
    write(f"Código: {code}")
    if code in ERROR_HINTS:
        write("Dica: " + ERROR_HINTS[code])
    write("Você pode tentar outra pergunta.\n")


def format_result(result: QueryResult) -> list[str]:
    def cell(value):
        text = "NULL" if value is None else str(value)
        return "".join(c if ord(c) >= 32 and ord(c) != 127 else f"\\x{ord(c):02x}" for c in text)
    table = [[cell(name) for name in result.columns]] + [[cell(v) for v in row] for row in result.rows]
    widths = [max(len(row[i]) for row in table) for i in range(len(result.columns))]
    lines = [" | ".join(value.ljust(widths[i]) for i, value in enumerate(table[0])),
             "-+-".join("-" * w for w in widths)]
    lines.extend(" | ".join(value.ljust(widths[i]) for i,value in enumerate(row)) for row in table[1:])
    lines.append(f"{len(result.rows)} linha(s) | {result.duration_ms:.1f} ms")
    if result.truncated:
        lines.append("Resultado truncado no limite configurado; a consulta não será repetida automaticamente.")
    return lines


def _show_proposal(proposal, write):
    write("\n" + SEPARATOR)
    write(f"SQL proposta | tentativa {proposal.attempt}/3\n")
    write(proposal.sql)
    if proposal.validation.status == "approved":
        write("[OK] Proposta aprovada pela política de leitura.")
    else:
        write("[Bloqueada] A proposta não passou pela política de segurança.")
        for reason in proposal.validation.reasons:
            write(f"  - {reason.message} ({reason.code})")


def _close_session(use_case):
    session = getattr(use_case, "session", None)
    if isinstance(session, SessionContext):
        use_case.pending.invalidate_session(session.id)
        session.reset(session.connection_id)


def run(use_case, read=input, write=print, *, executor=None, context_path=None, destination=None):
    write("\n" + SEPARATOR)
    write("  AskDB | Assistente de consultas PostgreSQL")
    write(SEPARATOR)
    write("Escreva sua pergunta em português para gerar uma proposta SQL.")
    write("Exemplo: Quais são os cinco produtos mais vendidos?")
    write("Toda execução exige confirmação explícita da SQL e do destino." if executor is not None
          else "Modo de geração: a SQL será exibida sem execução no banco.")
    if destination:
        write(f"Conexão ativa: {destination}")
    if context_path is not None:
        write(f"Arquivo de contexto: {context_path}")
        if not context_path.exists():
            write("Contexto vazio: o arquivo ainda não existe. Prepare-o manualmente em UTF-8 nesse caminho.")
    write("Digite sair ou pressione Ctrl+C para encerrar.\n")
    while True:
        try:
            text = read("Sua pergunta > ")
            if text.strip().lower() == "sair":
                _close_session(use_case)
                write("\nSessão encerrada. Até a próxima!")
                return
            request = SqlGenerationRequest(question=text)
            write("\nConsultando o esquema, gerando e validando a SQL... Aguarde.")
            started = perf_counter()
            proposal = use_case.execute(request)
            elapsed = perf_counter() - started
            while True:
                _show_proposal(proposal, write)
                if proposal.validation.status != "approved" or executor is None:
                    write(f"Tempo de geração: {elapsed:.1f} s | SQL não executada.")
                    break
                write(f"Destino da execução: {destination or proposal.connection_id}")
                confirmation = read("Executar exatamente esta SQL? Digite sim para confirmar > ")
                if confirmation.strip().casefold() not in {"sim", "s"}:
                    use_case.pending.invalidate_session(proposal.session_id)
                    write("Execução cancelada. Nenhuma consulta foi executada.")
                    break
                try:
                    result = executor.execute(ExecuteSqlRequest(proposal_id=proposal.id,
                        connection_id=proposal.connection_id, session_id=proposal.session_id, confirmed=True))
                    for line in format_result(result):
                        write(line)
                    break
                except ApplicationError as error:
                    show_error(error.code, error.message, write)
                    if error.code in {"query_syntax_error", "query_resolution_error"} and proposal.attempt < 3:
                        write("Preparando uma proposta corrigida; ela exigirá nova confirmação.")
                        proposal = use_case.correct(proposal, error)
                        continue
                    break
            write(SEPARATOR + "\n")
        except (EOFError, KeyboardInterrupt):
            _close_session(use_case)
            write("\nSessão encerrada. Até a próxima!")
            return
        except ValidationError:
            show_error("invalid_input", "Informe uma pergunta com 1 a 2000 caracteres.", write)
        except ApplicationError as error:
            show_error(error.code, error.message, write)
        except Exception:
            show_error("unexpected_error", "Não foi possível processar a pergunta.", write)


def select_profile(settings: Settings, read=input, write=print):
    write("Perfis de IA: 1 DeepSeek (API própria) | 2 Ollama local | 3 OpenAI (API própria)")
    choices = {"1": "deepseek", "2": "ollama", "3": "openai",
               "deepseek": "deepseek", "ollama": "ollama", "openai": "openai"}
    while True:
        choice = read(f"Escolha o perfil [{settings.llm_provider}] ou sair > ").strip().lower()
        if choice == "sair":
            raise EOFError()
        provider = settings.llm_provider if not choice else choices.get(choice)
        if provider is not None:
            return settings.profile(provider)
        write("Escolha 1, 2 ou 3, ou informe o nome do provedor.")


def main(*, read=input, write=print, ask_secret=None):
    import logging
    import warnings
    from getpass import GetPassWarning, getpass

    def hidden_key(prompt):
        # O fallback do getpass ecoaria a chave em um terminal sem entrada oculta.
        with warnings.catch_warnings():
            warnings.simplefilter("error", GetPassWarning)
            try:
                return getpass(prompt)
            except GetPassWarning:
                raise ApplicationError("llm_authentication_failed", "O terminal não oferece entrada oculta; use a variável de ambiente.") from None
    # Mantém eventos técnicos fora da interação normal no terminal.
    logging.basicConfig(level=logging.WARNING, format="%(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    try:
        settings = Settings.from_env()
        profile = select_profile(settings, read=read, write=write)
        api_key = None
        if profile.provider != "ollama":
            write("O provedor remoto receberá pergunta, esquema autorizado, contexto e pares pergunta/SQL; resultados não são enviados.")
            api_key = read_api_key(profile.provider, ask_secret=ask_secret or hidden_key)
        generation, execution, path = build_cli_session(settings, profile=profile, api_key=api_key)
        write(f"IA selecionada: {profile.provider} | modelo {profile.model}")
        run(generation, read=read, write=write, executor=execution,
            context_path=path, destination=settings.connection.label)
    except (EOFError, KeyboardInterrupt):
        write("\nSessão encerrada.")
        return 0
    except ApplicationError as error:
        write(f"\n[Erro ao iniciar] {error.message}")
        write(f"Código: {error.code}")
        write("Confira configuração e credencial em execução e inicie a CLI novamente.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
