import io
import zipfile

import pytest

from conftest import QA


@pytest.mark.asyncio
@pytest.mark.parametrize("area,name,member", [("manuscript", "清稿.docx", "word/document.xml"),
                                            ("manuscript", "清稿.pdf", None),
                                            ("slides", "研究汇报.pptx", "ppt/presentation.xml"),
                                            ("slides", "研究汇报.pdf", None)])
async def test_export_download_repeated_artifacts_equal_every_native_byte(live, area, name, member):
    native = await live.response("GET", "/download", params={"area": area, "name": name})
    assert native.status_code == 200
    files = []
    for index in range(2):
        output = live.root / f"artifact_{index}{name[name.rfind('.'):]}"
        actual = await live.invoke("workbench_export_download", project_id=QA, area=area, name=name, output_path=str(output))
        assert output.read_bytes() == native.content
        assert actual["data"]["bytes"] == len(native.content)
        assert actual["artifacts"][0]["path"] == str(output)
        files.append(actual["artifacts"][0]["path"])
    assert len(set(files)) == 2
    if member:
        with zipfile.ZipFile(io.BytesIO(native.content)) as archive:
            assert member in archive.namelist()
            assert archive.testzip() is None
            if area == "manuscript":
                assert b"Synthetic" in archive.read(member)
            else:
                pages = [p for p in archive.namelist() if p.startswith("ppt/slides/slide") and p.endswith(".xml")]
                assert len(pages) == 3
    else:
        assert native.content.startswith(b"%PDF-") and b"%%EOF" in native.content[-200:]


@pytest.mark.asyncio
async def test_export_download_unknown_name_and_invalid_area_are_errors(live):
    await live.error("workbench_export_download", "404", project_id=QA, name="missing-independent.docx", output_path=str(live.root / "absent.docx"))
    await live.error("workbench_export_download", "Input should be", project_id=QA, area="private", name="anything", output_path=str(live.root / "invalid.bin"))
