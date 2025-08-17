"""Reusable WebDAV client utilities.

Loads credentials from environment / .env and returns a webdavclient3 Client.

Environment variables:
  WEBDAV_URL
  WEBDAV_USERNAME
  WEBDAV_PASSWORD

Functions:
  load_webdav_config() -> (url, username, password)
  get_webdav_client() -> Client
  list_dir(path:str) -> list[str]
"""
from __future__ import annotations

import os
from typing import Tuple, List
import requests
from dotenv import load_dotenv
from webdav3.client import Client

_loaded = False

def load_webdav_config() -> Tuple[str, str, str]:
    global _loaded
    if not _loaded:
        load_dotenv()  # idempotent
        _loaded = True
    url = os.getenv("WEBDAV_URL")
    user = os.getenv("WEBDAV_USERNAME")
    password = os.getenv("WEBDAV_PASSWORD")
    if not all([url, user, password]):
        raise RuntimeError("Missing WEBDAV_URL / WEBDAV_USERNAME / WEBDAV_PASSWORD in environment/.env")
    return url.rstrip("/"), user, password  # normalize


def get_webdav_client() -> Client:
    url, user, password = load_webdav_config()
    options = {
        "webdav_hostname": url,
        "webdav_login": user,
        "webdav_password": password,
    }
    return Client(options)


def list_dir(path: str) -> List[str]:
    """List directory entries at given relative path (relative to WebDAV root)."""
    client = get_webdav_client()
    # webdavclient3 expects '.' or relative path; ensure no leading slash
    norm = path.lstrip('/') or '.'
    entries = client.list(norm)
    # Some servers include the directory itself as first entry; remove duplicates
    if entries and entries[0].rstrip('/') in (norm.rstrip('/'), '.'):
        return entries[1:]
    return entries

__all__ = ["get_webdav_client", "list_dir", "load_webdav_config"]
 
def _sanitize_path(path: str) -> str:
    # remove leading slash, prevent .. segments
    parts = [p for p in path.strip().split('/') if p and p not in ('.', '..')]
    return '/'.join(parts)


def get_file_content(path: str) -> str:
    """Download file content as UTF-8 (replacement chars on decode errors).

    Raises FileNotFoundError if the file does not exist.
    """
    rel = _sanitize_path(path)
    if not rel:
        raise FileNotFoundError("Empty path")
    url, user, password = load_webdav_config()
    file_url = f"{url}/{rel}"
    resp = requests.get(file_url, auth=(user, password))
    if resp.status_code == 404:
        raise FileNotFoundError(rel)
    if resp.status_code >= 400:
        raise RuntimeError(f"HTTP {resp.status_code} while fetching {rel}")
    # Try treat as text
    try:
        return resp.content.decode('utf-8', errors='replace')
    except Exception:  # pragma: no cover
        return resp.text

__all__.append("get_file_content")
