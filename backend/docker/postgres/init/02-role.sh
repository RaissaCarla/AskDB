#!/bin/sh
set -eu
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
    --set=reader_password="$ASKDB_READER_PASSWORD" <<'SQL'
CREATE ROLE askdb_reader LOGIN PASSWORD :'reader_password' NOSUPERUSER NOBYPASSRLS;
GRANT CONNECT ON DATABASE askdb TO askdb_reader;
GRANT USAGE ON SCHEMA public TO askdb_reader;
GRANT SELECT ON clientes, produtos, pedidos, itens_pedido, referencia_restrita,
    chave_composta, referencia_composta TO askdb_reader;
GRANT SELECT (id, publico) ON parcial TO askdb_reader;
SQL
