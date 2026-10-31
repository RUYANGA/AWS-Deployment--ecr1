# Logistic API

[![CI](https://github.com/RUYANGA/AWS-Deployment--ecr1/actions/workflows/ci.yml/badge.svg?event=pull_request)](https://github.com/RUYANGA/AWS-Deployment--ecr1/actions/workflows/ci.yml)
[![Push to ECR](https://github.com/RUYANGA/AWS-Deployment--ecr1/actions/workflows/ecr.yml/badge.svg?branch=main)](https://github.com/RUYANGA/AWS-Deployment--ecr1/actions/workflows/ecr.yml)

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
├── docker-compose.yml   # runs the production image locally
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

`docker compose up --build` runs the app exactly as in production: gunicorn,
`config.settings.prod` and the same image that is pushed to ECR. For day-to-day
development with auto-reload, use `python manage.py runserver`.

Services: `migrate` (one-off, applies migrations) → `web` (starts only after migrations succeed).
`web` has a healthcheck, restart policy, CPU/memory limits, log rotation and is hardened
(read-only filesystem, non-root, no Linux capabilities, `no-new-privileges`).

The `db` service runs PostgreSQL with data persisted in the named `postgres_data` volume.
The `migrate` and `web` services connect to it using the Compose hostname `db`, and the
app is published on `localhost:$WEB_PORT`. Optional variables: `WEB_PORT`, `IMAGE_NAME`,
`IMAGE_TAG`.

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

## Deploy to EC2

```
Internet -HTTPS-> ALB (ACM certificate) -HTTP:8000-> EC2 (Docker) -> RDS PostgreSQL
                                                       ^ image from ECR
```

**1. Push the image to ECR** (from your machine):
```bash
REPO=<account-id>.dkr.ecr.<region>.amazonaws.com/logistic-api
aws ecr get-login-password --region <region> | docker login --username AWS --password-stdin ${REPO%/*}
docker build --platform linux/amd64 -t $REPO:1.0.0 . && docker push $REPO:1.0.0
```

**2. Prepare the instance** (Amazon Linux 2023, instance role with
`AmazonEC2ContainerRegistryReadOnly` + `AmazonSSMManagedInstanceCore`):
```bash
sudo dnf install -y docker && sudo systemctl enable --now docker
sudo mkdir -p /opt/logistic && sudo cp .env.production /opt/logistic/.env && sudo chmod 600 /opt/logistic/.env
```
The production `.env` sets `DJANGO_SETTINGS_MODULE=config.settings.prod`, `DEBUG=False`,
`ALLOWED_HOSTS=<your domain>`, `ENABLE_API_DOCS=False`, a new `SECRET_KEY` and the RDS
`POSTGRES_*` values.

**3. Deploy / update** (on the instance):
```bash
REPO=<account-id>.dkr.ecr.<region>.amazonaws.com/logistic-api
aws ecr get-login-password --region <region> | docker login --username AWS --password-stdin ${REPO%/*}
docker pull $REPO:1.0.0

# migrations once (RUN_MIGRATIONS=false stops the entrypoint from migrating a second time)
docker run --rm --env-file /opt/logistic/.env -e RUN_MIGRATIONS=false $REPO:1.0.0 \
  python manage.py migrate --noinput

docker rm -f logistic-api 2>/dev/null
docker run -d --name logistic-api --restart unless-stopped \
  --env-file /opt/logistic/.env -e RUN_MIGRATIONS=false -p 8000:8000 $REPO:1.0.0
```

**4. Load balancer:** target group HTTP:8000 with health check path `/api/v1/health/`;
ALB listener HTTPS:443 with an ACM certificate, HTTP:80 redirecting to 443.
The health endpoint is answered by `HealthCheckMiddleware` before host validation and the
HTTPS redirect, so ALB checks on the instance's private IP over HTTP succeed while every
other path still enforces `ALLOWED_HOSTS` and HTTPS.

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
| GET | `users/` | Staff | List users (paginated; `?search=`, `?is_active=`, `?is_staff=`, `?ordering=`) |
| POST | `users/` | Staff | Create a user |
| GET / PATCH / DELETE | `users/{id}/` | Staff | Get / update / delete a user |
| POST | `users/{id}/activate/` · `users/{id}/deactivate/` | Staff | Enable / disable an account (tokens stop working immediately) |
| POST | `users/{id}/set-password/` | Staff | Set a user's password |
| GET | `health/` | – | Service + database health check |

## Tests
```bash
python manage.py test apps --settings=config.settings.test
```

## Code quality
[pre-commit](https://pre-commit.com) runs on every `git commit`:

| Hook | Checks |
|---|---|
| **ruff** / **ruff-format** | lint (pycodestyle, pyflakes, isort, bugbear, pyupgrade, simplify, Django, **Google-style docstrings**) + Black-style formatting |
| **flake8** | pycodestyle, pyflakes and complexity (max 10) |
| **django-upgrade** | modern Django 5.2 APIs |
| **bandit** | security issues |
| **shellcheck** / **hadolint** | shell scripts and Dockerfile |
| **django check** / **missing migrations** | `manage.py check`, `makemigrations --check` |
| pre-commit-hooks | whitespace, EOF, YAML/JSON/TOML syntax, merge conflicts, private keys, large files, no direct commits to `main` |

```bash
pip install -r requirements/dev.txt
pre-commit install            # once per clone
pre-commit run --all-files    # run everything manually
```
Settings live in `pyproject.toml` (ruff, bandit) and `.flake8`; line length is 100.

## Continuous integration
Two workflows, so nothing runs twice:

| Workflow | Trigger | Jobs |
|---|---|---|
| [`ci.yml`](.github/workflows/ci.yml) | every **pull request** | **Lint & format** · **Tests** · **Docker build & smoke test** |
| [`ecr.yml`](.github/workflows/ecr.yml) | **merge to `main`** (or manual run on `main`) | **Push image to ECR** only |

| Job | What it does |
|---|---|
| **Lint & format** | all pre-commit hooks (ruff, flake8, bandit, django-upgrade, shellcheck, hadolint, Django checks) |
| **Tests** | missing-migration check + test suite against a PostgreSQL 16 service |
| **Docker build & smoke test** | builds the `runtime` image (BuildKit cache), runs migrations, starts gunicorn, waits for `/api/v1/health/`, verifies the container runs as UID 10001 |
| **Push image to ECR** | assumes `AWS_ROLE_ARN` via GitHub OIDC (no access keys) and pushes one plain image tagged `backend/logistic:<commit-sha>` and `:latest`; skipped if that commit is already in ECR; saves the build cache for later PRs |

The checks are not repeated after merging, so the PR must be tested against the latest
`main`. Enable branch protection on `main` (*Settings → Branches*) with **Require status
checks to pass** (the three CI jobs) and **Require branches to be up to date before
merging**. Superseded PR runs are cancelled; ECR publishes are never cancelled.

The ECR job needs two **repository variables** (*Settings → Secrets and variables → Actions →
Variables*): `AWS_ROLE_ARN` (IAM role trusted for `repo:<owner>/<repo>:ref:refs/heads/main`
through the `token.actions.githubusercontent.com` OIDC provider, allowed to push to the
repository) and `AWS_REGION`.

**ECR repository settings** (`backend/logistic` in `eu-west-1`): tag mutability is
**MUTABLE**, so `:latest` can move to each new build. Optional hardening, which keeps
commit-SHA tags locked while still letting `latest` move:
```bash
aws ecr put-image-tag-mutability --region eu-west-1 --repository-name backend/logistic \
  --image-tag-mutability IMMUTABLE_WITH_EXCLUSION \
  --image-tag-mutability-exclusion-filters filterType=WILDCARD,filter=latest
```

Lifecycle policy (one-time): delete untagged images after 1 day, keep the 20 most recent:
```bash
aws ecr put-lifecycle-policy --region eu-west-1 --repository-name backend/logistic \
  --lifecycle-policy-text file://infra/ecr/lifecycle-policy.json
```
Deploy a specific commit with `:<commit-sha>` (rollback = previous SHA); `:latest` is a
convenience pointer to the newest build.
Make the three checks required in *Settings → Branches → Branch protection* so a PR cannot be
merged while CI is red.

## Contributing
Rules live in [.claude/CLAUDE.md](.claude/CLAUDE.md) and are enforced by
[.claude/hooks/git_guard.py](.claude/hooks/git_guard.py):

- Conventional Commits (`feat:`, `fix:`, `chore:` …), branches `feat/<topic>` etc.
- Pull requests change **at most 10 files**; larger work is split into stacked PRs.
- No AI attribution in commits or PRs.
- `manage.py check` and the test suite must pass before commit and push.
