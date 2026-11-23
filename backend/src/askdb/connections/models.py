import hashlib
import json
from urllib.parse import parse_qs, unquote, urlsplit
from pydantic import Field

from askdb.queries.errors import ApplicationError
from askdb.queries.models import DataModel


class DBConnection(DataModel):
    host: str = Field(min_length=1)
    port: int = Field(ge=1, le=65535)
    database: str = Field(min_length=1)
    role: str = Field(min_length=1)

    @property
    def id(self) -> str:
        identity = json.dumps([self.host.lower(), self.port, self.database, self.role])
        return hashlib.sha256(identity.encode("utf-8")).hexdigest()

    @property
    def label(self) -> str:
        return f"{self.host}:{self.port}/{self.database} (role {self.role})"

    @classmethod
    def from_url(cls, url: str):
        try:
            value = urlsplit(url)
            query = parse_qs(value.query)
            if (value.scheme not in {"postgres", "postgresql"} or not value.hostname
                    or not value.username or not value.path.strip("/")
                    or set(query) - {"sslmode", "sslrootcert", "sslcert", "sslkey", "application_name"}
                    or value.fragment):
                raise ValueError()
            return cls(host=value.hostname.lower(), port=value.port if value.port is not None else 5432,
                       database=unquote(value.path[1:]), role=unquote(value.username))
        except (ValueError, TypeError):
            raise ApplicationError("configuration_error", "Confira a conexão PostgreSQL e sua role explícita.") from None
