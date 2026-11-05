"""Capture real rendered administrator pages without running research actions."""
from pathlib import Path
from datetime import datetime
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / ".local/browser-qa"))
from playwright.sync_api import sync_playwright

BASE = "https://tutor.example.invalid"
PROJECT = "c37b9168a0db40e3b258c9c03cd56697"
PAGES = [
    ("overview", "研究总览", "view=overview"),
    ("chat", "研究对话", "view=chat"),
    ("workflow", "工作流", "view=workflow"),
    ("literature", "文献与知识库", "area=literature"),
    ("code", "程序", "area=code"),
    ("paper", "论文", "area=paper"),
    ("figures", "图表", "area=figures"),
    ("slides", "PPT", "area=slides"),
]


def main():
    output = ROOT / "reports/admin-review"
    output.mkdir(exist_ok=True)
    manifest = {"captured_at": datetime.now().astimezone().isoformat(),
                "project_id": PROJECT, "pages": [], "viewport": {"width": 1500, "height": 1000},
                "scope": "实际浏览器渲染的页面截图和可见文字；未执行模型生成、文件修改或研究任务。"}
    with sync_playwright() as p:
        browser = p.chromium.launch(
            executable_path="C:/Program Files/Google/Chrome/Application/chrome.exe",
            headless=True, proxy={"server": "http://127.0.0.1:12000"})
        context = browser.new_context(viewport=manifest["viewport"])
        result = context.request.get(BASE + "/admin/research/api/bootstrap")
        assert result.ok
        project = next(item for item in result.json()["projects"] if item["id"] == PROJECT)
        manifest["project_name"] = project["name"]
        page = context.new_page()
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        for key, title, query in PAGES:
            url = BASE + "/admin/research/?project=" + PROJECT + "&dt_workspace=" + project["native_id"] + "&" + query
            page.goto(url, wait_until="domcontentloaded", timeout=60000)
            page.get_by_role("button", name="研究总览", exact=True).wait_for(timeout=45000)
            if query.startswith("area="):
                page.locator(".dp-artifacts").wait_for(state="visible", timeout=30000)
            page.wait_for_timeout(2500)
            text = page.locator("body").inner_text()
            assert len(text) > 60, title + " did not render"
            assert not errors, errors
            filename = key + ".png"
            page.screenshot(path=str(output / filename), full_page=True)
            manifest["pages"].append({"key": key, "title": title, "url": page.url,
                                      "image_path": "/admin/review-images/" + filename,
                                      "visible_text": text[:6000], "text_truncated": len(text) > 6000})
            print(json.dumps({"captured": key, "visible_characters": len(text)}, ensure_ascii=True), flush=True)
        manifest["page_errors"] = errors
        browser.close()
    (output / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"pages": len(manifest["pages"]), "output": str(output)}, ensure_ascii=True))


if __name__ == "__main__":
    main()
