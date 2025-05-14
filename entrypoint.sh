#!/bin/bash
set -e

while ! nc -z $POSTGRES_HOST $POSTGRES_PORT; do
    sleep 0.1
done

alembic upgrade heads

exec uvicorn app.main:app --host 0.0.0.0 --port 8000
