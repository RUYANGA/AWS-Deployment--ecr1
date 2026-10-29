# Logistic API

Django REST API with PostgreSQL, JWT authentication and Swagger documentation.

## Stack
- Django 5.2 · Django REST Framework
- PostgreSQL (psycopg 3)
- JWT auth (SimpleJWT, rotating refresh tokens + blacklist)
- OpenAPI 3 docs (drf-spectacular: Swagger UI & ReDoc)

## Project structure
```
.
├── src/                     # All application source code
│   ├── apps/
│   │   ├── accounts/        # Custom User model (email login), auth endpoints
│   │   │   ├── admin/
│   │   │   │   └── user_admin.py
│   │   │   ├── api/
│   │   │   │   ├── serializers/
│   │   │   │   │   ├── auth.py      # register / login / logout
│   │   │   │   │   ├── password.py  # change password
│   │   │   │   │   ├── token.py     # token response schema
│   │   │   │   │   └── user.py      # user profile
│   │   │   │   ├── throttles/
│   │   │   │   │   └── auth.py
│   │   │   │   ├── views/
│   │   │   │   │   ├── auth.py
│   │   │   │   │   └── profile.py
│   │   │   │   └── urls.py
│   │   │   ├── managers/
│   │   │   │   └── user_manager.py
│   │   │   ├── migrations/
│   │   │   ├── models/
│   │   │   │   └── user.py
│   │   │   ├── tests/
│   │   │   │   └── api/test_auth.py
│   │   │   ├── utils/
│   │   │   │   └── tokens.py    # JWT helpers
│   │   │   └── apps.py
│   │   └── core/            # Shared utilities, health check
│   ├── config/
│   │   ├── settings/
│   │   │   ├── base.py      # Shared settings
│   │   │   ├── dev.py       # Local development
│   │   │   ├── prod.py      # Production (security hardening)
│   │   │   └── test.py      # Test runner
│   │   ├── urls.py
│   │   ├── wsgi.py
│   │   └── asgi.py
├── manage.py
├── requirements/            # base / dev / prod
├── scripts/entrypoint.sh
├── Dockerfile
├── docker-compose.yml            # base (production-like) stack
├── docker-compose.override.yml   # development overrides (auto-loaded)
├── .env.example
└── README.md
```

## Getting started

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements/dev.txt
cp .env.example .env          # then set your PostgreSQL credentials

createdb -h localhost -U postgres logistic_db   # once
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

### Docker Compose

| Mode | Command | Runs |
|---|---|---|
| Development | `docker compose up --build` | `runserver` with auto-reload, `src/` mounted, dev settings |
| Production-like | `docker compose -f docker-compose.yml up --build` | gunicorn, prod settings, exactly the image you ship |

Services: `migrate` (one-off, applies migrations) → `web` (starts only after migrations succeed).
`web` has a healthcheck, restart policy, CPU/memory limits, log rotation and is hardened
(read-only filesystem, non-root, no Linux capabilities, `no-new-privileges`).

Containers read `.env` as-is and use the **host network**, so the database settings in
`.env` (`POSTGRES_HOST=localhost`, …) work unchanged and the app listens on
`127.0.0.1:$WEB_PORT`. Host networking requires Docker Engine on Linux.
Optional variables: `WEB_PORT`, `IMAGE_NAME`, `IMAGE_TAG`.

### Docker image
Multi-stage build (`base` → `builder` → `runtime`): dependencies are installed with
[uv](https://github.com/astral-sh/uv) into a virtualenv using a BuildKit cache, and only that
virtualenv, the source code and pre-collected static files reach the final non-root image.

```bash
docker build -t logistic-api .
docker run --env-file .env -p 8000:8000 logistic-api
```

| Runtime variable | Default | Purpose |
|---|---|---|
| `RUN_MIGRATIONS` | `true` | Run `migrate` on start. Set `false` when migrations run as a separate task (e.g. ECS) |
| `GUNICORN_CMD_ARGS` | – | Extra gunicorn options, e.g. `--workers 4 --timeout 60` |

## API docs
- Swagger UI: http://localhost:8000/api/v1/docs/
- ReDoc: http://localhost:8000/api/v1/redoc/
- OpenAPI schema: http://localhost:8000/api/v1/schema/

Docs are only served when `ENABLE_API_DOCS=True` in `.env` (off by default — keep it `False` in production).

In Swagger, call **login**, copy `tokens.access`, click **Authorize** and paste it.

## Endpoints (`/api/v1/`)

| Method | Path | Auth | Description |
|---|---|---|---|
| POST | `auth/register/` | – | Create account, returns user + tokens |
| POST | `auth/login/` | – | Email/password login, returns user + tokens |
| POST | `auth/token/refresh/` | – | Exchange refresh token for new access token |
| POST | `auth/logout/` | Bearer | Blacklist refresh token |
| GET/PATCH | `auth/me/` | Bearer | View / update own profile |
| POST | `auth/change-password/` | Bearer | Change password |
| GET | `health/` | – | Service + database health check |

## Tests
```bash
python manage.py test apps --settings=config.settings.test
```

## Contributing
Rules live in [.claude/CLAUDE.md](.claude/CLAUDE.md) and are enforced by
[.claude/hooks/git_guard.py](.claude/hooks/git_guard.py):

- Conventional Commits (`feat:`, `fix:`, `chore:` …), branches `feat/<topic>` etc.
- Pull requests change **at most 10 files**; larger work is split into stacked PRs.
- No AI attribution in commits or PRs.
- `manage.py check` and the test suite must pass before commit and push.
