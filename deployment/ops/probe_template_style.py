"""Exercise the existing text replacement helper on an isolated styled fixture."""
from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.oxml.xmlchemy import OxmlElement
from pptx.util import Inches, Pt


def snapshot(shape):
    return [{"level": p.level, "runs": [
        {"text": r.text, "font": r.font.name,
         "size_pt": r.font.size.pt if r.font.size else None,
         "bold": r.font.bold, "italic": r.font.italic,
         "east_asian_font": (r._r.rPr.find("{http://schemas.openxmlformats.org/drawingml/2006/main}ea").get("typeface")
                             if r._r.rPr is not None and r._r.rPr.find("{http://schemas.openxmlformats.org/drawingml/2006/main}ea") is not None else None)}
        for r in p.runs]} for p in shape.text_frame.paragraphs]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--helper", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    spec = importlib.util.spec_from_file_location("existing_template_tools", args.helper)
    helper = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helper)
    presentation = Presentation()
    slide = presentation.slides.add_slide(presentation.slide_layouts[6])
    box = slide.shapes.add_textbox(Inches(1), Inches(1), Inches(6), Inches(3))
    first = box.text_frame.paragraphs[0]
    run = first.add_run()
    run.text = "English 中文"
    run.font.name = "Arial"
    run.font.size = Pt(28)
    run.font.bold = True
    run.font.color.rgb = RGBColor.from_string("123456")
    east_asian = OxmlElement("a:ea")
    east_asian.set("typeface", "Microsoft YaHei")
    run._r.get_or_add_rPr().append(east_asian)
    second = box.text_frame.add_paragraph()
    second.level = 1
    detail = second.add_run()
    detail.text = "Secondary evidence"
    detail.font.name = "Times New Roman"
    detail.font.size = Pt(18)
    detail.font.italic = True
    before = snapshot(box)
    helper.set_text_preserve_style(box, "Replacement 中文\nSecondary evidence")
    after = snapshot(box)
    checks = {
        "first_latin_font_preserved": after[0]["runs"][0]["font"] == before[0]["runs"][0]["font"],
        "paragraph_count_preserved": len(after) == len(before),
        "second_level_preserved": len(after) > 1 and after[1]["level"] == before[1]["level"],
        "east_asian_font_preserved": after[0]["runs"][0]["east_asian_font"] == "Microsoft YaHei",
        "secondary_italic_preserved": any(r["italic"] is True for p in after for r in p["runs"]),
    }
    report = {"helper": str(args.helper.resolve()), "before": before, "after": after,
              "checks": checks, "strict_template_preservation": all(checks.values()),
              "scope": "An isolated synthetic mixed-script/multi-paragraph fixture; structural check only, no Office rendering or user template.",
              "interpretation": "This helper preserves selected properties from one run. It is insufficient as the sole implementation of strict template fidelity."}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf8")
    print(json.dumps({"checks": checks, "strict_template_preservation": report["strict_template_preservation"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
