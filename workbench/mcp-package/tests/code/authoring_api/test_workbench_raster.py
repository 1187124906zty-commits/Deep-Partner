import base64

import pytest

from conftest import DATA, IMAGE, QA, png_rgb


@pytest.mark.asyncio
async def test_raster_every_changed_native_pixel_and_timestamp_conflict(live):
    original = await live.response("GET", "/file", params={"path": IMAGE})
    assert original.status_code == 200
    current = await live.get("/image-context", params={"path": IMAGE})
    original_path = live.root / "restore_original.png"
    original_path.write_bytes(original.content)
    try:
        for filename in ["synthetic.png", "changed_synthetic.png"]:
            image = DATA / filename
            native_payload = {"path": IMAGE, "image": "data:image/png;base64," + base64.b64encode(image.read_bytes()).decode(),
                              "expected_modified": current["modified"]}
            native = await live.response("POST", "/image/save", json=native_payload)
            assert native.status_code == 200
            saved_native = await live.response("GET", "/file", params={"path": IMAGE})
            current = await live.get("/image-context", params={"path": IMAGE})
            mcp = await live.invoke("workbench_raster", project_id=QA, path=IMAGE, image_path=str(image), expected_modified=current["modified"])
            assert mcp["data"]["saved"] is True
            actual = await live.response("GET", "/file", params={"path": IMAGE})
            assert actual.content == saved_native.content
            assert png_rgb(actual.content) == png_rgb(image.read_bytes())
            current = await live.get("/image-context", params={"path": IMAGE})
            assert current["modified"] == mcp["data"]["modified"]
        await live.error("workbench_raster", "409", project_id=QA, path=IMAGE, image_path=str(DATA / "synthetic.png"), expected_modified=0)
        unchanged = await live.response("GET", "/file", params={"path": IMAGE})
        assert unchanged.content == actual.content
    finally:
        restored = await live.invoke("workbench_raster", project_id=QA, path=IMAGE, image_path=str(original_path))
        assert restored["data"]["saved"] is True
        final = await live.response("GET", "/file", params={"path": IMAGE})
        assert png_rgb(final.content) == png_rgb(original.content)


@pytest.mark.asyncio
async def test_raster_missing_remote_image_preserves_source_error(live):
    await live.error("workbench_raster", "400", project_id=QA, path="results/missing-independent.png", image_path=str(DATA / "synthetic.png"))
