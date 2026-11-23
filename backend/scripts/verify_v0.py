"""Verifica a V0 em um PostgreSQL Docker exclusivo, sem modificar bancos existentes."""
import argparse
import os
from pathlib import Path
import secrets
import socket
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--demo-provider", choices=["deepseek", "ollama", "openai"])
    parser.add_argument("--real-provider", choices=["deepseek", "ollama", "openai"])
    args = parser.parse_args()
    project = "askdb-v0-test-" + secrets.token_hex(4)
    admin_password, reader_password = secrets.token_urlsafe(24), secrets.token_urlsafe(24)
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    env = {**os.environ, "ASKDB_ADMIN_PASSWORD": admin_password, "ASKDB_READER_PASSWORD": reader_password,
           "ASKDB_POSTGRES_PORT": str(port), "PYTHONIOENCODING": "utf-8"}
    url = f"postgresql://askdb_reader:{reader_password}@127.0.0.1:{port}/askdb"
    env.update(DATABASE_URL=url, ASKDB_TEST_DATABASE_URL=url,
               ASKDB_TEST_ADMIN_URL=f"postgresql://postgres:{admin_password}@127.0.0.1:{port}/askdb")
    # O teste real é opt-in; configuração externa não deve ativá-lo por acidente.
    env.pop("ASKDB_REAL_LLM_PROVIDER", None)
    if args.real_provider:
        env["ASKDB_REAL_LLM_PROVIDER"] = args.real_provider
    compose = ["docker", "compose", "-p", project, "-f", str(ROOT / "backend/compose.yaml")]
    hidden = [admin_password, reader_password] + [v for k,v in env.items() if k in {"DEEPSEEK_API_KEY", "OPENAI_API_KEY"} and v]

    def run(command):
        result = subprocess.run(command, cwd=ROOT, env=env, capture_output=True, encoding="utf-8", errors="replace")
        output = result.stdout + result.stderr
        for value in hidden:
            output = output.replace(value, "[oculto]")
        print(output, end="", flush=True)
        return result.returncode

    print(f"Projeto Docker temporário: {project}; porta {port}. Nenhum volume existente será reutilizado.", flush=True)
    try:
        if run(compose + ["up", "-d", "--wait", "--wait-timeout", "90"]) != 0:
            return 1
        with tempfile.TemporaryDirectory(prefix="askdb-v0-verificacao-") as temp:
            env["ASKDB_APP_DATA_DIR"] = str(Path(temp) / "app")
            if args.demo_provider:
                # O exemplo sintético é preparado explicitamente pelo roteiro, nunca pelo adaptador.
                from askdb.settings import Settings
                settings = Settings.from_env(env)
                context = Path(env["ASKDB_APP_DATA_DIR"]) / "connections" / settings.connection.id / "context.md"
                context.parent.mkdir(parents=True)
                context.write_bytes((ROOT / "backend/examples/context.md").read_bytes())
                env["LLM_PROVIDER"] = args.demo_provider
                print("Demonstração interativa com dados e contexto sintéticos. Digite sair para finalizar.", flush=True)
                return subprocess.run([sys.executable, "-m", "askdb.entrypoints.cli"], cwd=ROOT, env=env).returncode
            tests = ["backend/tests/integration/test_real_llm.py", "-s"] if args.real_provider else ["backend/tests"]
            return run([sys.executable, "-m", "pytest", *tests, "-q"])
    finally:
        # Nome gerado nesta execução: a limpeza não alcança outros projetos/volumes.
        if project.startswith("askdb-v0-test-") and len(project) == len("askdb-v0-test-") + 8:
            run(compose + ["down", "--volumes", "--remove-orphans"])


if __name__ == "__main__":
    raise SystemExit(main())
