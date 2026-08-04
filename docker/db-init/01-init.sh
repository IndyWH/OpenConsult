#!/bin/bash
# First-run database init (DOCKER_DEMO_SPEC.md §§1.3, 1.5). Runs once,
# on an empty pg-data volume, as the Postgres superuser.
#
# Order matters: vector goes into template1 BEFORE consultation_ai is
# created, so the app database — and every database the app role creates
# later, including the disposable consultation_ai_test the suite builds
# and drops per session — inherits the extension. pgvector is untrusted,
# so template1 is the only route that gives the non-superuser app role a
# test database with vector in it; without both of these the suite does
# not degrade, it refuses (tests/conftest.py, by design).
set -euo pipefail

psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" <<-SQL
	CREATE ROLE consultation_app LOGIN
	  PASSWORD '${APP_DB_PASSWORD:-consultation_dev_password}'
	  CREATEDB;
SQL

psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d template1 \
    -c "CREATE EXTENSION IF NOT EXISTS vector;"

psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" \
    -c "CREATE DATABASE consultation_ai OWNER consultation_app;"

echo "[db-init] role consultation_app (CREATEDB), vector in template1," \
     "database consultation_ai created"
