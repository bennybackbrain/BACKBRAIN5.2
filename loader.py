#!/usr/bin/env python3
"""CLI tool to interact with Nextcloud / WebDAV storage.

Currently supported:
  --list     List files & folders in 01_inbox

Credentials are read from environment / .env (WEBDAV_URL, WEBDAV_USERNAME, WEBDAV_PASSWORD).

Examples:
  python loader.py --list
"""
from __future__ import annotations

import argparse
import sys
from typing import List

from app.services.webdav_client import list_dir

INBOX_DIR = "01_inbox"


def cmd_list() -> int:
    try:
        entries: List[str] = list_dir(INBOX_DIR)
    except Exception as exc:  # pragma: no cover
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 2
    if not entries:
        print("(leer)")
        return 0
    for e in entries:
        print(e)
    return 0


def parse_args():
    ap = argparse.ArgumentParser(description="BACKBRAIN5.2 WebDAV Loader")
    ap.add_argument("--list", action="store_true", help="List contents of 01_inbox")
    return ap.parse_args()


def main() -> int:
    args = parse_args()
    if args.list:
        return cmd_list()
    print("No command. Use --list", file=sys.stderr)
    return 1

if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
