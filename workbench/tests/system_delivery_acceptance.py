"""Read-only final checks of the actual published application and MCP archive."""
import asyncio
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "mcp-package/src"))
from client import WorkbenchClient


async def main():
    client = WorkbenchClient()
    try:
        guide = await client.request("GET", "/research/api/integrations/workbench")
        assert guide["mcp"]["available"] is True
        assert len(guide["features"]) == 10 and len(guide["mcp"]["tools"]) == 37
        response = await client._http().get(client.url(guide["mcp"]["download"]))
        client.check(response)
        assert response.content == (ROOT / "mcp-package/dist/research-workbench-mcp.zip").read_bytes()
        html = await client.request("GET", "/research/")
        scripts = re.findall(r'src="(/research/assets/[^"]+\.js)"', html)
        styles = re.findall(r'href="(/research/assets/[^"]+\.css)"', html)
        assert scripts == ["/research/assets/index-bbPS919k.js"]
        assert styles == ["/research/assets/index-CLqCOViI.css"]
        build = json.loads((ROOT / "verification/build.json").read_text(encoding="utf8"))
        expected_assets = {x["path"].replace("static/", "/research/"): x["bytes"] for x in build["transferred"]["files"]}
        assets = []
        for path in scripts + styles:
            head = await client._http().head(client.url(path), headers={"Accept-Encoding": "identity"})
            client.check(head)
            assert int(head.headers["content-length"]) == expected_assets[path]
            assert head.headers["content-type"].startswith("text/javascript" if path.endswith(".js") else "text/css")
            sample = await client._http().get(client.url(path), headers={"Accept-Encoding": "identity", "Range": "bytes=0-127"})
            assert sample.status_code == 206 and len(sample.content) == 128
            assert sample.headers["content-range"] == "bytes 0-127/" + str(expected_assets[path])
            assets.append({"path": path, "status": head.status_code, "bytes": int(head.headers["content-length"]), "range_prefix_bytes": len(sample.content)})
        pid = "05a893386c09449d88366cf6dfdc825f"
        project = await client.project(pid)
        downloads = await client.request("GET", "/research/api/projects/" + pid + "/literature/downloads")
        worker = await client.request("GET", "/research/api/download-worker/status")
        report = {"success": True, "checked_utc": datetime.now(timezone.utc).isoformat(),
                  "project_id": project["id"], "features": len(guide["features"]), "tools": len(guide["mcp"]["tools"]),
                  "mcp_package": {"available": True, "site_bytes_equal_verified_archive": True,
                                  "bytes": len(response.content), "url": guide["mcp"]["download"]},
                  "web_assets": assets, "download_worker": worker,
                  "download_queue": downloads}
        (ROOT / "verification/system-delivery-acceptance.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf8")
        print(json.dumps({"success": True, "features": 10, "tools": 37, "package_bytes": len(response.content), "assets": assets}, ensure_ascii=False))
    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(main())
