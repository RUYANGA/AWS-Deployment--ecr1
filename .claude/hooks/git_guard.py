#!/usr/bin/env python3
"""Pre-flight guard for git / GitHub commands run by Claude Code.

Runs as a PreToolUse hook on every Bash call. Commands that are not
`git commit`, `git push`, `git pull` or `gh pr create` pass straight through.

Rules enforced (see .claude/CLAUDE.md):
  1. No AI attribution: commit messages, PR titles/bodies, authors and
     committers must not credit Claude / Anthropic (no Co-Authored-By trailer,
     no "Generated with Claude Code" footer).
  2. Pull requests must change at most MAX_PR_FILES files.
  3. Quality gate before commit and push: `manage.py check` + test suite.
  4. Never commit secrets (.env files).
  5. `git pull` only on a clean working tree.
  6. No force-push to protected branches.

Exit code 2 blocks the command; the reasons are printed to stderr and shown
to Claude so it can fix the problem and retry.
"""
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

MAX_PR_FILES = 10
PROTECTED_BRANCHES = {"main", "master"}
DEFAULT_BASE = "main"

ATTRIBUTION_PATTERNS = [
    r"co-authored-by:.*(claude|anthropic)",
    r"noreply@anthropic\.com",
    r"generated (with|by) \[?claude",
    r"claude\.(com|ai)/(claude-)?code",
    r"\bclaude code\b",
    r"\banthropic\b",
    r"🤖",
]
IDENTITY_PATTERN = re.compile(r"claude|anthropic", re.IGNORECASE)
OPERATORS = {"&&", "||", ";", "|", "&", "\n"}

ROOT = Path(os.environ.get("CLAUDE_PROJECT_DIR") or Path(__file__).resolve().parents[2])


# --------------------------------------------------------------------------- helpers
def run(*args, check=False):
    return subprocess.run(args, cwd=ROOT, capture_output=True, text=True, check=check)


def git(*args):
    return run("git", *args).stdout.strip()


def find_attribution(text):
    return [p for p in ATTRIBUTION_PATTERNS if re.search(p, text or "", re.IGNORECASE)]


def split_segments(command):
    """Tokenize a shell command and split it into simple commands."""
    lexer = shlex.shlex(command, posix=True, punctuation_chars=";&|")
    lexer.whitespace_split = True
    lexer.commenters = ""
    try:
        tokens = list(lexer)
    except ValueError:  # unbalanced quotes: fall back to a naive split
        tokens = command.split()
    segments, current = [], []
    for tok in tokens:
        if tok in OPERATORS:
            if current:
                segments.append(current)
            current = []
        else:
            current.append(tok)
    if current:
        segments.append(current)
    return segments


def option_values(args, *names):
    """Collect values of options like -m/--message (both `-m x` and `--message=x`)."""
    values = []
    for i, arg in enumerate(args):
        for name in names:
            if arg == name and i + 1 < len(args):
                values.append(args[i + 1])
            elif name.startswith("--") and arg.startswith(name + "="):
                values.append(arg.split("=", 1)[1])
            elif not name.startswith("--") and arg.startswith(name) and len(arg) > len(name):
                values.append(arg[len(name):])
    return values


def read_file(path):
    try:
        return (ROOT / path).read_text() if path != "-" else ""
    except OSError:
        return ""


def staged_snapshot():
    """Export the index (exactly what will be committed) to a temp directory."""
    tmp = Path(tempfile.mkdtemp(prefix="git-guard-"))
    run("git", "checkout-index", "--all", "--force", f"--prefix={tmp}/")
    if (ROOT / ".env").exists():  # untracked local config the checks need
        shutil.copy(ROOT / ".env", tmp / ".env")
    return tmp


def quality_gate(root=ROOT):
    """Run Django system checks and the test suite in `root`."""
    python = ROOT / ".venv" / "bin" / "python"
    python = str(python) if python.exists() else sys.executable
    if not (root / "manage.py").exists():
        return []
    steps = [("Django system check", [python, "manage.py", "check"])]
    if (root / "src" / "config" / "settings" / "test.py").exists():
        steps.append(
            ("Test suite", [python, "manage.py", "test", "apps", "--settings=config.settings.test"])
        )
    errors = []
    for label, cmd in steps:
        result = subprocess.run(cmd, cwd=root, capture_output=True, text=True)
        if result.returncode != 0:
            tail = "\n".join((result.stdout + result.stderr).strip().splitlines()[-15:])
            errors.append(f"{label} failed:\n{tail}")
    return errors


# --------------------------------------------------------------------------- checks
def check_commit(args, stages_in_same_command=False):
    errors = []
    messages = option_values(args, "-m", "--message")
    messages += [read_file(p) for p in option_values(args, "-F", "--file")]
    for msg in messages:
        if find_attribution(msg):
            errors.append("Commit message credits Claude/Anthropic (Co-Authored-By trailer, "
                          "'Generated with Claude Code' footer, etc.). Remove it.")
            break

    for key in ("user.name", "user.email"):
        if IDENTITY_PATTERN.search(git("config", key)):
            errors.append(f"git {key} must be a human author, not Claude/Anthropic.")

    staged = git("diff", "--cached", "--name-only").splitlines()
    secrets = [f for f in staged if re.search(r"(^|/)\.env(\.(?!example$)[^/]+)?$", f)]
    if secrets:
        errors.append(f"Secret files are staged: {', '.join(secrets)}. Unstage them.")

    # Test exactly what is being committed. If files are staged by the same
    # command (`git add … && git commit`, `commit -a`) the index is not final
    # yet, so fall back to the working tree.
    if stages_in_same_command or {"-a", "--all"} & set(args):
        errors += quality_gate()
    else:
        snapshot = staged_snapshot()
        try:
            errors += quality_gate(snapshot)
        finally:
            shutil.rmtree(snapshot, ignore_errors=True)
    return errors


def check_push(args):
    errors = []
    forced = any(a in ("-f", "--force") or a.startswith("--force=") for a in args)
    targets = {a.split(":")[-1].lstrip("+") for a in args if not a.startswith("-")}
    if (forced or any(a.startswith("+") for a in args)) and targets & PROTECTED_BRANCHES:
        errors.append(f"Force-push to a protected branch ({', '.join(PROTECTED_BRANCHES)}) is not allowed.")

    # Every local commit that is not on a remote yet is about to be published.
    log = git("log", "--branches", "--not", "--remotes",
              "--format=%H%x00%an <%ae>%x00%cn <%ce>%x00%B%x1e")
    for entry in filter(None, (e.strip() for e in log.split("\x1e"))):
        sha, author, committer, body = (entry.split("\x00") + ["", "", ""])[:4]
        if IDENTITY_PATTERN.search(author) or IDENTITY_PATTERN.search(committer):
            errors.append(f"Commit {sha[:7]} has a Claude/Anthropic author or committer.")
        if find_attribution(body):
            errors.append(f"Commit {sha[:7]} message credits Claude/Anthropic. "
                          "Reword it (git commit --amend / rebase) before pushing.")

    errors += quality_gate()
    return errors


def check_pull(_args):
    if git("status", "--porcelain", "--untracked-files=no"):
        return ["Working tree has uncommitted changes. Commit or stash them before pulling."]
    return []


def check_pr_create(args):
    errors = []
    texts = option_values(args, "-t", "--title") + option_values(args, "-b", "--body")
    texts += [read_file(p) for p in option_values(args, "-F", "--body-file")]
    if any(find_attribution(t) for t in texts):
        errors.append("PR title/body credits Claude/Anthropic "
                      "(e.g. 'Generated with Claude Code'). Remove it.")
    if "--fill" in args or "--fill-first" in args or "--fill-verbose" in args:
        errors.append("Do not use --fill: write the PR title and body explicitly.")

    base = (option_values(args, "-B", "--base") or [DEFAULT_BASE])[-1]
    head = (option_values(args, "-H", "--head") or [git("branch", "--show-current")])[-1]
    head = head.split(":")[-1]
    base_ref = f"origin/{base}" if git("rev-parse", "--verify", "--quiet", f"origin/{base}") else base
    changed = [f for f in git("diff", "--name-only", f"{base_ref}...{head}").splitlines() if f]
    if len(changed) > MAX_PR_FILES:
        errors.append(
            f"PR {head} -> {base} changes {len(changed)} files; the limit is {MAX_PR_FILES}. "
            "Split it into smaller stacked PRs.")
    return errors


def classify(segment):
    """Return (kind, args) for a git/gh command segment we care about."""
    while segment and re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", segment[0]):  # env assignments
        segment = segment[1:]
    if not segment:
        return None, []
    prog = os.path.basename(segment[0])
    rest = segment[1:]
    if prog == "git":
        while rest and rest[0] in ("-C", "-c"):  # git -C <dir> / -c key=val
            rest = rest[2:]
        if rest and rest[0] in ("add", "commit", "push", "pull"):
            return rest[0], rest[1:]
    if prog == "gh" and rest[:2] == ["pr", "create"]:
        return "pr-create", rest[2:]
    return None, []


CHECKS = {"commit": check_commit, "push": check_push, "pull": check_pull, "pr-create": check_pr_create}


def main():
    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError:
        return 0
    if payload.get("tool_name") != "Bash":
        return 0
    command = payload.get("tool_input", {}).get("command", "")
    if not re.search(r"\b(git|gh)\b", command):
        return 0

    errors, seen = [], set()
    for segment in split_segments(command):
        kind, args = classify(segment)
        if kind == "add":
            seen.add("add")
            continue
        if kind and kind not in seen:
            seen.add(kind)
            extra = {"stages_in_same_command": "add" in seen} if kind == "commit" else {}
            errors += [f"[{kind}] {e}" for e in CHECKS[kind](args, **extra)]

    if errors:
        print("Blocked by .claude/hooks/git_guard.py:\n- " + "\n- ".join(errors), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
