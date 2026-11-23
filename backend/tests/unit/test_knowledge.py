from pathlib import Path

import pytest

from askdb.bootstrap import prepare_knowledge
from askdb.connections.models import DBConnection
from askdb.knowledge.files import MAX_KNOWLEDGE_BYTES, MarkdownKnowledgeAdapter
from askdb.queries.errors import ApplicationError
from askdb.settings import Settings


def identity(role="reader"):
    return DBConnection.from_url(f"postgresql://{role}:p@localhost/demo").id


def test_prepare_and_read_survive_cwd_and_restart(tmp_path, monkeypatch):
    settings = Settings(database_url="postgresql://reader:p@localhost/demo", app_data_dir=tmp_path / "app")
    files = prepare_knowledge(settings)
    path = files.path(identity())
    assert path.parent.is_dir() and not path.exists()
    assert files.read(identity()) == ""
    content = "# Contexto\nVendas válidas excluem pedidos cancelados.\n"
    path.write_text(content, encoding="utf-8", newline="")
    monkeypatch.chdir(tmp_path)
    restarted = prepare_knowledge(settings)
    assert restarted.path(identity()) == path and restarted.read(identity()) == content
    assert not files.path(identity("other")).exists()
    assert path.read_text(encoding="utf-8") == content


@pytest.mark.parametrize("bad_id", ["../outside", "/absolute", "a" * 63, "a" * 64 + "/x"])
def test_reject_path_ids(tmp_path, bad_id):
    with pytest.raises(ApplicationError):
        MarkdownKnowledgeAdapter(tmp_path / "connections").prepare(bad_id)


def test_invalid_large_unreadable_and_no_fallback(tmp_path, monkeypatch):
    files = MarkdownKnowledgeAdapter(tmp_path / "connections")
    path = files.prepare(identity())
    path.write_bytes(b"\xff\xfe")
    with pytest.raises(ApplicationError, match="UTF-8"):
        files.read(identity())
    path.write_bytes(b"x" * (MAX_KNOWLEDGE_BYTES + 1))
    with pytest.raises(ApplicationError) as error:
        files.read(identity())
    assert error.value.code == "context_limit_exceeded"
    path.unlink()
    path.mkdir()
    with pytest.raises(ApplicationError):
        files.read(identity())
    monkeypatch.setattr(Path, "mkdir", lambda *a, **k: (_ for _ in ()).throw(PermissionError()))
    with pytest.raises(ApplicationError):
        files.prepare(identity("other"))


def test_symlink_escape(tmp_path):
    files = MarkdownKnowledgeAdapter(tmp_path / "connections")
    path = files.prepare(identity())
    outside = tmp_path / "outside.md"
    outside.write_text("private", encoding="utf-8")
    try:
        path.symlink_to(outside)
    except OSError:
        pytest.skip("O Windows exige privilégio para criar symlink; junctions são verificadas separadamente.")
    with pytest.raises(ApplicationError):
        files.read(identity())


def test_windows_junction_escape(tmp_path):
    import os
    import subprocess
    if os.name != "nt":
        pytest.skip("Junction é específica do Windows.")
    root = tmp_path / "connections"
    root.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    linked = root / identity()
    created = subprocess.run(["cmd", "/c", "mklink", "/J", str(linked), str(outside)], capture_output=True)
    assert created.returncode == 0
    with pytest.raises(ApplicationError):
        MarkdownKnowledgeAdapter(root).prepare(identity())
    assert not (outside / "context.md").exists()
