"""Read-only production checks with a fresh browser and no login cookies."""
from pathlib import Path
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / ".local/browser-qa"))
from playwright.sync_api import sync_playwright

ORIGIN = "https://tutor.example.invalid"


def main():
    report = {"anonymous_browser": True, "checks": {}, "page_errors": [],
              "failed_requests": [], "escaped_api_requests": [], "websockets": []}
    with sync_playwright() as p:
        browser = p.chromium.launch(
            executable_path="C:/Program Files/Google/Chrome/Application/chrome.exe",
            headless=True, proxy={"server": "http://127.0.0.1:12000"})
        context = browser.new_context(viewport={"width": 1500, "height": 1000})
        for path, expected in [("/api/auth/status", 200), ("/research/api/bootstrap", 401),
                               ("/access/request", 200), ("/admin/architecture.md", 200),
                               ("/admin/research/api/bootstrap", 200),
                               ("/admin/research/api/schema", 200)]:
            response = context.request.get(ORIGIN + path, max_redirects=0, timeout=30000)
            assert response.status == expected, (path, response.status, response.text()[:500])
            report["checks"][path] = response.status
            if path == "/api/auth/status":
                assert response.json()["enabled"] is True
                assert response.json()["authenticated"] is False
            if path == "/admin/research/api/bootstrap":
                assert response.json()["user"]["role"] == "admin"
                report["projects"] = len(response.json()["projects"])
                assert "set-cookie" not in response.headers
        assert not context.cookies(), "Admin gateway leaked cookies into the original login"
        assert context.request.head(ORIGIN + "/admin/architecture.md").status == 200
        page = context.new_page()
        page.on("pageerror", lambda e: report["page_errors"].append(str(e)))
        page.on("response", lambda r: report["failed_requests"].append(
            {"status": r.status, "url": r.url}) if r.status >= 400 else None)
        page.on("request", lambda r: report["escaped_api_requests"].append(r.url)
                if r.url.startswith((ORIGIN + "/api/", ORIGIN + "/research/api/")) else None)
        page.on("websocket", lambda ws: report["websockets"].append(ws.url))
        page.goto(ORIGIN + "/admin/", wait_until="domcontentloaded", timeout=60000)
        page.get_by_role("button", name="研究总览", exact=True).wait_for(timeout=45000)
        page.wait_for_timeout(2500)
        report["title"] = page.title()
        report["url"] = page.url
        report["visible_text"] = page.locator("body").inner_text()[:1800]
        assert "/admin/research/" in page.url
        assert not report["page_errors"], report["page_errors"]
        assert not report["escaped_api_requests"], report["escaped_api_requests"]
        page.get_by_role("button", name="工作流", exact=True).first.click()
        page.wait_for_timeout(2000)
        report["workflow_view"] = "view=workflow" in page.url
        assert report["workflow_view"]
        report["websocket_handshake"] = page.evaluate("""() => new Promise(resolve => {
            const ws = new WebSocket('wss://tutor.example.invalid/admin/ws');
            const timeout = setTimeout(() => { ws.close(); resolve('timeout'); }, 12000);
            ws.onopen = () => { clearTimeout(timeout); ws.close(); resolve('open'); };
            ws.onerror = () => { clearTimeout(timeout); resolve('error'); };
        })""")
        assert report["websocket_handshake"] == "open"
        screenshot = ROOT / "reports/screenshots/admin-gateway.png"
        screenshot.parent.mkdir(exist_ok=True)
        page.screenshot(path=str(screenshot), full_page=True)
        report["screenshot"] = str(screenshot)
        assert not report["page_errors"], report["page_errors"]
        assert not report["failed_requests"], report["failed_requests"]
        assert not context.cookies(), "Admin browser changed original login state"
        browser.close()
    (ROOT / "reports/admin-gateway-verification.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
