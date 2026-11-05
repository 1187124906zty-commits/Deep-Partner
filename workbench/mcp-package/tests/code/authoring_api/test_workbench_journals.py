import pytest

from conftest import without_clock


@pytest.mark.asyncio
async def test_journals_generic_catalog_and_language_changed_details_match_source(live):
    native = await live.get("/research/api/journals/search", project=False, params={"q": ""})
    actual = await live.invoke("workbench_journals", query="")
    assert without_clock(actual["data"]) == without_clock(native)
    for kind, language in [("generic-en", "en"), ("generic-zh", "zh-CN")]:
        native = await live.get(f"/research/api/journals/{kind}", project=False)
        actual = await live.invoke("workbench_journals", action="details", journal_id=kind, year=2025)
        assert without_clock(actual["data"]) == without_clock(native)
        assert actual["data"]["language"] == language
        assert actual["data"]["impact_factor"] is None
        assert actual["data"]["quartile"] is None


@pytest.mark.asyncio
async def test_journals_missing_selection_and_short_query_preserve_source_errors(live):
    await live.error("workbench_journals", "journal_id", action="details")
    await live.error("workbench_journals", "400", action="search", query="x")
    await live.error("workbench_journals", "project_id", action="preview")
