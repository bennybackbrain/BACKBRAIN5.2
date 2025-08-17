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
from typing import Tuple, List, Sequence, Any
import requests
from dotenv import load_dotenv
from webdav3.client import Client

_loaded = False

def load_webdav_config() -> Tuple[str, str, str]:
    global _loaded
    if not _loaded:
        load_dotenv()  # idempotent
        _loaded = True
    url = os.getenv("WEBDAV_URL") or None
    user = os.getenv("WEBDAV_USERNAME") or None
    password = os.getenv("WEBDAV_PASSWORD") or None
    if not (url and user and password):
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
    entries: Sequence[Any] = client.list(norm)
    # Some servers include the directory itself as first entry; remove duplicates
    from typing import cast
    if entries and isinstance(entries[0], str) and entries[0].rstrip('/') in (norm.rstrip('/'), '.'):
        return [cast(str, e) for e in entries[1:] if isinstance(e, str)]
    return [cast(str, e) for e in entries if isinstance(e, str)]

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


def write_file_content(path: str, content: str) -> None:
    """Write (upload) text content to the given relative path.

    Creates intermediate directories implicitly via WebDAV client if supported.
    """
    rel = _sanitize_path(path)
    if not rel:
        raise ValueError("Empty path")
    url, user, password = load_webdav_config()
    file_url = f"{url}/{rel}"
    resp = requests.put(file_url, data=content.encode('utf-8'), auth=(user, password))
    if resp.status_code >= 400:
        raise RuntimeError(f"HTTP {resp.status_code} while writing {rel}")

__all__.append("write_file_content")


def mkdirs(path: str) -> bool:
    """Create directory path recursively (best-effort). Returns True if created new leaf.

    WebDAV MKCOL only creates a single level; we iterate segments.
    """
    norm = _sanitize_path(path)
    if not norm:
        return False
    url, user, password = load_webdav_config()
    base = url.rstrip('/')
    created_any = False
    current: List[str] = []
    for segment in norm.split('/'):
        current.append(segment)
        partial = '/'.join(current)
        dir_url = f"{base}/{partial}".rstrip('/')
        # Probe existence via PROPFIND depth 0 (fast)
        head = requests.request("PROPFIND", dir_url + '/', auth=(user, password), headers={"Depth": "0"})
        if head.status_code == 404:
            mk = requests.request("MKCOL", dir_url, auth=(user, password))
            if mk.status_code not in (201, 405):  # 405 = already exists race
                raise RuntimeError(f"MKCOL failed for {partial}: {mk.status_code}")
            created_any = True
    return created_any

__all__.append("mkdirs")
