import copy

import pytest

from conftest import DATA, QA, text_nodes


@pytest.mark.asyncio
async def test_manuscript_full_native_read_and_reversible_changed_save(live):
    original = await live.get("/manuscript")
    received = await live.invoke("workbench_manuscript", project_id=QA)
    assert received["data"] == original
    changed = copy.deepcopy(original)
    changed["title"] = "Independent MCP changed title; synthetic only"
    supplied = copy.deepcopy(changed)
    try:
        saved = (await live.invoke("workbench_manuscript", project_id=QA, action="save", document=changed,
                                   revision=original["revision"], reason="Independent reversible input test"))["data"]
        assert changed == supplied
        assert saved["title"] == changed["title"]
        assert saved["content"] == original["content"]
        assert saved["references"] == original["references"]
        assert saved["revision"] == original["revision"] + 1
        assert await live.get("/manuscript") == saved
        await live.error("workbench_manuscript", "409", project_id=QA, action="save", document=changed)
        assert await live.get("/manuscript") == saved
    finally:
        await live.restore_manuscript(original)


@pytest.mark.asyncio
async def test_manuscript_changed_import_compares_full_native_content_and_upload_bytes(live):
    original = await live.get("/manuscript")
    path = live.root / "independent_import.md"
    path.write_text("# Changed independent fixture\n\nNew input value 17 and preserved units m/s.\n\n$$u=3v$$\n", encoding="utf8")
    try:
        with path.open("rb") as stream:
            response = await live.response("POST", "/manuscript/import", files={"file": (path.name, stream, "text/markdown")})
        assert response.status_code == 200
        direct = response.json()
        mcp = (await live.invoke("workbench_manuscript", project_id=QA, action="import", file_path=str(path)))["data"]
        assert mcp["content"] == direct["content"]
        assert mcp["title"] == direct["title"] == path.stem
        assert "New input value 17" in text_nodes(mcp["content"])
        assert any(n.get("attrs", {}).get("latex") == "u=3v" for n in mcp["content"]["content"])
        asset = (await live.invoke("workbench_manuscript", project_id=QA, action="upload_asset",
                                   file_path=str(DATA / "changed_synthetic.png")))["data"]
        raw = await live.response("GET", asset["src"], project=False)
        assert raw.content == (DATA / "changed_synthetic.png").read_bytes()
    finally:
        await live.restore_manuscript(original)


@pytest.mark.asyncio
async def test_manuscript_missing_revision_and_unavailable_project_are_mcp_errors(live):
    await live.error("workbench_manuscript", "revision", project_id=QA, action="save", document={"content": {"type": "doc"}})
    await live.error("workbench_manuscript", "unavailable", project_id="independent-nonexistent-project")
