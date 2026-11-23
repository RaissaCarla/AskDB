from typing import Protocol

from askdb.queries.models import QueryResult


class ReadOnlyQueryPort(Protocol):
    def execute(self, connection_id: str, sql: str) -> QueryResult: ...
