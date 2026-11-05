"""Run a command with age-encrypted environment values, without a plaintext file."""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
ALLOWED_KEYS = {"WEATHERBIT_KEY", "WEATHERAPI_KEY"}


def parse_secret_lines(text: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            raise ValueError("Invalid encrypted secrets format")
        name, value = line.split("=", 1)
        if (name not in ALLOWED_KEYS or name in values or
                not re.fullmatch(r"[A-Za-z0-9._/+=:-]+", value)):
            raise ValueError("Invalid encrypted secret entry")
        values[name] = value
    return values


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--identity", default=os.getenv("AGE_IDENTITY_FILE"))
    parser.add_argument("--ciphertext", default=str(ROOT / "secrets.env.age"))
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    command = args.command[1:] if args.command[:1] == ["--"] else args.command
    if not args.identity or not command:
        parser.error("set AGE_IDENTITY_FILE or --identity and provide a command after --")
    age_bin = os.getenv("AGE_BIN") or shutil.which("age")
    if not age_bin:
        parser.error("age executable not found on PATH")
    encrypted = subprocess.run(
        [age_bin, "-d", "-i", args.identity, args.ciphertext],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
    )
    if encrypted.returncode:
        print("Unable to decrypt secrets.env.age with the provided identity", file=sys.stderr)
        return 2
    try:
        values = parse_secret_lines(encrypted.stdout.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        print("Invalid encrypted secrets file", file=sys.stderr)
        return 2
    child_env = os.environ.copy()
    child_env.update(values)
    return subprocess.run(command, env=child_env, check=False).returncode


if __name__ == "__main__":
    raise SystemExit(main())
