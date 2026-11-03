from typing import Protocol

from pydantic import Field

from askdb.queries.models import DataModel


class Column(DataModel):
    name: str
    data_type: str
    nullable: bool


class ForeignKey(DataModel):
    columns: list[str]
    target_schema: str
    target_table: str
    target_columns: list[str]


class Table(DataModel):
    schema_name: str
    name: str
    columns: list[Column]
    primary_key: list[str] = Field(default_factory=list)
    foreign_keys: list[ForeignKey] = Field(default_factory=list)


class SchemaCatalog(DataModel):
    tables: list[Table]


class SchemaCatalogPort(Protocol):
    def discover(self) -> SchemaCatalog: ...
