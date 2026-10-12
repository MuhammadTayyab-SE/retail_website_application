"""Django management entry point."""

import os
import re
import sys
from pathlib import Path

from django.core.management import execute_from_command_line


def load_local_environment(path, environ):
    """Load literal local settings without overriding the process environment."""
    try:
        lines = path.read_text(encoding="utf-8-sig").splitlines()
    except FileNotFoundError:
        return
    values = {}
    for number, line in enumerate(lines, 1):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        key, separator, value = line.partition("=")
        key, value = key.strip(), value.strip()
        if not separator or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", key):
            raise ValueError(f"Invalid .env assignment on line {number}.")
        if value.startswith(("'", '"')):
            if len(value) < 2 or value[-1] != value[0]:
                raise ValueError(f"Unclosed .env quote on line {number}.")
            value = value[1:-1]
        values[key] = value
    for key, value in values.items():
        environ.setdefault(key, value)


if __name__ == "__main__":
    try:
        load_local_environment(Path(__file__).resolve().with_name(".env"), os.environ)
    except ValueError as error:
        sys.exit(str(error))
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    execute_from_command_line(sys.argv)
