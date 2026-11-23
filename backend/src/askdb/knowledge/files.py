import re
from pathlib import Path
from typing import Protocol

from askdb.queries.errors import ApplicationError

MAX_KNOWLEDGE_BYTES = 131072


class KnowledgeFilePort(Protocol):
    def read(self, connection_id: str) -> str: ...


class MarkdownKnowledgeAdapter:
    def __init__(self, connections_root: Path):
        self.root = Path(connections_root)

    def path(self, connection_id: str) -> Path:
        try:
            if not self.root.is_absolute() or not re.fullmatch(r"[a-f0-9]{64}", connection_id):
                raise ValueError()
            base = self.root.parent.resolve()
            # A raiz connections e os filhos não podem redirecionar para outra conexão/pasta.
            expected_root = base / self.root.name
            directory = expected_root / connection_id
            target = directory / "context.md"
            if (self.root.resolve() != expected_root
                    or directory.resolve() != directory
                    or target.resolve() != target):
                raise ValueError()
            return target
        except (OSError, ValueError, RuntimeError):
            raise ApplicationError("knowledge_unavailable", "O caminho do contexto não pertence à pasta autorizada.") from None

    def prepare(self, connection_id: str) -> Path:
        try:
            path = self.path(connection_id)
            path.parent.mkdir(parents=True, exist_ok=True)
            return self.path(connection_id)
        except OSError:
            raise ApplicationError("knowledge_unavailable", "Não foi possível preparar a pasta de contexto do aplicativo.") from None

    def read(self, connection_id: str) -> str:
        path = self.path(connection_id)
        try:
            with path.open("rb") as stream:
                body = stream.read(MAX_KNOWLEDGE_BYTES + 1)
            if len(body) > MAX_KNOWLEDGE_BYTES:
                raise ApplicationError("context_limit_exceeded", "O arquivo de contexto excede o limite de leitura.")
            return body.decode("utf-8-sig")
        except FileNotFoundError:
            return ""
        except (OSError, UnicodeError):
            raise ApplicationError("knowledge_unavailable", "Não foi possível ler o arquivo de contexto em UTF-8.") from None
