import copy

import pytest

from conftest import QA


@pytest.mark.asyncio
async def test_references_full_native_records_and_case_changed_duplicate_add(live):
    native = await live.get("/references")
    result = await live.invoke("workbench_references", project_id=QA)
    assert result["data"] == native
    assert native["items"]
    entry = copy.deepcopy(native["items"][0])
    entry["doi"] = entry["doi"].upper()
    expected = await live.response("POST", "/references", json={"entry": entry, "revision": native["revision"]})
    assert expected.status_code == 200
    actual = await live.invoke("workbench_references", project_id=QA, action="add", entry=entry, revision=native["revision"])
    assert actual["data"] == expected.json()
    assert actual["data"]["reference"]["id"] == native["items"][0]["id"]
    assert await live.get("/references") == native


@pytest.mark.asyncio
async def test_references_missing_source_stale_revision_and_unselected_recommendation(live):
    native = await live.get("/references")
    await live.error("workbench_references", "400", project_id=QA, action="add", entry={"title": "Incomplete fixture"}, revision=native["revision"])
    await live.error("workbench_references", "400", project_id=QA, action="add", entry=native["items"][0], revision=-1)
    await live.error("workbench_references", "reference_id", project_id=QA, action="related")
    await live.error("workbench_references", "400", project_id=QA, action="recommend", reference_id="missing-independent-reference", newest=True, query="changed source words")
    assert await live.get("/references") == native
