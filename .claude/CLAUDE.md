# Project rules for Claude Code

Logistic API — Django 5 + DRF + PostgreSQL, JWT auth, Swagger docs.
Code lives in `src/` (`src/apps/*`, `src/config/*`); `manage.py` is at the repo root.

These rules are **mandatory**. The git-related ones are enforced automatically by
[`hooks/git_guard.py`](hooks/git_guard.py), which runs before every Bash command
and blocks `git commit`, `git push`, `git pull` and `gh pr create` when a rule is broken.

## 1. Authorship — no AI attribution

- Never add Claude / Anthropic as author, committer, co-author or contributor.
- No `Co-Authored-By: Claude …` trailer in commits.
- No "🤖 Generated with Claude Code" (or similar) line in PR titles, bodies or comments.
- Commits are authored by the configured git user only (`git config user.name/email`).
- Attribution is also disabled in [`settings.json`](settings.json) (`attribution.commit/pr = ""`).

## 2. Pull requests

- **A PR may change at most 10 files.** Larger work is split into a chain of
  small, stacked PRs (each PR's base is the previous PR's branch), merged in order.
- One logical change per PR; every PR must pass checks and tests on its own.
- Title follows Conventional Commits (see below). Body contains:
  `## Summary`, `## How to test`, and the merge order when stacked.
- Always write the title and body explicitly (no `gh pr create --fill`).

## 3. Commits

- Conventional Commits: `type(scope): summary` — types: `feat`, `fix`, `refactor`,
  `test`, `docs`, `chore`, `ci`, `perf`, `style`. Imperative mood, ≤ 72 chars.
- Google-style docstrings on every module, class and public function/method (enforced by
  ruff `D` rules; tests, migrations, package `__init__`, `Meta` and magic methods exempt).
  View and serializer docstrings are published in Swagger, so write them for API users.
- Small, focused commits. Never commit `.env` or other secrets, `.venv/`,
  `__pycache__/`, `staticfiles/`.

## 4. Branches

- Never commit directly to `main`; never force-push `main`/`master`.
- Branch names: `feat/<topic>`, `fix/<topic>`, `chore/<topic>`, `docs/<topic>`,
  `refactor/<topic>`, `test/<topic>`.

## 5. Checks before commit / push / pull

| Action | Checks |
|---|---|
| `git commit` | no attribution in message · no Claude identity · no staged `.env` · `manage.py check` · test suite |
| `git push`   | no attribution/Claude identity in any unpushed commit · no force-push to `main` · `manage.py check` · test suite |
| `git pull`   | working tree must be clean (commit or stash first) |
| `gh pr create` | ≤ 10 changed files vs base · no attribution in title/body · no `--fill` |

The test suite needs the local PostgreSQL configured in `.env` to be running.

## Commands

```bash
source .venv/bin/activate
python manage.py runserver 8001                               # dev server
python manage.py test apps --settings=config.settings.test    # tests
python manage.py makemigrations && python manage.py migrate   # DB changes
pre-commit run --all-files                                    # format, lint, security
```

CI (`.github/workflows/ci.yml`) runs the same hooks, the tests and a Docker smoke test on every PR.
Code must pass the pre-commit hooks (ruff, ruff-format, flake8, bandit, django-upgrade,
shellcheck, hadolint, Django checks) before it is committed; line length is 100.
