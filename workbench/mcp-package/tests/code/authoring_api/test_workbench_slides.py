import copy

import pytest

from conftest import QA


@pytest.mark.asyncio
async def test_slides_full_native_plan_changed_reversible_save_and_real_previews(live):
    original = await live.get("/slides")
    actual = await live.invoke("workbench_slides", project_id=QA)
    assert actual["data"] == original
    changed = copy.deepcopy(original)
    changed["title"] = "Independent changed slide title; synthetic fixture"
    changed["sections"][1]["content"] = "Caller-supplied changed content 23 with preserved units s."
    try:
        actual = await live.invoke("workbench_slides", project_id=QA, action="save", plan=changed)
        assert actual["data"] == {"saved": True}
        assert await live.get("/slides") == changed
    finally:
        restored = await live.response("PUT", "/slides", json=original)
        assert restored.status_code == 200
    for kind, page in [("deck", 1), ("deck", 2), ("beamer-default", 1)]:
        native = await live.response("GET", "/slide-preview", params={"kind": kind, "page": page})
        assert native.status_code == 200
        output = live.root / f"{kind}_{page}.png"
        actual = await live.invoke("workbench_slides", project_id=QA, action="preview", kind=kind, page=page, output_path=str(output))
        assert output.read_bytes() == native.content
        assert actual["artifacts"][0]["path"] == str(output)
        assert native.content.startswith(b"\x89PNG")


@pytest.mark.asyncio
async def test_slides_unconfirmed_generation_and_bad_structure_fail_before_model(live):
    assert (await live.get("/slide-templates"))["confirmation"] is None
    await live.error("workbench_slides", "400", project_id=QA, action="export")
    await live.error("workbench_slides", "400", project_id=QA, action="plan", confirmation_id="independent-invalid", use_native=False, instruction="Changed request")
    await live.error("workbench_slides", "400", project_id=QA, action="save", plan={"sections": "not-a-list"})
    await live.error("workbench_slides", "400", project_id=QA, action="preview", page=0, output_path=str(live.root / "bad-page.png"))
