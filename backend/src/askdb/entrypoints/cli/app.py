from time import perf_counter

from pydantic import ValidationError

from askdb.bootstrap import build_cli_session
from askdb.llm.credentials import read_api_key
from askdb.queries.errors import ApplicationError
from askdb.queries.models import ExecuteSqlRequest, QueryResult, SessionContext, SqlGenerationRequest
from askdb.settings import Settings, read_environment

from .demo import check_demo_connection, demo_connections
from .terminal import Terminal

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


def show_error(code, message, terminal, *, demo=False):
    terminal.line(f"\n[Erro] {message}", style="bold red")
    terminal.line(f"Código: {code}")
    if demo and code == "database_unavailable":
        terminal.line("Confira o PostgreSQL da demo ou digite trocar para selecionar outra conexão.")
        return
    if code in ERROR_HINTS:
        terminal.line("Dica: " + ERROR_HINTS[code])
    terminal.line("Você pode tentar outra pergunta.")


def format_result(result: QueryResult) -> list[str]:
    rendered = []
    Terminal(write=rendered.append).result(result)
    return "\n".join(rendered).splitlines()


def _show_proposal(proposal, terminal):
    terminal.section(f"SQL proposta · tentativa {proposal.attempt}/3")
    terminal.sql(proposal.sql)
    if proposal.validation.status == "approved":
        terminal.line("SQL aprovada pela política de leitura.", style="green")
    else:
        terminal.line("[Bloqueada] A proposta não passou pela política de segurança.", style="bold red")
        for reason in proposal.validation.reasons:
            terminal.line(f"  - {reason.message} ({reason.code})")


def _close_session(use_case):
    session = getattr(use_case, "session", None)
    if isinstance(session, SessionContext):
        use_case.pending.invalidate_session(session.id)
        session.reset(session.connection_id)


def run(use_case, read=input, write=print, *, executor=None, context_path=None, destination=None,
        profile=None, demo_name=None, terminal=None):
    terminal = terminal or Terminal(write=write)
    terminal.section(f"Conexão · {demo_name}" if demo_name else "AskDB V0 · Consultas PostgreSQL")
    if profile:
        terminal.line(f"Modelo: {profile.model} ({profile.provider})")
    if destination:
        terminal.line(f"Conexão ativa: {destination}")
    if demo_name:
        terminal.line(f"Contexto carregado: {demo_name} / context.md", style="dim")
    elif context_path is not None:
        terminal.line(f"Arquivo de contexto: {context_path}", style="dim")
        if not context_path.exists():
            terminal.line("Contexto vazio. Prepare um arquivo UTF-8 nesse caminho.", style="yellow")
    terminal.line()
    terminal.line("Escreva sua pergunta em português.")
    terminal.line("Leia a SQL e o destino antes de confirmar a execução." if executor is not None
                  else "Modo de geração: a SQL será exibida sem execução no banco.")
    commands = "trocar · selecionar outra conexão | " if demo_name else ""
    terminal.line(f"{commands}sair · encerrar", style="dim")
    while True:
        try:
            terminal.line()
            text = read("Sua pergunta > ")
            command = text.strip().casefold()
            if command == "sair":
                _close_session(use_case)
                terminal.line("\nSessão encerrada.")
                return
            if command == "trocar" and demo_name:
                _close_session(use_case)
                return "trocar"
            request = SqlGenerationRequest(question=text)
            terminal.line("\nGerando e validando a SQL…", style="dim")
            started = perf_counter()
            proposal = use_case.execute(request)
            elapsed = perf_counter() - started
            while True:
                _show_proposal(proposal, terminal)
                if proposal.validation.status != "approved" or executor is None:
                    terminal.line(f"Tempo de geração: {elapsed:.1f} s | SQL não executada.", style="dim")
                    break
                terminal.section("Confirmação")
                terminal.line(f"Destino da execução: {destination or proposal.connection_id}")
                confirmation = read("Executar exatamente esta SQL? Digite sim para confirmar > ")
                if confirmation.strip().casefold() not in {"sim", "s"}:
                    use_case.pending.invalidate_session(proposal.session_id)
                    terminal.line("Execução cancelada. Nenhuma consulta foi executada.", style="yellow")
                    break
                try:
                    result = executor.execute(ExecuteSqlRequest(proposal_id=proposal.id,
                        connection_id=proposal.connection_id, session_id=proposal.session_id, confirmed=True))
                    terminal.result(result)
                    break
                except ApplicationError as error:
                    show_error(error.code, error.message, terminal, demo=bool(demo_name))
                    if error.code in {"query_syntax_error", "query_resolution_error"} and proposal.attempt < 3:
                        terminal.line("Preparando uma proposta corrigida. Ela exigirá nova confirmação.", style="yellow")
                        proposal = use_case.correct(proposal, error)
                        continue
                    break
        except (EOFError, KeyboardInterrupt, StopIteration):
            _close_session(use_case)
            terminal.line("\nSessão encerrada.")
            return
        except ValidationError:
            show_error("invalid_input", "Informe uma pergunta com 1 a 2000 caracteres.", terminal)
        except ApplicationError as error:
            show_error(error.code, error.message, terminal, demo=bool(demo_name))
        except Exception:
            show_error("unexpected_error", "Não foi possível processar a pergunta.", terminal)


def select_profile(settings: Settings, read=input, write=print, *, terminal=None):
    terminal = terminal or Terminal(write=write)
    profiles = (
        ("deepseek", "DeepSeek (API própria)"),
        ("ollama", "Ollama local"),
        ("openai", "OpenAI (API própria)"),
    )
    terminal.section("Modelo de IA")
    for index, (provider, label) in enumerate(profiles, 1):
        terminal.line(f"  {index}. {label} · {settings.profile(provider).model}")
    choices = {str(index): provider for index, (provider, _) in enumerate(profiles, 1)}
    choices.update({provider: provider for provider, _ in profiles})
    terminal.line()
    while True:
        choice = read(f"Escolha o perfil [{settings.llm_provider}] ou sair > ").strip().lower()
        if choice == "sair":
            raise EOFError()
        provider = settings.llm_provider if not choice else choices.get(choice)
        if provider is not None:
            return settings.profile(provider)
        terminal.line("Escolha 1, 2 ou 3, ou informe o nome do provedor.", style="yellow")


def select_connection(cases, read, terminal):
    terminal.section("Conexões previamente cadastradas")
    for index, case in enumerate(cases, 1):
        connection = case.settings.connection
        terminal.line(f"  {index}. {case.name} · {connection.host}:{connection.port}/{connection.database}"
                      f" · usuário {connection.role}")
    choices = {str(index): case for index, case in enumerate(cases, 1)}
    choices.update({case.name.casefold(): case for case in cases})
    terminal.line()
    while True:
        choice = read("Escolha a conexão ou digite sair > ").strip().casefold()
        if choice == "sair":
            raise EOFError()
        case = choices.get(choice)
        if case is not None:
            return case
        terminal.line("Escolha 1, 2 ou 3, ou informe o nome da conexão.", style="yellow")


def run_demo(cases, profile, api_key, read, terminal):
    while True:
        case = select_connection(cases, read, terminal)
        try:
            generation, execution, path = build_cli_session(case.settings, profile=profile, api_key=api_key)
            check_demo_connection(case, generation.catalog)
            knowledge = generation.context_builder.knowledge
            if not knowledge.read(case.settings.connection.id).strip():
                raise ApplicationError("knowledge_unavailable", "Prepare os contextos com backend/demo/prepare.py.")
        except ApplicationError as error:
            terminal.line(f"\n[Conexão indisponível] {case.name} · {error.message}", style="bold red")
            terminal.line("Confira a preparação da demo ou selecione outra conexão.")
            continue
        result = run(generation, read=read, executor=execution, context_path=path,
                     destination=case.settings.connection.label, profile=profile, demo_name=case.name,
                     terminal=terminal)
        if result != "trocar":
            return


def main(*, read=input, write=print, ask_secret=None, demo=False, console=None):
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
    terminal = Terminal(write=write, console=console)
    try:
        cases = demo_connections(read_environment()) if demo else ()
        settings = cases[0].settings if demo else Settings.from_env()
        if demo:
            terminal.section("AskDB V0 · Demonstração")
            terminal.line("Jornada de consulta após o onboarding simulado da V1.")
        profile = select_profile(settings, read=read, terminal=terminal)
        api_key = None
        if profile.provider != "ollama":
            terminal.line("O provedor remoto recebe a pergunta, o esquema autorizado, o contexto e os pares de pergunta e SQL. "
                          "Os resultados ficam locais.", style="dim")
            api_key = read_api_key(profile.provider, ask_secret=ask_secret or hidden_key)
        if demo:
            run_demo(cases, profile, api_key, read, terminal)
        else:
            generation, execution, path = build_cli_session(settings, profile=profile, api_key=api_key)
            run(generation, read=read, executor=execution, context_path=path,
                destination=settings.connection.label, profile=profile, terminal=terminal)
    except (EOFError, KeyboardInterrupt):
        terminal.line("\nSessão encerrada.")
        return 0
    except ApplicationError as error:
        terminal.line(f"\n[Erro ao iniciar] {error.message}", style="bold red")
        terminal.line(f"Código: {error.code}")
        terminal.line("Confira a configuração e inicie a CLI novamente.")
        return 1
    return 0
