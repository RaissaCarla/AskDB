import psycopg
from psycopg.rows import dict_row, tuple_row
import time
from uuid import uuid4

from askdb.connections.models import DBConnection
from askdb.databases.catalog import Column, ForeignKey, SchemaCatalog, Table
from askdb.queries.errors import ApplicationError
from askdb.queries.models import QueryResult


class PostgresDatabaseAdapter:
    def __init__(self, database_url: str, *, max_rows: int = 100, statement_timeout_ms: int = 30000):
        self._database_url = database_url
        if not 1 <= max_rows <= 1000 or not 1 <= statement_timeout_ms <= 30000:
            raise ApplicationError("configuration_error", "Confira os limites de execução.")
        self.max_rows = max_rows
        self.statement_timeout_ms = statement_timeout_ms
        try:
            self.identity = DBConnection.from_url(database_url)
        except ApplicationError:
            self.identity = None

    def _check_role(self, connection):
        role = connection.execute(
            "SELECT rolsuper, rolbypassrls, current_user AS effective_role, "
            "current_database() AS effective_database FROM pg_roles WHERE rolname = current_user"
        ).fetchone()
        if not role or role["rolsuper"] or role["rolbypassrls"]:
            raise ApplicationError("configuration_error", "Use uma role sem superusuário ou BYPASSRLS.")
        if self.identity is not None and (role.get("effective_role") != self.identity.role
                or role.get("effective_database") != self.identity.database):
            raise ApplicationError("connection_mismatch", "A identidade efetiva diverge da conexão configurada.")

    def discover(self) -> SchemaCatalog:
        try:
            with psycopg.connect(self._database_url, connect_timeout=10,
                                 options="-c statement_timeout=10000 -c default_transaction_read_only=on -c search_path=pg_catalog,public",
                                 row_factory=dict_row) as connection:
                self._check_role(connection)
                rows = connection.execute("""
                    SELECT c.oid, n.nspname, c.relname, a.attnum, a.attname,
                           format_type(a.atttypid,a.atttypmod) AS data_type,
                           NOT a.attnotnull AS nullable
                    FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
                    JOIN pg_attribute a ON a.attrelid=c.oid
                    WHERE c.relkind IN ('r','p') AND a.attnum>0 AND NOT a.attisdropped
                      AND n.nspname NOT LIKE 'pg_%' AND n.nspname <> 'information_schema'
                      AND has_schema_privilege(n.oid,'USAGE')
                      AND has_column_privilege(c.oid,a.attnum,'SELECT')
                    ORDER BY n.nspname,c.relname,a.attnum
                """).fetchall()
                tables = {}
                columns = {}
                for row in rows:
                    oid = row["oid"]
                    if oid not in tables:
                        tables[oid] = Table(schema_name=row["nspname"], name=row["relname"], columns=[])
                        columns[oid] = {}
                    columns[oid][row["attnum"]] = row["attname"]
                    tables[oid].columns.append(Column(name=row["attname"], data_type=row["data_type"],
                                                     nullable=row["nullable"]))
                constraints = connection.execute("""
                    SELECT conrelid,confrelid,contype,conkey,confkey
                    FROM pg_constraint WHERE contype IN ('p','f') ORDER BY conname
                """).fetchall()
                for item in constraints:
                    origin = item["conrelid"]
                    keys = item["conkey"]
                    if origin not in tables or not all(k in columns[origin] for k in keys):
                        continue
                    names = [columns[origin][k] for k in keys]
                    if item["contype"] == "p":
                        tables[origin].primary_key = names
                        continue
                    target = item["confrelid"]
                    targets = item["confkey"]
                    if target not in tables or not all(k in columns[target] for k in targets):
                        continue
                    tables[origin].foreign_keys.append(ForeignKey(columns=names,
                        target_schema=tables[target].schema_name, target_table=tables[target].name,
                        target_columns=[columns[target][k] for k in targets]))
                return SchemaCatalog(tables=list(tables.values()))
        except ApplicationError:
            raise
        except psycopg.Error:
            raise ApplicationError("database_unavailable", "Não foi possível descobrir o esquema PostgreSQL.") from None

    def execute(self, connection_id: str, sql: str) -> QueryResult:
        if self.identity is None or connection_id != self.identity.id:
            raise ApplicationError("connection_mismatch", "O executor está vinculado a outra conexão.")
        started = time.monotonic()
        connection = None
        try:
            connection = psycopg.connect(self._database_url, connect_timeout=10, row_factory=dict_row,
                options=f"-c default_transaction_read_only=on -c statement_timeout={self.statement_timeout_ms} "
                        "-c lock_timeout=5000 -c search_path=pg_catalog,public")
            connection.execute("SET TRANSACTION READ ONLY")
            self._check_role(connection)
            with connection.cursor(name="askdb_" + uuid4().hex, row_factory=tuple_row) as cursor:
                cursor.execute(sql)
                rows = cursor.fetchmany(self.max_rows + 1)
                columns = [item.name for item in cursor.description]
            return QueryResult(columns=columns, rows=rows[:self.max_rows],
                               truncated=len(rows) > self.max_rows,
                               duration_ms=round((time.monotonic() - started) * 1000, 3))
        except ApplicationError:
            raise
        except psycopg.errors.QueryCanceled:
            raise ApplicationError("query_timeout", "A consulta foi cancelada ou excedeu o tempo limite.") from None
        except psycopg.errors.InsufficientPrivilege:
            raise ApplicationError("query_permission_denied", "A role não pode realizar essa consulta.") from None
        except (psycopg.errors.UndefinedColumn, psycopg.errors.UndefinedTable):
            raise ApplicationError("query_resolution_error", "A consulta referencia tabela ou coluna não disponível.") from None
        except psycopg.errors.SyntaxError:
            raise ApplicationError("query_syntax_error", "A consulta contém um erro de sintaxe PostgreSQL.") from None
        except psycopg.OperationalError:
            raise ApplicationError("database_unavailable", "O PostgreSQL não está disponível para concluir a consulta.") from None
        except psycopg.Error:
            raise ApplicationError("query_failed", "Não foi possível concluir a consulta com segurança.") from None
        finally:
            if connection is not None:
                try:
                    connection.rollback()
                except psycopg.Error:
                    pass
                finally:
                    connection.close()
