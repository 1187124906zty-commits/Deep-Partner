"""Load the tool through DeepTutor's public extension entry points."""
import json
from pathlib import Path
import subprocess

ROOT = Path("/srv/dify-research")
TARGET = "/srv/deeptutor/compose.override.yaml"
site_packages = subprocess.check_output(["docker", "exec", "deeptutor", "python", "-c",
    "import site;print(site.getsitepackages()[0])"], text=True).strip()
if not site_packages.startswith("/usr/local/lib/python") or not site_packages.endswith("/site-packages"):
    raise SystemExit("Native Python installation changed; inspect its standard plugin install location.")
override = {
    "services": {"deeptutor": {
        "volumes": [str(ROOT / "tutor-extension") + ":/opt/dify-delivery:ro",
                    str(ROOT / "tutor-extension/dify_delivery.pth") + ":" + site_packages + "/dify_delivery.pth:ro"],
        "environment": {"DIFY_WORKBENCH_BRIDGE_URL": "https://tutor.example.invalid/research/dify"},
    }}
}
exists = subprocess.run(["sudo", "-n", "test", "-f", TARGET]).returncode == 0
if exists:
    current = json.loads(subprocess.check_output(["sudo", "-n", "cat", TARGET], text=True))
    owned = (set(current.get("services", {})) == {"deeptutor"} and
             str(ROOT / "tutor-extension") + ":/opt/dify-delivery:ro" in current["services"]["deeptutor"].get("volumes", []) and
             set(current["services"]["deeptutor"].get("environment", {})) <= {"PYTHONPATH", "DIFY_WORKBENCH_BRIDGE_URL"})
    if current != override and not owned:
        raise SystemExit("Existing native override belongs to another change; merge after inspection.")
stage = ROOT / "tutor.override.json"
stage.write_text(json.dumps(override, indent=2))
subprocess.run(["sudo", "-n", "install", "-m", "644", str(stage), TARGET], check=True)
compose = ["sudo", "-n", "docker", "compose", "-f", "/srv/deeptutor/compose.yaml", "-f", TARGET]
subprocess.run(compose + ["config", "--quiet"], check=True)
subprocess.run(compose + ["up", "-d", "--no-deps", "deeptutor"], check=True)
print("Native DeepTutor extension configured; existing base Compose retained")
