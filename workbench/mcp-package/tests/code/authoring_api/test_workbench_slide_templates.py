import pytest

from conftest import QA


@pytest.mark.asyncio
async def test_slide_templates_full_native_manifest_and_changed_selection(live):
    native = await live.get("/slide-templates")
    actual = await live.invoke("workbench_slide_templates", project_id=QA)
    assert actual["data"] == native
    assert {"beamer-default", "metropolis"} <= {t["id"] for t in native["templates"]}
    original = native["selected"]
    assert native["confirmation"] is None, "Assigned fixture is deliberately unconfirmed"
    try:
        for choice in ["beamer-default", "metropolis"]:
            source = await live.response("PUT", "/slide-template", json={"template": choice})
            assert source.status_code == 200
            actual = await live.invoke("workbench_slide_templates", project_id=QA, action="select", template=choice)
            assert actual["data"] == source.json() == {"selected": choice}
            assert (await live.get("/slide-templates"))["selected"] == choice
    finally:
        restored = await live.response("PUT", "/slide-template", json={"template": original})
        assert restored.status_code == 200


@pytest.mark.asyncio
async def test_slide_templates_missing_upload_and_builtin_roles_are_errors(live):
    await live.error("workbench_slide_templates", "file_path", project_id=QA, action="upload")
    await live.error("workbench_slide_templates", "400", project_id=QA, action="roles", template="beamer-default", roles={"cover": 2})
    native = await live.response("POST", "/slide-templates/independent-missing-template/prepare")
    assert native.status_code == 400
    await live.error("workbench_slide_templates", "400", project_id=QA, action="prepare", template="independent-missing-template")
