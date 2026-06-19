#!/bin/bash
set -e

# Crear la base de datos para InvenioRDM
# (Asumimos que la de DSpace se crea automáticamente con POSTGRES_DB)
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    CREATE DATABASE inveniodb;
    GRANT ALL PRIVILEGES ON DATABASE inveniodb TO $POSTGRES_USER;
EOSQL