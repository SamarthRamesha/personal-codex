#!/usr/bin/env python3
"""Generate an owner-only token or start the authenticated private backend. Never prints secrets."""
import argparse
import os
from pathlib import Path
import secrets
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--create-token", metavar="PATH", help="create a new 0600 token file; refuses overwrite")
    args = parser.parse_args()
    if args.create_token:
        path = Path(args.create_token).expanduser()
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w") as stream:
            stream.write(secrets.token_urlsafe(48) + "\n")
        print("Created owner token file; keep it outside Git. Its contents are never logged.")
        return
    if not os.getenv("PERSONAL_CODEX_TOKEN_FILE"):
        parser.error("set PERSONAL_CODEX_TOKEN_FILE to an owner-only token file")
    from app.server import main
    main()


if __name__ == "__main__":
    main()
