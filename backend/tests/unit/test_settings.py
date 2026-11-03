import pytest

from askdb.queries.errors import ApplicationError
from askdb.settings import Settings


def test_defaults_and_overrides():
    settings = Settings.from_env({"DATABASE_URL": "postgresql://user:secret@localhost/db"})
    assert settings.ollama_model == "qwen3.5:9b"
    assert settings.ollama_url == "http://127.0.0.1:11434"
    assert "secret" not in repr(settings)
    changed = Settings.from_env({"DATABASE_URL": "postgresql://user:secret@localhost/db",
                                 "OLLAMA_MODEL": "outro", "LLM_TIMEOUT": "30"})
    assert changed.ollama_model == "outro" and changed.llm_timeout == 30


@pytest.mark.parametrize("environ", [{}, {"DATABASE_URL": "segredo"},
    {"DATABASE_URL": "postgresql://u:segredo@localhost/db", "LLM_TIMEOUT": "0"},
    {"DATABASE_URL": "postgresql://u:segredo@localhost/db", "OLLAMA_URL": "http://u:segredo@localhost"}])
def test_invalid_settings_safe(environ):
    with pytest.raises(ApplicationError) as error:
        Settings.from_env(environ)
    assert error.value.code == "configuration_error"
    assert "segredo" not in str(error.value)


def test_dotenv_and_terminal_precedence(tmp_path, monkeypatch):
    import os
    path = tmp_path / ".env"
    path.write_text("DATABASE_URL=postgresql://u:dev@localhost/db\nOLLAMA_MODEL=arquivo\n", encoding="utf-8")
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("OLLAMA_MODEL", raising=False)
    assert Settings.from_env(env_file=path).ollama_model == "arquivo"
    assert "DATABASE_URL" not in os.environ
    monkeypatch.setenv("OLLAMA_MODEL", "terminal")
    assert Settings.from_env(env_file=path).ollama_model == "terminal"
    with pytest.raises(ApplicationError):
        Settings.from_env({}, env_file=path)


def test_file_location_independent_of_terminal(tmp_path, monkeypatch):
    from askdb.settings import ENV_FILE
    monkeypatch.chdir(tmp_path)
    assert ENV_FILE.is_absolute() and ENV_FILE.parent.name == "backend"


def test_missing_or_unreadable_file(tmp_path, monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    for path in (tmp_path / "ausente", tmp_path):
        with pytest.raises(ApplicationError):
            Settings.from_env(env_file=path)
