"""Prepare a source-only Deep Partner architecture snapshot for public review."""
from pathlib import Path
import json
import os
import shutil
import subprocess
import tarfile

DEST = Path("D:/Development/Deep Partner")
STAGE = Path(__file__).resolve().parents[1] / ".local/source-publication"
WORKBENCH = Path("D:/Development/research-workbench")
DEPLOYMENT = Path(__file__).resolve().parents[1]
SKIP = {".git", "node_modules", "__pycache__", ".venv", "venv", "target", ".pytest_cache",
        ".mypy_cache", ".ruff_cache", ".next", ".local", ".deepcode", ".pipeline",
        "scholar-env", "research-workbench-env", "tmp", "notebooks", "verification",
        "reports", "dist", "ui-dist", "build", "tenant-storage", "data", "logs"}
OMIT_SUFFIX = {".pyc", ".pyo", ".pyd", ".exe", ".dll", ".sqlite", ".sqlite3", ".db",
               ".log", ".pem", ".key", ".p12", ".pfx", ".pdf"}
OMIT_NAMES = {"auth.json", "admin-login.json", "deepcode_config.json", "deepcode_config.json.lock"}
inventory = []


def allowed(path):
    return (not any(part in SKIP or part.endswith("-env") for part in path.parts)
            and path.suffix.lower() not in OMIT_SUFFIX
            and path.name not in OMIT_NAMES
            and (not path.name.startswith(".env") or path.name.endswith(".example")))


def copy_tree(source, destination, exclude=()):
    if not source.exists():
        return
    paths = [source] if source.is_file() else source.rglob("*")
    for path in paths:
        if not path.is_file() or path.is_symlink():
            continue
        rel = Path(path.name) if source.is_file() else path.relative_to(source)
        if not allowed(rel) or any(rel.as_posix().startswith(prefix) for prefix in exclude):
            continue
        target = destination / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, target)


def local_sources():
    for name in ["README.md", "requirements.txt", "server", "web", "unified-ui", "docs", "scripts",
                 "integrations", "licenses", "templates", "vendor", "research", "examples", "search-tools"]:
        if (WORKBENCH / name).is_file():
            copy_tree(WORKBENCH / name, DEST / "workbench")
        else:
            copy_tree(WORKBENCH / name, DEST / "workbench" / name,
                      exclude=("reference-downloads/", "neoread-web/samples/"))
    mcp = WORKBENCH / "mcp-package"
    for name in ["src", "tests", "skill", "tool-manifest.json", "TOOL_REFERENCE.md", "USAGE.md", "PROVENANCE.json"]:
        if (mcp / name).is_dir():
            copy_tree(mcp / name, DEST / "workbench/mcp-package" / name)
        else:
            copy_tree(mcp / name, DEST / "workbench/mcp-package")
    # Tests sometimes use a directory named data for synthetic fixtures.
    copy_tree(WORKBENCH / "tests", DEST / "workbench/tests")
    desktop = Path("D:/Development/电脑答疑/deeptutor-desktop")
    for name in ["src", "ui", "assets", "scripts", "icons", "licenses", "tests", "gen"]:
        copy_tree(desktop / name, DEST / "desktop" / name)
    for path in desktop.iterdir():
        if path.is_file():
            copy_tree(path, DEST / "desktop")
    for name in ["bridge", "docs", "ops", "tests", "tutor-extension", "workbench-search", "quality-skills"]:
        copy_tree(DEPLOYMENT / name, DEST / "deployment" / name)
    for path in DEPLOYMENT.iterdir():
        if path.is_file():
            copy_tree(path, DEST / "deployment")
    copy_tree(DEPLOYMENT / "quality-knowledge", DEST / "deployment/quality-knowledge",
              exclude=("library/", "presentation-sources/"))
    for path in (DEPLOYMENT / "quality-knowledge/presentation-sources").glob("*.py"):
        copy_tree(path, DEST / "deployment/quality-knowledge/presentation-sources")
    copy_tree(Path("C:/Users/DEVELOPER/.codex/skills/deep-partner-research"),
              DEST / "integrations/codex/deep-partner-research")
    native = Path("C:/Users/DEVELOPER/DeepTutor")
    result = subprocess.check_output(["git", "-C", str(native), "ls-files", "-z"])
    for item in result.decode().split("\0"):
        rel = Path(item)
        if item and allowed(rel) and (native / rel).is_file():
            target = DEST / "native/DeepTutor" / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(native / rel, target)
    inventory.append({"component": "native-source-baseline", "source": "HKUDS/DeepTutor",
                      "commit": subprocess.check_output(["git", "-C", str(native), "rev-parse", "HEAD"], text=True).strip(),
                      "overlay": "The running production Python source is applied below."})


REMOTE_EXPORT = r'''
from pathlib import Path
import io,json,os,subprocess,sys,tarfile
SKIP={'__pycache__','node_modules','.git','.venv','venv','data','logs','private','secrets','state','reports','dist','static','artifacts','candidates','site-packages'}
roots=[
('/srv/research-workbench/source/server','workbench/server'),
('/srv/research-workbench/source/tests','workbench/tests'),
('/srv/dify-research/bridge','deployment/bridge'),
('/srv/dify-research/tutor-extension','deployment/tutor-extension'),
('/srv/dify-research/model-wait-policy','deployment/runtime-patches/model-wait-policy'),
('/srv/dify-research/native-terminal-admission','deployment/runtime-patches/native-terminal-admission'),
('/srv/dify-research/native-request-contract','deployment/runtime-patches/native-request-contract'),
('/srv/deeptutor/compat','deployment/deeptutor-compat'),
('/srv/deeptutor/coder-build','cluster/coder-service'),
('/srv/deeptutor/workbench-src','integrations/deeptutor-extension'),
('/srv/tutor-research-compute/app','cluster/research-compute'),
('/srv/tutor-research-compute/README.md','cluster/README.md'),
('/srv/tutor-research-compute/refresh_skill.py','cluster/refresh_skill.py'),
('/srv/deep-partner-admin/admin_gateway.py','deployment/admin/admin_gateway.py')]
with tarfile.open(fileobj=sys.stdout.buffer,mode='w|gz') as archive:
 for source,dest in roots:
  root=Path(source)
  paths=[root] if root.is_file() else root.rglob('*')
  for path in paths:
   if not path.is_file() or path.is_symlink():continue
   rel=Path() if root.is_file() else path.relative_to(root)
   if any(p in SKIP or p.endswith('-env') for p in rel.parts):continue
   if path.suffix in ['.pyc','.log','.tar','.gz','.zip','.sqlite','.sqlite3','.db','.pem','.key']:continue
   if path.name in ['compute-token','trusted-token','token','auth.json','admin-login.json']:continue
   # Runtime packages ship installation metadata but no account configuration.
   archive.add(path,arcname=(Path(dest)/rel).as_posix() if rel.parts else dest,recursive=False)
 # Native code includes mounted production patches, as seen by the real runtime.
 payload=subprocess.check_output(['docker','exec','deeptutor','tar','-czf','-','--exclude=__pycache__',
   '-C','/app','deeptutor','deeptutor_cli','tutor_community','workbench_pages','scripts',
   'deeptutor_registration_gate.py','registration_admin.py','trusted_devices.py',
   'entrypoint.sh','healthcheck.py','start-backend.sh','start-frontend.sh'])
 with tarfile.open(fileobj=io.BytesIO(payload),mode='r:gz') as inner:
  for member in inner:
   if not member.isfile():continue
   member.name='native/DeepTutor/'+member.name
   archive.addfile(member,inner.extractfile(member))
'''


CLUSTER_EXPORT = r'''
from pathlib import Path
import os,sys,tarfile
root=Path('/work/home/cluster_user/research-projects/deeptutor-integration/frontend/src/web')
skip={'node_modules','.next','dist','__pycache__','.git'}
with tarfile.open(fileobj=sys.stdout.buffer,mode='w|gz') as archive:
 for folder,dirs,files in os.walk(root):
  dirs[:]=[d for d in dirs if d not in skip]
  for name in files:
   p=Path(folder)/name
   if name.startswith('.env') and not name.endswith('.example'):continue
   if p.is_symlink():continue
   archive.add(p,arcname='native/DeepTutor/web/'+p.relative_to(root).as_posix(),recursive=False)
'''


def download(host, code, name):
    target = STAGE / name
    command = "sudo -n python3 -" if host == "papers-research" else "/public/software/apps/anaconda3/2023.09/bin/python -"
    with target.open("wb") as output:
        subprocess.run(["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=15", host, command],
                       input=code.encode(), stdout=output, stderr=subprocess.PIPE, check=True, timeout=180)
    with tarfile.open(target) as archive:
        archive.extractall(DEST, filter="data")
    inventory.append({"component": name, "source": host, "archive_bytes": target.stat().st_size})
    print(json.dumps({"received": name, "bytes": target.stat().st_size}), flush=True)


def main():
    STAGE.mkdir(parents=True, exist_ok=True)
    DEST.mkdir(exist_ok=True)
    local_sources()
    print("Local source components copied", flush=True)
    download("papers-research", REMOTE_EXPORT, "production-source.tar.gz")
    download("research-cluster-xh5", CLUSTER_EXPORT, "production-frontend-source.tar.gz")
    (DEST / "docs").mkdir(exist_ok=True)
    (DEST / "docs/source-provenance.json").write_text(
        json.dumps({"snapshot_date": "2026-11-05", "sources": inventory,
                    "excluded": ["account credentials", "private research data", "runtime databases",
                                 "downloaded papers", "virtual environments", "dependency/build caches"]},
                   ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    files = [p for p in DEST.rglob("*") if p.is_file() and ".git" not in p.parts]
    print(json.dumps({"files": len(files), "bytes": sum(p.stat().st_size for p in files)}), flush=True)


if __name__ == "__main__":
    main()
