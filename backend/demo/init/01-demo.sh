#!/bin/sh
# O Postgres pode carregar este arquivo no shell do entrypoint.
(
    set -eu
    psql -X --username "$POSTGRES_USER" --dbname postgres --set ON_ERROR_STOP=on <<'SQL'
\getenv reader_password ASKDB_READER_PASSWORD
CREATE ROLE askdb_reader LOGIN PASSWORD :'reader_password' NOSUPERUSER NOBYPASSRLS;
CREATE DATABASE demo_vendas;
CREATE DATABASE demo_suporte;
CREATE DATABASE demo_estoque;
SQL

    for caso in vendas suporte estoque; do
        psql -X --username "$POSTGRES_USER" --dbname "demo_${caso}" \
            --set ON_ERROR_STOP=on --single-transaction \
            --file "/docker-entrypoint-initdb.d/casos/${caso}.sql" --file "/docker-entrypoint-initdb.d/casos/leitura.sql"
    done
)
