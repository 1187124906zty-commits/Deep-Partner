"""A separate, anonymous administrator entrance; upstream authentication stays enabled."""
from contextlib import asynccontextmanager
from pathlib import Path
import asyncio
import html
import json
import mimetypes
import os
import re
import time

import httpx
from fastapi import FastAPI, Request, WebSocket
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse, Response, StreamingResponse
from starlette.background import BackgroundTask
from websockets.legacy.client import connect
from websockets.exceptions import WebSocketException

PREFIX = "/admin"
ORIGIN = "https://tutor.example.invalid"
STATIC = Path(os.environ.get("ADMIN_STATIC", "/srv/admin-static"))
DOC = Path(os.environ.get("ADMIN_ARCHITECTURE", "/srv/admin/architecture.md"))
REVIEW = Path(os.environ.get("ADMIN_REVIEW", "/srv/admin/review"))
LOGIN = Path(os.environ.get("ADMIN_LOGIN", "/run/secrets/admin-login.json"))
PROJECT = "c37b9168a0db40e3b258c9c03cd56697"
DROP = {"host", "content-length", "connection", "transfer-encoding", "content-encoding",
        "set-cookie", "authorization", "cookie", "accept-encoding"}
PATH_LITERAL = re.compile(r"""(["'\x60])/(research|api|ws)(?=[/?"'\x60])""")
cache = {}


def relocate(text):
    return PATH_LITERAL.sub(lambda match: match[1] + PREFIX + "/" + match[2], text)


def upstream(path):
    if path.startswith("/research/api/"):
        port = 47900
        if re.match(r"/research/api/projects/[^/]+/research-flow(?:/|$)", path):
            port = 47909
        elif re.match(r"/research/api/download-worker/[^/]+/result$", path):
            port = 47905
        elif re.match(r"/research/api/projects/[^/]+/(literature/upload|attachments)$", path):
            port = 47905
    elif path.startswith("/api/coder/"):
        port = 8010
    elif path.startswith(("/api/mobile-tools/", "/partner/")):
        port = 19390
    else:
        port = 8008
    return "http://127.0.0.1:" + str(port)


class Administrator:
    def __init__(self, client):
        self.client = client
        self.token = ""
        self.expires = 0
        self.lock = asyncio.Lock()

    async def headers(self):
        async with self.lock:
            if time.monotonic() >= self.expires:
                # Authentication stays between services. No browser receives this cookie.
                credentials = json.loads(LOGIN.read_text())
                response = await self.client.post(
                    "http://127.0.0.1:8008/api/auth/login",
                    json={key: credentials[key] for key in ("username", "password")},
                    headers={"Origin": ORIGIN})
                response.raise_for_status()
                assert response.json().get("is_admin"), "The configured account is not an administrator"
                self.token = response.cookies.get("dt_token")
                assert self.token, "Native login did not return a session"
                self.expires = time.monotonic() + 300
                self.client.cookies.clear()
        return {"Authorization": "Bearer " + self.token, "Origin": ORIGIN}


@asynccontextmanager
async def lifespan(app):
    async with httpx.AsyncClient(timeout=httpx.Timeout(None, connect=15), trust_env=False) as client:
        app.state.client = client
        app.state.admin = Administrator(client)
        yield


app = FastAPI(title="Deep Partner administrator entrance", lifespan=lifespan)


@app.get("/health")
def health():
    return {"ok": True, "scope": PREFIX, "original_authentication": "unchanged"}


@app.api_route(PREFIX, methods=["GET", "HEAD"])
@app.api_route(PREFIX + "/", methods=["GET", "HEAD"])
async def entry():
    return RedirectResponse(PREFIX + "/research/?project=" + PROJECT + "&view=overview", status_code=303)


@app.api_route(PREFIX + "/architecture.md", methods=["GET", "HEAD"])
async def architecture_markdown():
    return Response(DOC.read_text(), media_type="text/plain", headers={"Cache-Control": "no-store"})


@app.api_route(PREFIX + "/architecture", methods=["GET", "HEAD"])
async def architecture():
    content = html.escape(DOC.read_text())
    return HTMLResponse(
        '<!doctype html><html lang="zh-CN"><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<title>Deep Partner · 架构</title>'
        '<style>body{max-width:1000px;margin:48px auto;padding:0 24px;font:16px/1.8 system-ui;'
        'color:#262626;background:#fdfcf9}pre{white-space:pre-wrap;font:inherit}a{color:#365c78}</style>'
        '<a href="/admin/">打开管理员工作台</a> · '
        '<a href="/admin/research/api/schema">读取 API 架构</a>'
        '<pre>' + content + '</pre></html>', headers={"Cache-Control": "no-store"})


def review_manifest():
    return json.loads((REVIEW / "manifest.json").read_text())


@app.api_route(PREFIX + "/review.json", methods=["GET", "HEAD"])
async def review_json():
    return JSONResponse(review_manifest(), headers={"Cache-Control": "no-store"})


@app.api_route(PREFIX + "/review.md", methods=["GET", "HEAD"])
async def review_markdown():
    manifest = review_manifest()
    content = ["# Deep Partner 实际界面审阅", "",
               "以下截图与文字来自实际浏览器渲染。它们是静态审阅资料，交互测试仍需支持 JavaScript 的浏览器。",
               "采集时间：" + manifest["captured_at"], "项目：" + manifest["project_name"], ""]
    for page in manifest["pages"]:
        content.extend(["## " + page["title"], "",
                        "界面：" + page["url"],
                        "实际截图：" + ORIGIN + page["image_path"], "",
                        "当时可见的页面文字：", "", page["visible_text"], ""])
    return Response("\n".join(content), media_type="text/plain", headers={"Cache-Control": "no-store"})


@app.api_route(PREFIX + "/review-images/{name}", methods=["GET", "HEAD"])
async def review_image(name: str):
    allowed = {Path(page["image_path"]).name for page in review_manifest()["pages"]}
    if name not in allowed:
        return JSONResponse({"detail": "Unknown review image"}, status_code=404)
    return FileResponse(REVIEW / name, media_type="image/png", headers={"Cache-Control": "no-store"})


@app.api_route(PREFIX + "/review", methods=["GET", "HEAD"])
async def review_page():
    manifest = review_manifest()
    escape = html.escape
    sections = []
    for page in manifest["pages"]:
        sections.append(
            '<section id="' + escape(page["key"]) + '"><h2>' + escape(page["title"]) + '</h2>'
            '<p><a href="' + escape(page["url"]) + '">打开交互页面</a> · '
            '<a href="' + escape(page["image_path"]) + '">查看原始截图</a></p>'
            '<img loading="lazy" src="' + escape(page["image_path"]) + '" alt="' +
            escape(page["title"]) + '的实际浏览器截图">'
            '<h3>采集时可见的文字</h3><pre>' + escape(page["visible_text"]) + '</pre></section>')
    navigation = " · ".join('<a href="#' + escape(page["key"]) + '">' +
                            escape(page["title"]) + '</a>' for page in manifest["pages"])
    return HTMLResponse(
        '<!doctype html><html lang="zh-CN"><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<title>Deep Partner · 实际界面审阅</title>'
        '<style>body{max-width:1200px;margin:40px auto;padding:0 24px;font:16px/1.8 system-ui;'
        'color:#262626;background:#fdfcf9}img{display:block;width:100%;height:auto;border:1px solid #ddd}'
        'pre{white-space:pre-wrap;overflow-wrap:anywhere;font:14px/1.7 system-ui;background:#f2f0eb;'
        'padding:20px}a{color:#365c78}section{margin:56px 0}h1,h2,h3{line-height:1.3}</style>'
        '<h1>Deep Partner 科研工作流 App：实际界面审阅</h1>'
        '<p>本页无需 JavaScript，提供真实浏览器渲染后的截图和当时可见的页面文字。'
        '这是静态审阅资料；操作流程与交互行为仍需在支持 JavaScript 的浏览器中检查。</p>'
        '<p>采集时间：' + escape(manifest["captured_at"]) + '；项目：' +
        escape(manifest["project_name"]) + '；视口：1500 × 1000。</p>'
        '<p><a href="/admin/">打开交互应用</a> · <a href="/admin/review.md">读取纯文本</a> · '
        '<a href="/admin/review.json">读取采集清单</a> · '
        '<a href="/admin/architecture">读取系统架构</a></p><nav>' + navigation + '</nav>' +
        "".join(sections) + '</html>', headers={"Cache-Control": "no-store"})


def static_response(path):
    relative = path.removeprefix("/research/")
    if path in ("/research", "/research/"):
        relative = "index.html"
    target = (STATIC / relative).resolve()
    if not target.is_relative_to(STATIC.resolve()) or not target.is_file():
        return None
    media_type = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
    if target.suffix in (".html", ".js", ".css", ".json", ".svg"):
        stamp = target.stat().st_mtime_ns
        key = str(target)
        item = cache.get(key)
        if not item or item[0] != stamp:
            data = relocate(target.read_text())
            if target.name == "index.html":
                data = data.replace("<title>DeepPartner</title>", "<title>Deep Partner · 管理员</title>")
                fallback = (
                    '<main><h1>Deep Partner 科研工作流 App</h1>'
                    '<p>交互界面需要浏览器执行 JavaScript。仅支持网页正文读取的工具可直接查看'
                    '<a href="/admin/review">真实界面截图与页面文字</a>。</p>'
                    '<p><a href="/admin/review.md">纯文本审阅资料</a> · '
                    '<a href="/admin/architecture">系统架构说明</a> · '
                    '<a href="/admin/research/api/schema">API 定义</a></p></main>')
                assert data.count('<div id="root"></div>') == 1, "SPA root changed"
                data = data.replace('<div id="root"></div>', '<div id="root">' + fallback + '</div>', 1)
            cache[key] = (stamp, data.encode())
        data = cache[key][1]
    else:
        data = target.read_bytes()
    return Response(data, media_type=media_type, headers={"Cache-Control": "no-store"})


@app.websocket(PREFIX + "/{path:path}")
async def websocket_proxy(browser: WebSocket, path: str):
    target = "/" + path
    if not target.startswith(("/ws", "/api/")):
        await browser.close(code=1008)
        return
    headers = await browser.app.state.admin.headers()
    # Native WebSockets authenticate through a cookie or query token, while
    # HTTP endpoints also accept Authorization. Keep this cookie server-side.
    headers["Cookie"] = "dt_token=" + browser.app.state.admin.token
    address = upstream(target).replace("http://", "ws://", 1) + target
    if browser.url.query:
        address += "?" + browser.url.query
    protocols = browser.headers.get("sec-websocket-protocol", "").split(",")
    protocols = [value.strip() for value in protocols if value.strip()]
    try:
        async with connect(address, extra_headers=headers, subprotocols=protocols or None,
                           max_size=43341141, open_timeout=15) as native:
            await browser.accept(subprotocol=native.subprotocol)

            async def send_native():
                while True:
                    message = await browser.receive()
                    if message["type"] == "websocket.disconnect":
                        return
                    await native.send(message.get("text") if message.get("text") is not None else message["bytes"])

            async def send_browser():
                async for message in native:
                    if isinstance(message, bytes):
                        await browser.send_bytes(message)
                    else:
                        await browser.send_text(relocate(message))

            tasks = [asyncio.create_task(send_native()), asyncio.create_task(send_browser())]
            done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
            for task in pending:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
    except (OSError, RuntimeError, WebSocketException):
        await browser.close(code=1011)


@app.api_route(PREFIX + "/{path:path}", methods=["GET", "HEAD", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"])
async def proxy(request: Request, path: str):
    target = "/" + path
    if target in ("/login", "/register", "/access", "/access/request"):
        return RedirectResponse(PREFIX + "/", status_code=303)
    if target.startswith("/research/") and not target.startswith("/research/api/"):
        result = static_response(target)
        if result is not None:
            return result
    if not target.startswith(("/research/api/", "/api/", "/ws", "/partner/")):
        return JSONResponse({"detail": "Unknown administrator route"}, status_code=404)
    if request.method not in ("GET", "HEAD", "OPTIONS"):
        origin = request.headers.get("origin")
        if origin and origin.rstrip("/") != ORIGIN:
            return JSONResponse({"detail": "请求来源与工作台不一致"}, status_code=403)
    headers = {key: value for key, value in request.headers.items() if key.lower() not in DROP}
    headers.update(await request.app.state.admin.headers())
    headers["Accept-Encoding"] = "identity"
    url = upstream(target) + target
    if request.url.query:
        url += "?" + request.url.query
    client = request.app.state.client
    response = await client.send(client.build_request(
        request.method, url, headers=headers, content=request.stream()), stream=True)
    forwarded = {key: value for key, value in response.headers.items() if key.lower() not in DROP}
    forwarded["Cache-Control"] = "no-store"
    if "location" in forwarded and forwarded["location"].startswith("/"):
        forwarded["location"] = PREFIX + forwarded["location"]
    if "json" in response.headers.get("content-type", ""):
        try:
            body = relocate((await response.aread()).decode())
        finally:
            await response.aclose()
        return Response(body, status_code=response.status_code, headers=forwarded)
    return StreamingResponse(response.aiter_raw(), status_code=response.status_code,
                             headers=forwarded, background=BackgroundTask(response.aclose))
