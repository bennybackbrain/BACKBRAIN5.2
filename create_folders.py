#!/usr/bin/env python3
"""Create required folder structure on Nextcloud / WebDAV.

Reads credentials from .env (WEBDAV_URL, WEBDAV_USERNAME, WEBDAV_PASSWORD).
Uses webdavclient3 to connect and idempotently create folders:
  01_inbox
  02_processing
  03_processed_archive
  04_summaries
  05_errors

Usage:
  python create_folders.py

Exit codes:
  0 success
  1 missing configuration
  2 connection/auth failure
  3 unexpected error
"""
from __future__ import annotations

import sys
import os
from pathlib import PurePosixPath
from typing import List

try:
    from dotenv import load_dotenv
    from webdav3.client import Client
except ImportError as exc:  # pragma: no cover
    print("[ERROR] Missing dependency. Install with: pip install webdavclient3 python-dotenv", file=sys.stderr)
    raise


REQUIRED_DIRS: List[str] = [
    "01_inbox",
    "02_processing",
    "03_processed_archive",
    "04_summaries",
    "05_errors",
]


def load_config():
    load_dotenv()
    url = os.getenv("WEBDAV_URL")
    user = os.getenv("WEBDAV_USERNAME")
    password = os.getenv("WEBDAV_PASSWORD")
    if not all([url, user, password]):
        print("[ERROR] WEBDAV_URL / WEBDAV_USERNAME / WEBDAV_PASSWORD must be set in .env", file=sys.stderr)
        sys.exit(1)
    # Normalize URL (webdavclient expects root path; ensure trailing slash not required)
    return url.rstrip("/"), user, password


def make_client(url: str, username: str, password: str) -> Client:
    options = {
        "webdav_hostname": url,
        "webdav_login": username,
        "webdav_password": password,
        # timeouts could be added: "timeout": 30
    }
    return Client(options)


def ensure_dir(client: Client, path: str) -> bool:
    posix_path = str(PurePosixPath(path))
    try:
        if client.check(posix_path):
            print(f"[OK] Exists: {posix_path}")
            return False
        client.mkdir(posix_path)
        print(f"[CREATED] {posix_path}")
        return True
    except Exception as exc:  # pragma: no cover
        print(f"[ERROR] Cannot create '{posix_path}': {exc}", file=sys.stderr)
        raise


def main() -> int:
    url, user, password = load_config()
    try:
        client = make_client(url, user, password)
        # Simple auth validation: list root (catch auth errors early)
        try:
            client.list(".")
        except Exception as auth_exc:
            print(f"[ERROR] Authentication / connection failed: {auth_exc}", file=sys.stderr)
            return 2
        created = 0
        for d in REQUIRED_DIRS:
            if ensure_dir(client, d):
                created += 1
        print(f"Done. Created {created} new folder(s).")
        return 0
    except SystemExit as se:
        return se.code
    except Exception as exc:  # pragma: no cover
        print(f"[ERROR] Unexpected: {exc}", file=sys.stderr)
        return 3


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
