import base64

import pytest

from conftest import DATA, IMAGE, QA


@pytest.mark.asyncio
async def test_image_review_corrected_native_draft_and_changed_annotations(live):
    for index, filename in enumerate(["synthetic.png", "changed_synthetic.png"]):
        instruction = f"Independent synthetic draft review {index}; retain supplied source and marks."
        crop = {"x": index, "y": 2, "width": 8, "height": 8}
        annotations = [{"type": "rectangle", "x": 1 + index, "y": 2, "width": 3, "height": 4, "label": "Synthetic crop"}]
        image = DATA / filename
        payload = {"path": IMAGE, "image": "data:image/png;base64," + base64.b64encode(image.read_bytes()).decode(),
                   "instruction": instruction, "plot_program": "", "compute_program": "", "crop": crop,
                   "annotations": annotations, "send": False}
        native = await live.response("POST", "/image-review", json=payload)
        assert native.status_code == 200
        direct = native.json()
        actual = (await live.invoke("workbench_image_review", project_id=QA, path=IMAGE, image_path=str(image),
                                    instruction=instruction, crop=crop, annotations=annotations, send=False))["data"]
        assert live.outbound[-1]["json"] == payload
        assert set(actual) == set(direct) == {"prepared", "id", "prompt", "processed_at"}
        assert actual["prepared"] is direct["prepared"] is True
        assert actual["prompt"] == direct["prompt"]
        assert instruction in actual["prompt"]
        assert actual["id"] != direct["id"]
        context = await live.get("/image-context", params={"path": IMAGE})
        assert context["last_request"] == instruction
        assert context["plot_program"] == context["compute_program"] == ""


@pytest.mark.asyncio
async def test_image_review_native_blank_instruction_and_missing_local_image_fail(live):
    await live.error("workbench_image_review", "400", project_id=QA, path=IMAGE, image_path=str(DATA / "synthetic.png"), instruction=" ", send=False)
    await live.error("workbench_image_review", "No such file", project_id=QA, path=IMAGE, image_path=str(live.root / "missing.png"), instruction="Synthetic", send=False)
