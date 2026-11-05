"""Authenticated transport to the existing Research Workbench APIs."""
from __future__ import annotations

import json
import mimetypes
import os
from pathlib import Path
from urllib.parse import urljoin, urlsplit
from uuid import uuid4

import httpx


DEFAULT_ORIGIN = "https://tutor.example.invalid"


def session_path() -> Path:
    return Path(os.environ.get("WORKBENCH_SESSION_FILE", str(Path.home() / ".config/research-workbench/session.json"))).expanduser()


class WorkbenchClient:
    """Resolve identity through upstream auth; never accept a substituted owner."""

    def __init__(self, origin: str | None = None):
        self.origin = (origin or os.environ.get("WORKBENCH_URL", DEFAULT_ORIGIN)).rstrip("/")
        parsed = urlsplit(self.origin)
        if parsed.username or parsed.password or parsed.path or parsed.query or parsed.fragment:
            raise ValueError("WORKBENCH_URL must be a server origin without a path or credentials")
        if parsed.scheme != "https" and not (parsed.scheme == "http" and parsed.hostname in ("localhost", "127.0.0.1", "::1")):
            raise ValueError("WORKBENCH_URL requires HTTPS, or HTTP on localhost")
        self._session = None

    def url(self, path: str) -> str:
        target = urljoin(self.origin + "/", path)
        parsed = urlsplit(target)
        source = urlsplit(self.origin)
        if (parsed.scheme, parsed.netloc) != (source.scheme, source.netloc) or parsed.username or parsed.password:
            raise ValueError("Authenticated requests must remain on the configured Workbench origin")
        return target

    def _http(self) -> httpx.AsyncClient:
        if self._session is not None:
            return self._session
        headers = {"Origin": self.origin, "Accept": "application/json"}
        cookies = {}
        token = os.environ.get("WORKBENCH_TOKEN", "").strip()
        file = session_path()
        if token:
            headers["Authorization"] = "Bearer " + token
        elif file.is_file():
            value = json.loads(file.read_text(encoding="utf-8-sig"))
            if value.get("origin", "").rstrip("/") != self.origin:
                raise ValueError("Session belongs to a different Workbench origin; sign in for WORKBENCH_URL")
            cookies = value.get("cookies", {})
            if not isinstance(cookies, dict) or not all(isinstance(k, str) and isinstance(v, str) for k, v in cookies.items()):
                raise ValueError("Invalid private session file; run workbench_auth.py login again")
        else:
            raise ValueError("Workbench sign-in required: run workbench_auth.py login or supply WORKBENCH_TOKEN")
        self._session = httpx.AsyncClient(headers=headers, cookies=cookies, timeout=httpx.Timeout(180, connect=20), follow_redirects=False, trust_env=False)
        return self._session

    @staticmethod
    def check(response: httpx.Response) -> None:
        if 200 <= response.status_code < 300:
            return
        if response.status_code in (401, 403):
            raise ValueError(f"Workbench HTTP {response.status_code}: sign in to the authorized account or check project access")
        detail = "Upstream request failed"
        if "json" in response.headers.get("content-type", ""):
            try:
                body = response.json()
                detail = str(body.get("detail", body.get("message", detail))) if isinstance(body, dict) else str(body)
            except ValueError:
                pass
        raise ValueError(f"Workbench HTTP {response.status_code}: {detail[:1200]}")

    async def request(self, method, path, *, params=None, json=None, data=None, files=None):
        response = await self._http().request(method, self.url(path), params=params, json=json, data=data, files=files)
        self.check(response)
        kind = response.headers.get("content-type", "")
        if "json" in kind:
            return response.json()
        if kind.startswith("text/") or "javascript" in kind or "svg+xml" in kind:
            return response.text
        root = Path(os.environ.get("WORKBENCH_OUTPUT_DIR", str(Path.home() / "Downloads/research-workbench"))).expanduser().resolve()
        suffix = mimetypes.guess_extension(kind.split(";", 1)[0]) or ".bin"
        return self._save(response, root / (uuid4().hex + suffix))

    @staticmethod
    def _save(response, output: Path):
        output.parent.mkdir(parents=True, exist_ok=True)
        temporary = output.with_name("." + uuid4().hex + ".part")
        try:
            temporary.write_bytes(response.content)
            temporary.replace(output)
        finally:
            temporary.unlink(missing_ok=True)
        return {"path": str(output), "bytes": len(response.content), "content_type": response.headers.get("content-type", "application/octet-stream"), "source_url": str(response.url)}

    async def download(self, path_or_same_origin_url, output_path, *, params=None):
        output = Path(output_path).expanduser()
        if not output.is_absolute():
            raise ValueError("Download output_path must be absolute")
        response = await self._http().get(self.url(path_or_same_origin_url), params=params)
        self.check(response)
        return self._save(response, output.resolve())

    async def project(self, project_id):
        value = await self.request("GET", "/research/api/projects")
        project = next((p for p in value.get("projects", []) if p.get("id") == project_id), None)
        if project is None:
            raise ValueError("Project is unavailable to the signed-in account")
        return project

    async def native_request(self, method, path, project_id, *, params=None, json=None, data=None, files=None):
        project = await self.project(project_id)
        workspace = project.get("native_id")
        if not workspace:
            raise ValueError("Project has no native workspace binding")
        return await self.request(method, path, params={**(params or {}), "dt_workspace": workspace}, json=json, data=data, files=files)

    async def close(self):
        if self._session is not None:
            await self._session.aclose()
            self._session = None
