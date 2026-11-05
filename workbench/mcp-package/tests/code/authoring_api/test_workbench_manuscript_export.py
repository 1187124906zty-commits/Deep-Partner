import io
import json
from datetime import datetime, timedelta, timezone
import zipfile

import pytest

from conftest import QA


@pytest.mark.asyncio
@pytest.mark.parametrize("review,columns", [(False, 1), (True, 2)])
async def test_manuscript_export_jobs_compare_direct_source_tex_bytes(live, review, columns):
    before = await live.get("/manuscript")
    payload = {"format": "tex", "review": review, "language": "source", "document_id": "", "columns": columns}
    direct_response = await live.response("POST", "/manuscript/export", json=payload)
    assert direct_response.status_code == 200
    direct_job = await live.wait_job(direct_response.json()["job_id"])
    direct_result = direct_job["result"]
    direct_file = await live.response("GET", "/download", params={"area": "manuscript", "name": direct_result["name"]})
    assert direct_file.status_code == 200
    tool = await live.invoke("workbench_manuscript_export", project_id=QA, **payload)
    assert tool["artifacts"] == []
    assert set(tool["data"]) == {"job_id"}
    assert tool["data"]["job_id"] != direct_response.json()["job_id"]
    assert "completed" not in tool["message"].lower()
    job = await live.wait_job(tool["data"]["job_id"])
    assert job["result"] == direct_result
    raw = await live.response("GET", "/download", params={"area": "manuscript", "name": job["result"]["name"]})
    assert raw.status_code == 200
    if review:
        # Native export_manuscript creates a ZIP when review=True, retaining
        # exact review records. ZIP-container timestamps change across calls;
        # every archive member and every byte inside it must match exactly.
        with zipfile.ZipFile(io.BytesIO(raw.content)) as actual_zip, zipfile.ZipFile(io.BytesIO(direct_file.content)) as source_zip:
            assert actual_zip.namelist() == source_zip.namelist() == ["manuscript.tex", "review.json"]
            assert all(actual_zip.read(name) == source_zip.read(name) for name in source_zip.namelist())
            tex = actual_zip.read("manuscript.tex")
            review_record = json.loads(actual_zip.read("review.json"))
            # app.manuscript_export always calls author_profile.prepare_preview
            # for generic templates. This fixture has empty author details, so
            # the source adds exactly its honestly labelled local preview date.
            day = datetime.now(timezone(timedelta(hours=8))).date().isoformat()
            prepared_document = {**before["content"], "content": [
                {"type": "paragraph", "content": [{"type": "text", "text": "Preview date: " + day}]},
                *before["content"]["content"],
            ]}
            assert review_record == {"comments": before.get("comments", []), "document": prepared_document}
        assert job["result"]["name"] == "审阅稿.zip"
    else:
        assert raw.content == direct_file.content
        tex = raw.content
        assert job["result"]["name"] == "清稿.tex"
    assert b"\\begin{document}" in tex and b"a+b=c" in tex
    assert await live.get("/manuscript") == before


@pytest.mark.asyncio
async def test_manuscript_export_missing_reader_and_closed_format_fail(live):
    await live.error("workbench_manuscript_export", "400", project_id=QA, format="tex", language="reader")
    await live.error("workbench_manuscript_export", "Input should be", project_id=QA, format="html")
    await live.error("workbench_manuscript_export", "Input should be", project_id=QA, format="tex", columns=3)
