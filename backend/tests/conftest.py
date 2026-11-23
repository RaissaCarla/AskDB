import pytest


@pytest.fixture(autouse=True)
def isolated_app_data(tmp_path, monkeypatch):
    # Nenhum teste deve criar dados na pasta real do perfil do usuário.
    monkeypatch.setenv("ASKDB_APP_DATA_DIR", str(tmp_path / "app"))
