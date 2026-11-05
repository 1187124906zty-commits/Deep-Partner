"""Compare actual stdio-produced artifacts with separate native HTTP responses."""
from __future__ import annotations

import argparse
import asyncio
from datetime import datetime, timezone
import io
import json
import os
from pathlib import Path
import zipfile

import httpx

from conftest import DATA, ORIGIN, PACKAGE, QA, png_rgb


async def verify(root, report):
    session = json.loads(Path(os.environ["WORKBENCH_SESSION_FILE"]).read_text(encoding="utf-8-sig"))
    assert session["origin"].rstrip("/") == ORIGIN
    cases = [
        ("template-0.png", "/research/api/manuscript-template-preview/elsevier", None),
        ("template-1.png", "/research/api/manuscript-template-preview/elsevier", None),
        ("export-0.docx", f"/research/api/projects/{QA}/download", {"area": "manuscript", "name": "清稿.docx"}),
        ("export-1.docx", f"/research/api/projects/{QA}/download", {"area": "manuscript", "name": "清稿.docx"}),
        ("export-2.pptx", f"/research/api/projects/{QA}/download", {"area": "slides", "name": "研究汇报.pptx"}),
        ("slide-0.png", f"/research/api/projects/{QA}/slide-preview", {"kind": "deck", "page": 1}),
        ("slide-1.png", f"/research/api/projects/{QA}/slide-preview", {"kind": "deck", "page": 2}),
    ]
    comparisons = []
    async with httpx.AsyncClient(base_url=ORIGIN, headers={"Origin": ORIGIN}, cookies=session["cookies"],
                                 timeout=180, trust_env=False) as native:
        for name, path, params in cases:
            response = await native.get(path, params=params)
            assert response.status_code == 200, f"Native artifact unavailable: {name} status{response.status_code}"
            actual = (root / name).read_bytes()
            assert actual == response.content, f"Every stdio artifact byte must agree with source: {name}"
            if name.endswith((".docx", ".pptx")):
                with zipfile.ZipFile(io.BytesIO(actual)) as archive:
                    assert archive.testzip() is None
                    member = "word/document.xml" if name.endswith(".docx") else "ppt/presentation.xml"
                    assert member in archive.namelist()
            else:
                assert actual.startswith(b"\x89PNG")
            comparisons.append({"file": str((root / name).resolve()), "native_path": path, "params": params,
                                "bytes": len(actual), "every_byte_equal": True})
        raster = await native.get(f"/research/api/projects/{QA}/file", params={"path": "results/synthetic.png"})
        assert raster.status_code == 200
        supplied = png_rgb((DATA / "changed_synthetic.png").read_bytes())
        actual = png_rgb(raster.content)
        assert actual == supplied
        context = await native.get(f"/research/api/projects/{QA}/image-context", params={"path": "results/synthetic.png"})
        assert context.status_code == 200
        assert context.json()["last_request"] == "Independent stdio synthetic draft 1; preserve native metadata."
        result = {"utc": datetime.now(timezone.utc).isoformat(), "success": True, "artifact_comparisons": comparisons,
                  "raster": {"width": actual[0], "height": actual[1], "rgb_bytes": len(actual[2]), "all_pixels_equal_changed_caller_input": True},
                  "review": {"latest_source_instruction_equal_stdio_input": True, "send": False}}
        report.parent.mkdir(parents=True, exist_ok=True)
        report.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf8")
        print(json.dumps({"success": True, "artifacts": len(comparisons), "all_raster_rgb_bytes": len(actual[2]), "report": str(report)}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifact-root", type=Path, default=PACKAGE / "tests/results/authoring_api/stdio/development")
    parser.add_argument("--report", type=Path, default=PACKAGE / "tests/results/authoring_api/stdio-artifact-comparisons.json")
    args = parser.parse_args()
    asyncio.run(verify(args.artifact_root.resolve(), args.report.resolve()))
