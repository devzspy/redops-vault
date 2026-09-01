"""Thin HTTP client over RedOps Vault's /api/v1 JSON API. Every CLI command
goes through this module rather than talking to httpx directly, so auth,
error translation, and base URL handling live in exactly one place. Mirrors
mcp_server/client.py's shape (same API, same server) but as an instance
rather than a module-level singleton, since the CLI constructs it lazily
after resolving config/env/flags rather than at import time.
"""

import os

import httpx


class ApiError(Exception):
    """Raised for any non-2xx response. Its message is what the user sees,
    so it includes the server's own error code/message rather than just an
    HTTP status.
    """

    def __init__(self, status_code, code, message):
        super().__init__(f"HTTP {status_code} ({code}): {message}")
        self.status_code = status_code
        self.code = code
        self.message = message


class ApiClient:
    def __init__(self, base_url, api_key, timeout=60.0, transport=None):
        """`transport` lets tests point this at an in-process WSGI app
        (httpx.WSGITransport) instead of a real socket.
        """
        self._client = httpx.Client(
            base_url=base_url, headers={"Authorization": f"Bearer {api_key}"}, timeout=timeout, transport=transport
        )

    def close(self):
        self._client.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        self.close()

    def _raise_for_error(self, resp):
        if resp.status_code < 400:
            return
        try:
            body = resp.json()
        except ValueError:
            body = {}
        raise ApiError(resp.status_code, body.get("error", "error"), body.get("message") or resp.text)

    def _parse(self, resp):
        if resp.status_code == 204 or not resp.content:
            return None
        return resp.json()

    def get(self, path, params=None):
        resp = self._client.get(path, params=params)
        self._raise_for_error(resp)
        return self._parse(resp)

    def get_text(self, path):
        """For endpoints that return plain text/HTML rather than JSON (e.g. a
        Markdown or HTML report export).
        """
        resp = self._client.get(path)
        self._raise_for_error(resp)
        return resp.text

    def post(self, path, json=None):
        resp = self._client.post(path, json=json if json is not None else {})
        self._raise_for_error(resp)
        return self._parse(resp)

    def patch(self, path, json=None):
        resp = self._client.patch(path, json=json if json is not None else {})
        self._raise_for_error(resp)
        return self._parse(resp)

    def put(self, path, json=None):
        resp = self._client.put(path, json=json if json is not None else {})
        self._raise_for_error(resp)
        return self._parse(resp)

    def delete(self, path):
        resp = self._client.delete(path)
        self._raise_for_error(resp)
        return {"deleted": True}

    def upload(self, path, file_path, fields):
        """Multipart file upload -- used for loot upload. `file_path` is a
        local path; `fields` is the accompanying form data (category,
        description, tags, associated_host, ...).
        """
        with open(file_path, "rb") as f:
            files = {"file": (os.path.basename(file_path), f)}
            data = {k: v for k, v in fields.items() if v is not None}
            resp = self._client.post(path, files=files, data=data, timeout=None)
        self._raise_for_error(resp)
        return self._parse(resp)

    def download(self, path, save_path):
        """Streams a binary response to a local file rather than buffering it
        in memory -- loot files can be many GB.
        """
        with self._client.stream("GET", path, timeout=None) as resp:
            if resp.status_code >= 400:
                resp.read()
                self._raise_for_error(resp)
            size = 0
            with open(save_path, "wb") as f:
                for chunk in resp.iter_bytes():
                    f.write(chunk)
                    size += len(chunk)
            sha256 = resp.headers.get("X-Sha256")
        return {"saved_to": save_path, "size_bytes": size, "sha256": sha256}
