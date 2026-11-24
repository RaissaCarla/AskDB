"""Prepara o PostgreSQL e os contextos e abre a CLI de demonstração."""

import argparse
from hashlib import sha256
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory

from askdb.bootstrap import prepare_knowledge
from askdb.databases.postgres import PostgresDatabaseAdapter
from askdb.entrypoints.cli.demo import DemoConnection, check_demo_connection, demo_connections
from askdb.queries.errors import ApplicationError
from askdb.settings import read_environment


DEMO_DIR = Path(__file__).resolve().parent
ENV_FILE = DEMO_DIR.parent / ".env"

# Identifica os modelos distribuídos na primeira demo, sem substituir edições locais.
INITIAL_CONTEXT_HASHES = {
    "demo_estoque": "1facc6ae0fd36a978cfc9bf8fc10bf41ead2d84545269008828f039f98154f02",
    "demo_suporte": "88ccdebb3521d2ae1c5fdde0caa2a5e062f36131baf02211f39b9bad99265553",
    "demo_vendas": "fc7dc3236d84bcd26d46aa1435fda0d4739e0bb7240120fe7cc57b2e2d203bd1",
}


def prepare_demo_context(case: DemoConnection, templates: Path) -> Path:
    connection = case.settings.connection
    knowledge = prepare_knowledge(case.settings)
    path = knowledge.path(connection.id)
    try:
        existing = knowledge.read(connection.id)
        fingerprint = sha256(existing.strip().replace("\r\n", "\n").encode("utf-8")).hexdigest()
        is_initial_template = fingerprint == INITIAL_CONTEXT_HASHES[connection.database]
        if not path.exists() or is_initial_template:
            body = (templates / f"{connection.database}.md").read_bytes()
            # Publique o arquivo completo. Só substitua uma cópia do modelo inicial.
            with TemporaryDirectory(dir=path.parent) as staging:
                draft = Path(staging) / "context.md"
                draft.write_bytes(body)
                try:
                    if is_initial_template:
                        if knowledge.read(connection.id) == existing:
                            draft.replace(path)
                    else:
                        os.link(draft, path)
                except FileExistsError:
                    pass
        if not knowledge.read(connection.id).strip():
            raise ApplicationError("knowledge_unavailable", "Confira o conteúdo do context.md da conexão.")
    except OSError:
        raise ApplicationError("knowledge_unavailable", "Não foi possível copiar o Markdown da demo.") from None
    return path


def compose(*args, overrides: dict[str, str] | None = None) -> None:
    command = [
        "docker", "compose", "--project-name", "askdb-demo-v0",
        "--env-file", str(ENV_FILE), "--file", str(DEMO_DIR / "compose.yaml"), *args,
    ]
    env = {name: value for name, value in os.environ.items() if name not in {
        "DEEPSEEK_API_KEY", "OPENAI_API_KEY",
    }}
    if overrides:
        env.update(overrides)
    try:
        result = subprocess.run(command, capture_output=True, encoding="utf-8", errors="replace", env=env)
    except FileNotFoundError:
        raise ApplicationError("docker_unavailable", "Instale e abra o Docker Desktop com Docker Compose.") from None
    except OSError:
        raise ApplicationError("docker_unavailable", "Não foi possível iniciar o Docker Compose. Confira a instalação.") from None
    if result.returncode == 0:
        return

    details = result.stderr.casefold()
    if "port is already allocated" in details or "address already in use" in details or "ports are not available" in details:
        hint = "A porta da demo está ocupada. Altere ASKDB_DEMO_POSTGRES_PORT no backend/.env."
    elif any(message in details for message in ("docker_engine", "dockerdesktoplinuxengine", "docker daemon")):
        hint = "Abra o Docker Desktop e aguarde o motor de contêineres Linux ficar pronto."
    else:
        hint = ("Confira o Docker Desktop, as variáveis ASKDB_ADMIN_PASSWORD e ASKDB_READER_PASSWORD "
                "e o estado do projeto askdb-demo-v0. Consulte o guia em backend/demo/README.md.")
    raise ApplicationError("demo_compose_failed", hint)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    actions = parser.add_mutually_exclusive_group()
    actions.add_argument("--prepare-only", action="store_true", help="prepara os bancos e os contextos")
    actions.add_argument("--stop", action="store_true", help="para o projeto e preserva o volume")
    args = parser.parse_args()

    try:
        if not ENV_FILE.is_file():
            raise ApplicationError("configuration_error", "Crie backend/.env a partir de backend/.env.example.")
        if args.stop:
            compose("stop")
            print("PostgreSQL da demo parado. Volume preservado.")
            return 0

        source = read_environment(ENV_FILE)
        cases = demo_connections(source)
        if not source.get("ASKDB_ADMIN_PASSWORD"):
            raise ApplicationError("configuration_error", "Defina ASKDB_ADMIN_PASSWORD no backend/.env.")

        print("Preparando o PostgreSQL da demo…", flush=True)
        compose_env = {
            "ASKDB_DEMO_POSTGRES_PORT": str(cases[0].settings.connection.port),
            "ASKDB_ADMIN_PASSWORD": source["ASKDB_ADMIN_PASSWORD"],
            "ASKDB_READER_PASSWORD": source["ASKDB_READER_PASSWORD"],
        }
        compose("up", "-d", "--wait", "--wait-timeout", "90", overrides=compose_env)
        for case in cases:
            adapter = PostgresDatabaseAdapter(case.settings.database_url.get_secret_value())
            try:
                check_demo_connection(case, adapter)
            except ApplicationError as error:
                if error.code == "demo_schema_missing":
                    raise ApplicationError(error.code, (
                        f"{case.name}: {error.message} Se o volume estiver na primeira edição, "
                        "use um projeto Compose separado com a carga atual. O manual mostra os comandos."
                    )) from None
                raise ApplicationError("demo_connection_failed", (
                    f"{case.name}: confira a porta, a senha do usuário de leitura e a carga inicial. "
                    "Um volume existente mantém as credenciais e os dados da primeira inicialização."
                )) from None

        for case in cases:
            path = prepare_demo_context(case, DEMO_DIR / "contexts")
            print(f"Pronto · {case.name} ({case.settings.connection.database})")
            if args.prepare_only:
                print(f"  Contexto: {path}")

        if args.prepare_only:
            return 0
        sys.stdout.flush()
        return subprocess.call([sys.executable, "-X", "utf8", "-m", "askdb.entrypoints.cli", "--demo"])
    except ApplicationError as error:
        print(f"[{error.code}] {error.message}", file=sys.stderr)
        return 1
    except (OSError, UnicodeError):
        print("[Erro] Confira o acesso e o formato UTF-8 dos arquivos da demo.", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
