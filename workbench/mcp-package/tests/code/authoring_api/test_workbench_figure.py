import pytest

from conftest import IMAGE, QA


@pytest.mark.asyncio
async def test_figure_native_raster_state_and_composed_context_are_exact(live):
    native = await live.get("/figure", params={"path": IMAGE, "edit_session": False})
    actual = await live.invoke("workbench_figure", project_id=QA, path=IMAGE)
    assert actual["data"] == native == {"ready": False, "reason": "此图尚未关联可编辑绘图对象", "kind": "raster"}
    context = await live.get("/image-context", params={"path": IMAGE})
    actual = await live.invoke("workbench_figure", project_id=QA, path=IMAGE, start_edit_session=True, include_context=True)
    assert actual["data"] == {"figure": native, "context": context}
    assert (context["width"], context["height"]) == (16, 16)
    assert context["path"] == IMAGE


@pytest.mark.asyncio
async def test_figure_unregistered_edits_and_missing_revision_fail_as_native(live):
    await live.error("workbench_figure", "revision", project_id=QA, path=IMAGE, action="save", changes={})
    for action in ["preview", "save"]:
        changes = {"figure": {"font_size": 17}, "objects": {}}
        source = await live.response("POST", "/figure/" + action, json={"path": IMAGE, "revision": 0, "changes": changes, "edit_session": "", "reason": "synthetic", "autosave": True})
        assert source.status_code == 400
        await live.error("workbench_figure", "400", project_id=QA, path=IMAGE, action=action, revision=0, changes=changes, autosave=True, reason="synthetic")
