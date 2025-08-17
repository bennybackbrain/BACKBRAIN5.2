#!/usr/bin/env python3
"""Secrets setup & retrieval for BACKBRAIN5.2.

Usage:
  python secrets_setup.py --init   # interactively store secrets into macOS Keychain
  python secrets_setup.py --test   # show masked retrieval

Secrets are stored under the service name BACKBRAIN5.2.
Falls Keychain nicht verfügbar (z.B. CI), werden Environment-Variablen genutzt.

Never commit real secret values.
"""
from __future__ import annotations

import argparse
import os
import sys
import getpass
from typing import Optional

import keyring  # type: ignore

SERVICE = "BACKBRAIN5.2"
SECRET_KEYS = [
    "WEBDAV_URL",
    "WEBDAV_USERNAME",
    "WEBDAV_PASSWORD",
    "OPENAI_API_KEY",
    # Add additional keys here as needed
]

def set_secret(key: str, value: str) -> None:
    keyring.set_password(SERVICE, key, value)

def get_secret(key: str) -> Optional[str]:
    try:
        val = keyring.get_password(SERVICE, key)
        if val:
            return val
    except Exception:
        pass
    return os.getenv(key)

def init_interactive() -> None:
    print(f"== BACKBRAIN5.2 Secret Initialisierung (Service: {SERVICE}) ==")
    print("Leer lassen zum Überspringen.")
    for k in SECRET_KEYS:
        # WEBDAV_PASSWORD etc. nicht im Klartext anzeigen
        prompt = f"{k}: "
        if k.endswith("PASSWORD") or k.endswith("KEY"):
            val = getpass.getpass(prompt)
        else:
            val = input(prompt)
        val = val.strip()
        if not val:
            print(f"  übersprungen {k}")
            continue
        set_secret(k, val)
        print(f"  gespeichert {k}")
    print("Fertig. Mit --test prüfen.")

def test_output() -> None:
    print(f"== BACKBRAIN5.2 Secret Test (Service: {SERVICE}) ==")
    for k in SECRET_KEYS:
        v = get_secret(k)
        if not v:
            print(f"{k}: [missing]")
            continue
        masked = v if len(v) <= 10 else f"{v[:4]}…{v[-4:]}"
        print(f"{k}: {masked}")

def parse_args():
    ap = argparse.ArgumentParser(description="Manage secrets in macOS Keychain (with env fallback).")
    ap.add_argument("--init", action="store_true", help="Interactively set secrets")
    ap.add_argument("--test", action="store_true", help="Show masked secrets")
    return ap.parse_args()

def main() -> int:
    args = parse_args()
    if args.init:
        init_interactive()
        return 0
    if args.test:
        test_output()
        return 0
    print("Nothing to do. Use --init or --test.")
    return 0

if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
