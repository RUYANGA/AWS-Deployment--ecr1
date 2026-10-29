#!/bin/sh
set -e

# Static files are collected at build time (see Dockerfile).
# Set RUN_MIGRATIONS=false when migrations run as a separate one-off task
# (e.g. an ECS task before deploy) so scaled-out containers don't race.
if [ "${RUN_MIGRATIONS:-true}" = "true" ]; then
    python manage.py migrate --noinput
fi

exec "$@"
