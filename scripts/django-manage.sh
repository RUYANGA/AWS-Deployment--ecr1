#!/bin/sh
# Run manage.py with the project's virtualenv when present (used by pre-commit hooks).
set -e
cd "$(dirname "$0")/.."
if [ -x .venv/bin/python ]; then
    PYTHON=.venv/bin/python
else
    PYTHON=python3
fi
exec "$PYTHON" manage.py "$@"
