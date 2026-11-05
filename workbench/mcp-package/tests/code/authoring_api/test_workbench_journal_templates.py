import pytest

from conftest import QA


@pytest.mark.asyncio
async def test_journal_template_discovery_retains_real_native_candidate_identity(live):
    journal = "issn-0008-8846"
    direct = await live.response("POST", "/journal-templates/search", json={"journal": journal})
    assert direct.status_code == 200
    native = direct.json()
    actual = (await live.invoke("workbench_journal_templates", project_id=QA, journal=journal))["data"]
    assert actual["journal"] == native["journal"] == journal
    # Network search can add independently fetched candidates. Every source-supported
    # official candidate established by the independent call must retain all fields.
    for item in native["items"]:
        assert item in actual["items"]
    assert actual["scope"] == native["scope"]
    assert actual["items"]
    assert all(i["source"] and i["url"].startswith("https://") and len(i["id"]) == 24 for i in actual["items"])


@pytest.mark.asyncio
async def test_journal_templates_changed_invalid_selection_and_missing_file_are_errors(live):
    await live.error("workbench_journal_templates", "journal", project_id=QA)
    await live.error("workbench_journal_templates", "400", project_id=QA, action="download", journal="issn-0008-8846", template_id="independent-unselected")
    await live.error("workbench_journal_templates", "404", project_id=QA, action="file", name="independent-missing.zip", output_path=str(live.root / "missing.zip"))
