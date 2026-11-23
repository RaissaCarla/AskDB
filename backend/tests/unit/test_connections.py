from pathlib import Path

import pytest
from pydantic import ValidationError

from askdb.connections.models import DBConnection
from askdb.llm.models import LLMProfile
from askdb.queries.errors import ApplicationError
from askdb.settings import Settings


def test_identity_stable_without_secrets():
    first = DBConnection.from_url("postgresql://reader:password@LOCALHOST/demo")
    second = DBConnection.from_url("postgresql://reader:other@localhost:5432/demo")
    assert first.id == second.id and len(first.id) == 64
    assert first.id != DBConnection.from_url("postgresql://other:p@localhost/demo").id
    assert "password" not in repr(first)
    for url in ("invalid", "postgresql://u:p@localhost/demo?options=-crole%3Dadmin"):
        with pytest.raises(ApplicationError):
            DBConnection.from_url(url)


def test_app_data_dir_independent_of_cwd_and_user(tmp_path, monkeypatch):
    common = {"DATABASE_URL": "postgresql://u:p@localhost/demo"}
    user_a = {**common, "LOCALAPPDATA": str(tmp_path / "user_a")}
    user_b = {**common, "LOCALAPPDATA": str(tmp_path / "user_b")}
    first = Settings.from_env(user_a)
    monkeypatch.chdir(tmp_path)
    assert first.app_data_dir == Settings.from_env(user_a).app_data_dir
    assert first.app_data_dir != Settings.from_env(user_b).app_data_dir
    assert not first.app_data_dir.exists()
    assert Settings.from_env({**common, "ASKDB_APP_DATA_DIR": str(tmp_path / "test")}).app_data_dir == tmp_path / "test"
    with pytest.raises(ApplicationError):
        Settings.from_env({**common, "ASKDB_APP_DATA_DIR": "relative"})
    monkeypatch.delenv("LOCALAPPDATA", raising=False)
    monkeypatch.delenv("ASKDB_APP_DATA_DIR", raising=False)
    with pytest.raises(ApplicationError):
        Settings.from_env(common)


def test_profiles_keep_credentials_out(tmp_path):
    settings = Settings(database_url="postgresql://u:password@localhost/demo", app_data_dir=tmp_path)
    assert "password" not in repr(settings)
    assert settings.profile("deepseek").endpoint == "https://api.deepseek.com"
    assert "key" not in settings.profile("deepseek").model_dump()
    for endpoint in ("http://api.deepseek.com", "https://evil.invalid", "https://k:secret@api.deepseek.com"):
        with pytest.raises(ValidationError):
            LLMProfile(provider="deepseek", endpoint=endpoint, model="deepseek-flash")
    with pytest.raises(ValidationError):
        Settings(database_url="postgresql://u:p@localhost/demo", app_data_dir=Path("relative"))
