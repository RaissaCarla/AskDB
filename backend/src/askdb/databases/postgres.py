import psycopg
from psycopg.rows import dict_row

from askdb.databases.catalog import Column, ForeignKey, SchemaCatalog, Table
from askdb.queries.errors import ApplicationError


class PostgresDatabaseAdapter:
    def __init__(self, database_url: str):
        self._database_url = database_url

    def discover(self) -> SchemaCatalog:
        try:
            with psycopg.connect(self._database_url, connect_timeout=10,
                                 options="-c statement_timeout=10000 -c default_transaction_read_only=on",
                                 row_factory=dict_row) as connection:
                role = connection.execute(
                    "SELECT rolsuper, rolbypassrls FROM pg_roles WHERE rolname = current_user"
                ).fetchone()
                if not role or role["rolsuper"] or role["rolbypassrls"]:
                    raise ApplicationError("configuration_error", "Use uma role sem superusuário ou BYPASSRLS.")
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
