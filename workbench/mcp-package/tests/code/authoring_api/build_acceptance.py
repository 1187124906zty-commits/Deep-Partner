"""Build source-backed real-stdio cases; no inventory is inferred from server discovery."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

PACKAGE = Path(__file__).resolve().parents[3]
QA = "4959b9a67b324c0eb69ab9c67ee897cb"
IMAGE = "results/synthetic.png"
DATA = PACKAGE / "notebooks/authoring_flows/data"
REQUIRED = {
    "workbench_manuscript": ["project_id"],
    "workbench_manuscript_templates": [],
    "workbench_manuscript_export": ["project_id", "format"],
    "workbench_export_download": ["project_id", "name", "output_path"],
    "workbench_references": ["project_id"],
    "workbench_journals": [],
    "workbench_journal_templates": ["project_id"],
    "workbench_figure": ["project_id", "path"],
    "workbench_figure_chat": ["project_id", "path"],
    "workbench_image_review": ["project_id", "path", "image_path", "instruction"],
    "workbench_raster": ["project_id", "path", "image_path"],
    "workbench_slide_templates": ["project_id"],
    "workbench_slides": ["project_id"],
}


def build(output_root):
    cases = []

    def positive(name, tool, arguments, expected=None, artifact=None):
        case = {"name": name, "tool": tool, "arguments": arguments, "required_inputs": REQUIRED[tool]}
        if expected is not None:
            case["expected_subset"] = expected
        if artifact:
            case.update(min_artifacts=1, artifact_root=str(output_root), unique_artifacts=True)
        cases.append(case)

    def error(name, tool, arguments, contains):
        cases.append({"name": name, "tool": tool, "arguments": arguments,
                      "required_inputs": REQUIRED[tool], "error_contains": contains})

    catalog = json.loads((PACKAGE / "notebooks/authoring_flows/outputs/005_manuscript_template_catalog.json").read_text(encoding="utf8"))
    positive("authoring-manuscript-source-read", "workbench_manuscript", {"project_id": QA},
             {"data": {"title": "Synthetic API reference document", "template": "generic-en"}})
    positive("authoring-source-template-catalog", "workbench_manuscript_templates", {},
             {"data": {"templates": [{"id": row["id"]} for row in catalog["templates"]]}})
    for i in range(2):
        positive(f"authoring-template-preview-{i}", "workbench_manuscript_templates",
                 {"action": "preview", "kind": "elsevier", "output_path": str(output_root / f"template-{i}.png")}, artifact=True)
    positive("authoring-manuscript-source-export-job", "workbench_manuscript_export",
             {"project_id": QA, "format": "tex", "language": "source", "columns": 1},
             {"message": "Manuscript export submitted; poll workbench_jobs", "artifacts": [],
              "reference": f"https://tutor.example.invalid/research/api/projects/{QA}/manuscript/export"})
    for i, (area, name) in enumerate([("manuscript", "清稿.docx"), ("manuscript", "清稿.docx"), ("slides", "研究汇报.pptx")]):
        positive(f"authoring-original-export-{i}", "workbench_export_download",
                 {"project_id": QA, "area": area, "name": name, "output_path": str(output_root / f"export-{i}{Path(name).suffix}")}, artifact=True)
    positive("authoring-native-reference-records", "workbench_references", {"project_id": QA},
             {"data": {"items": [{"id": "ref-69627e486aa744bd", "doi": "10.1016/j.cemconres.2011.04.001"}]}})
    positive("authoring-generic-journal-source", "workbench_journals", {"action": "details", "journal_id": "generic-zh"},
             {"data": {"id": "generic-zh", "language": "zh-CN", "generic": True, "impact_factor": None, "quartile": None}})
    positive("authoring-official-template-discovery", "workbench_journal_templates", {"project_id": QA, "journal": "issn-0008-8846"},
             {"data": {"journal": "issn-0008-8846", "scope": "官方作者投稿模板；出版社出版后的卷期、页码和成品排版另行处理。"}})
    positive("authoring-unregistered-figure-state", "workbench_figure", {"project_id": QA, "path": IMAGE},
             {"data": {"ready": False, "reason": "此图尚未关联可编辑绘图对象", "kind": "raster"}})
    positive("authoring-native-image-history", "workbench_figure_chat", {"project_id": QA, "path": IMAGE}, {"data": {"messages": []}})
    for i, filename in enumerate(["synthetic.png", "changed_synthetic.png"]):
        positive(f"authoring-prepared-review-{i}", "workbench_image_review",
                 {"project_id": QA, "path": IMAGE, "image_path": str(DATA / filename),
                  "instruction": f"Independent stdio synthetic draft {i}; preserve native metadata.", "send": False}, {"data": {"prepared": True}})
        positive(f"authoring-raster-changed-pixels-{i}", "workbench_raster",
                 {"project_id": QA, "path": IMAGE, "image_path": str(DATA / filename)}, {"data": {"saved": True}})
    positive("authoring-private-template-catalog", "workbench_slide_templates", {"project_id": QA},
             {"data": {"selected": "metropolis", "confirmation": None}})
    positive("authoring-editable-slide-plan", "workbench_slides", {"project_id": QA},
             {"data": {"title": "Synthetic authoring API fixture", "audience_profile": "group", "visual_template": "beamer-default"}})
    for i in range(2):
        positive(f"authoring-rendered-slide-preview-{i}", "workbench_slides",
                 {"project_id": QA, "action": "preview", "kind": "deck", "page": i + 1,
                  "output_path": str(output_root / f"slide-{i}.png")}, artifact=True)
    error("authoring-manuscript-required-revision", "workbench_manuscript", {"project_id": QA, "action": "save", "document": {"content": {"type": "doc"}}}, "revision")
    error("authoring-template-native-missing", "workbench_manuscript_templates", {"action": "source", "kind": "independent-missing", "output_path": str(output_root / "missing.docx")}, "404")
    error("authoring-export-closed-format", "workbench_manuscript_export", {"project_id": QA, "format": "html"}, "Input should be")
    error("authoring-export-missing-file", "workbench_export_download", {"project_id": QA, "name": "independent-absent.docx", "output_path": str(output_root / "missing-export.docx")}, "404")
    error("authoring-reference-requires-identity", "workbench_references", {"project_id": QA, "action": "related"}, "reference_id")
    error("authoring-journal-source-short-query", "workbench_journals", {"query": "x"}, "400")
    error("authoring-template-requires-journal", "workbench_journal_templates", {"project_id": QA}, "journal")
    error("authoring-figure-native-registry-required", "workbench_figure", {"project_id": QA, "path": IMAGE, "action": "preview", "revision": 0, "changes": {}}, "400")
    error("authoring-image-session-not-associated", "workbench_figure_chat", {"project_id": QA, "path": IMAGE, "action": "session", "session_id": "independent-unassociated"}, "403")
    error("authoring-review-blank-instruction", "workbench_image_review", {"project_id": QA, "path": IMAGE, "image_path": str(DATA / "synthetic.png"), "instruction": " ", "send": False}, "400")
    error("authoring-raster-timestamp-conflict", "workbench_raster", {"project_id": QA, "path": IMAGE, "image_path": str(DATA / "synthetic.png"), "expected_modified": 0}, "409")
    error("authoring-builtin-template-roles-fixed", "workbench_slide_templates", {"project_id": QA, "action": "roles", "template": "beamer-default", "roles": {"cover": 2}}, "400")
    error("authoring-no-implicit-slide-confirmation", "workbench_slides", {"project_id": QA, "action": "export"}, "400")
    return cases


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--label", default="development")
    args = parser.parse_args()
    root = (PACKAGE / "tests/results/authoring_api/stdio" / args.label).resolve()
    root.mkdir(parents=True, exist_ok=True)
    cases = build(root)
    target = PACKAGE / "reports/mcp-acceptance-authoring_api.json"
    target.write_text(json.dumps(cases, indent=2, ensure_ascii=False), encoding="utf8")
    expected = PACKAGE / "tests/results/authoring_api/expected-tools.json"
    expected.write_text(json.dumps(list(REQUIRED), indent=2), encoding="utf8")
    print(json.dumps({"cases": len(cases), "positive_tools": len({c["tool"] for c in cases if "error_contains" not in c}),
                      "case_path": str(target), "expected_path": str(expected)}))
