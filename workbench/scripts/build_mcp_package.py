"""Build the explicit recipient package from the independently verified modules."""
import hashlib
import json
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[1] / "mcp-package"
FILES = ["USAGE.md", "TOOL_REFERENCE.md", "PROVENANCE.json", "skill/SKILL.md",
         "src/project_mcp.py", "src/client.py", "src/workbench_auth.py", "src/requirements.txt",
         "src/tools/workspace_api.py", "src/tools/authoring_api.py"]


def main():
    destination = ROOT / "dist/research-workbench-mcp.zip"
    destination.parent.mkdir(parents=True, exist_ok=True)
    files = {}
    with zipfile.ZipFile(destination, "w", zipfile.ZIP_DEFLATED) as archive:
        for name in FILES:
            data = (ROOT / name).read_bytes()
            assert data, name
            archive.writestr("research-workbench-mcp/" + name, data)
            files[name] = {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}
    with zipfile.ZipFile(destination) as archive:
        assert archive.testzip() is None
        assert len(archive.namelist()) == len(FILES)
    report = {"archive": str(destination.resolve()), "archive_sha256": hashlib.sha256(destination.read_bytes()).hexdigest(),
              "bytes": destination.stat().st_size, "top_level": "research-workbench-mcp", "files": files}
    (ROOT / "reports/package-inventory.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf8")
    print(json.dumps({k: v for k, v in report.items() if k != "files"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
