#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""

import os
import sys
from pathlib import Path

# Application code lives in src/; make it importable.
sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))


def main():
    """Run a management command with ``src/`` on the import path."""
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError("Couldn't import Django. Is your virtual environment activated?") from exc
    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
