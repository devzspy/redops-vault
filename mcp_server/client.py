"""Thin HTTP client over RedOps Vault's /api/v1 JSON API. Every MCP tool
goes through this module rather than talking to httpx directly, so auth,
error translation, and base URL handling live in exactly one place.
"""

import os
import sys

import httpx

DEFAULT_BASE_URL = "http://localhost:5000/api/v1"


class ApiError(Exception):
    """Raised for any non-2xx response. Its message is what the calling
    agent sees as the MCP tool error, so it includes the server's own
    error code/message rather than just an HTTP status.
    """

    def __init__(self, status_code, code, message):
        super().__init__(f"HTTP {status_code} ({code}): {message}")
        self.status_code = status_code
        self.code = code
        self.message = message


def _build_client():
    base_url = os.environ.get("REDOPS_API_BASE_URL", DEFAULT_BASE_URL)
    api_key = os.environ.get("REDOPS_API_KEY")
    if not api_key:
        print(
            "REDOPS_API_KEY environment variable is required (create one at "
            "/api-keys in the RedOps Vault web UI for an agent/operator/admin user).",
            file=sys.stderr,
        )
        sys.exit(1)
    return httpx.Client(base_url=base_url, headers={"Authorization": f"Bearer {api_key}"}, timeout=60.0)


_client = _build_client()


def _raise_for_error(resp):
    if resp.status_code < 400:
        return
    try:
        body = resp.json()
    except ValueError:
        body = {}
    raise ApiError(resp.status_code, body.get("error", "error"), body.get("message") or resp.text)


def _parse(resp):
    if resp.status_code == 204 or not resp.content:
        return None
    return resp.json()


def get(path, params=None):
    resp = _client.get(path, params=params)
    _raise_for_error(resp)
    return _parse(resp)


def get_text(path):
    """For endpoints that return plain text/HTML rather than JSON (e.g. a
    Markdown or HTML report export).
    """
    resp = _client.get(path)
    _raise_for_error(resp)
    return resp.text


def post(path, json=None):
    resp = _client.post(path, json=json if json is not None else {})
    _raise_for_error(resp)
    return _parse(resp)


def patch(path, json=None):
    resp = _client.patch(path, json=json if json is not None else {})
    _raise_for_error(resp)
    return _parse(resp)


def put(path, json=None):
    resp = _client.put(path, json=json if json is not None else {})
    _raise_for_error(resp)
    return _parse(resp)


def delete(path):
    resp = _client.delete(path)
    _raise_for_error(resp)
    return {"deleted": True}


def upload(path, file_path, fields):
    """Multipart file upload -- used for loot upload. `file_path` is a path
    on the machine running this MCP server; `fields` is the accompanying
    form data (category, description, tags, associated_host, ...).
    """
    with open(file_path, "rb") as f:
        files = {"file": (os.path.basename(file_path), f)}
        data = {k: v for k, v in fields.items() if v is not None}
        resp = _client.post(path, files=files, data=data, timeout=None)
    _raise_for_error(resp)
    return _parse(resp)


def download(path, save_path):
    """Streams a binary response to a local file rather than returning
    bytes in the tool result -- loot files can be many GB.
    """
    with _client.stream("GET", path, timeout=None) as resp:
        if resp.status_code >= 400:
            resp.read()
            _raise_for_error(resp)
        size = 0
        with open(save_path, "wb") as f:
            for chunk in resp.iter_bytes():
                f.write(chunk)
                size += len(chunk)
        sha256 = resp.headers.get("X-Sha256")
    return {"saved_to": save_path, "size_bytes": size, "sha256": sha256}
