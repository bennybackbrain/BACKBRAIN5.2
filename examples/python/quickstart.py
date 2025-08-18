#!/usr/bin/env python3
"""Minimal Backbrain client quickstart.

Usage:
  export BASE_URL=https://backbrain5.fly.dev
  export BB_API_KEY=...   # optional for private write
  python examples/python/quickstart.py
"""
from clients.python.backbrain_client import from_env, BackbrainError
import os, sys

def main():
    c = from_env()
    name = 'quickstart_demo.txt'
    try:
        if c.api_key:
            print('Writing file (requires API key)...')
            r = c.write_file(name, 'Hello Backbrain!')
            print('Write response:', r)
        else:
            print('No API key set; skipping write.')
        print('Listing entry files...')
        files = c.list_files('entries')
        print('Total files (first 10):', files[:10])
        if name in files:
            print('Reading file...')
            content = c.read_file(name)
            print('Content:', content[:200])
    except BackbrainError as e:
        print('Error:', e, file=sys.stderr)
        sys.exit(1)

if __name__ == '__main__':
    main()
