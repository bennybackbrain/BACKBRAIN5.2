from __future__ import annotations
import os, json, time
import urllib.request, urllib.error
from typing import Any, Dict, Optional

class BackbrainError(Exception):
    pass

class BackbrainClient:
    def __init__(self, base_url: str, api_key: str | None = None, timeout: float = 15.0):
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key
        self.timeout = timeout

    def _req(self, method: str, path: str, params: Dict[str,str] | None = None, body: Dict[str,Any] | None = None) -> Any:
        url = self.base_url + path
        if params:
            from urllib.parse import urlencode
            url += '?' + urlencode(params)
        data_bytes: Optional[bytes] = None
        headers = {"Accept": "application/json"}
        if body is not None:
            data_bytes = json.dumps(body).encode('utf-8')
            headers["Content-Type"] = "application/json"
        if self.api_key:
            headers['X-API-Key'] = self.api_key
        req = urllib.request.Request(url, data=data_bytes, headers=headers, method=method.upper())
        start = time.time()
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                raw = resp.read().decode('utf-8')
                if resp.getheader('Content-Type','').startswith('application/json'):
                    return json.loads(raw)
                return raw
        except urllib.error.HTTPError as e:
            detail = e.read().decode('utf-8')
            raise BackbrainError(f"HTTP {e.code} {e.reason}: {detail[:200]}") from None
        except urllib.error.URLError as e:
            raise BackbrainError(f"Connection error: {e}") from None
        finally:
            duration_ms = int((time.time()-start)*1000)
            # lightweight debug log
            print(f"[backbrain_client] {method} {path} {duration_ms}ms", flush=True)

    def list_files(self, kind: str) -> list[str]:
        data = self._req('GET', '/api/v1/files/list-files', params={'kind': kind})
        return data['items'] if 'items' in data else data.get('files', [])

    def read_file(self, name: str, kind: str = 'entries') -> str:
        data = self._req('GET', '/api/v1/files/read-file', params={'name': name, 'kind': kind})
        # supports both private and public response shapes
        return data.get('content','') if isinstance(data, dict) else str(data)

    def write_file(self, name: str, content: str, kind: str = 'entries') -> dict[str,Any]:
        return self._req('POST', '/api/v1/files/write-file', body={'name': name, 'kind': kind, 'content': content})

# Convenience factory from env

def from_env() -> BackbrainClient:
    base = os.getenv('BASE_URL', 'http://127.0.0.1:8000')
    key = os.getenv('BB_API_KEY')
    return BackbrainClient(base, key)

__all__ = ['BackbrainClient', 'BackbrainError', 'from_env']
