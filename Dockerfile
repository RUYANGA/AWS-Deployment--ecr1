# syntax=docker/dockerfile:1.7
#
# Multi-stage build:
#   base     -> shared Python runtime settings
#   builder  -> resolves and installs dependencies into /opt/venv (uv, cached)
#   runtime  -> slim final image: venv + app code + collected static files
#
# Build:  docker build -t logistic-api .
# Run:    docker run --env-file .env -p 8000:8000 logistic-api

ARG PYTHON_VERSION=3.12

# ---------------------------------------------------------------- base
FROM python:${PYTHON_VERSION}-slim-bookworm AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# ---------------------------------------------------------------- builder
FROM base AS builder

# uv installs packages 10-100x faster than pip.
COPY --from=ghcr.io/astral-sh/uv:0.5.11 /uv /usr/local/bin/uv

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never

RUN uv venv /opt/venv

# Only the requirement files are copied here, so this layer is rebuilt
# when dependencies change, not on every code change.
COPY requirements/ requirements/
RUN --mount=type=cache,target=/root/.cache/uv \
    uv pip install --python /opt/venv/bin/python -r requirements/prod.txt \
    # Translation sources (.po) are not used at runtime; compiled .mo files stay.
    && find /opt/venv -name '*.po' -delete

# ---------------------------------------------------------------- runtime
FROM base AS runtime

ENV PATH="/opt/venv/bin:$PATH" \
    DJANGO_SETTINGS_MODULE=config.settings.prod

RUN groupadd --system app \
    && useradd --system --gid app --home-dir /app --no-create-home app \
    && install -d -o app -g app /app/staticfiles /app/media

COPY --from=builder /opt/venv /opt/venv
COPY --chown=app:app manage.py ./
COPY --chown=app:app scripts/entrypoint.sh scripts/entrypoint.sh
COPY --chown=app:app src/ src/

USER app

# Collect static files at build time so containers start instantly.
# Placeholder values only satisfy settings import; nothing connects to a DB.
RUN SECRET_KEY=collectstatic-only \
    POSTGRES_DB=build POSTGRES_USER=build POSTGRES_PASSWORD=build \
    python manage.py collectstatic --noinput --verbosity 0

EXPOSE 8000

ENTRYPOINT ["scripts/entrypoint.sh"]
# Tune at runtime with GUNICORN_CMD_ARGS, e.g. "--workers 4 --timeout 60".
CMD ["gunicorn", "config.wsgi:application", \
     "--chdir", "src", \
     "--bind", "0.0.0.0:8000", \
     "--workers", "3", \
     "--access-logfile", "-"]
