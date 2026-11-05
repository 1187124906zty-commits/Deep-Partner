import struct

import pytest


@pytest.mark.asyncio
async def test_manuscript_templates_exact_catalog_and_changed_binary_kinds(live):
    native = await live.get("/research/api/manuscript-templates", project=False)
    actual = await live.invoke("workbench_manuscript_templates")
    assert actual["data"] == native
    assert {"generic-en", "generic-zh", "elsevier"} <= {t["id"] for t in native["templates"]}
    for action, kind, suffix in [("source", "generic-en", "docx"), ("preview", "elsevier", "png")]:
        source = await live.response("GET", f"/research/api/manuscript-template-{action}/{kind}", project=False)
        assert source.status_code == 200
        seen = []
        for i in range(2):
            target = live.root / f"{kind}_{action}_{i}.{suffix}"
            result = await live.invoke("workbench_manuscript_templates", action=action, kind=kind, output_path=str(target))
            assert target.read_bytes() == source.content
            artifact = result["artifacts"][0]
            assert artifact["path"] == str(target)
            assert artifact["bytes"] == len(source.content)
            assert artifact["path"] not in seen
            seen.append(artifact["path"])
        if suffix == "docx":
            assert source.content.startswith(b"PK")
        else:
            assert source.content.startswith(b"\x89PNG")
            assert min(struct.unpack(">II", source.content[16:24])) > 0


@pytest.mark.asyncio
async def test_manuscript_templates_missing_kind_and_native_unknown_are_errors(live):
    await live.error("workbench_manuscript_templates", "kind", action="source", output_path=str(live.root / "missing.docx"))
    await live.error("workbench_manuscript_templates", "404", action="preview", kind="independent-missing-template", output_path=str(live.root / "unknown.png"))
