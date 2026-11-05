"""Reuse the current workbench runtime without rebuilding or editing its source."""
import json
from pathlib import Path
import subprocess

ROOT = Path("/srv/dify-research")
runtime = json.loads(subprocess.check_output(["docker", "inspect", "research-workbench"]))[0]["Image"]
(ROOT / "state").mkdir(mode=0o700, exist_ok=True)
service = {
    "image": runtime, "pull_policy": "never", "container_name": "dify-workbench-bridge",
    "restart": "unless-stopped", "network_mode": "host",
    "entrypoint": ["python"],
    "command": ["-m", "uvicorn", "app:app", "--app-dir", "/opt/dify-bridge", "--host", "127.0.0.1", "--port", "47910"],
    "volumes": [str(ROOT / "bridge") + ":/opt/dify-bridge:ro", str(ROOT / "state") + ":/state",
                str(ROOT / "private/workflow-key") + ":/run/secrets/workflow-key:ro"],
    "environment": {"PYTHONUNBUFFERED": "1", "PUBLIC_ORIGIN": "https://tutor.example.invalid"},
    "mem_limit": "192m", "cpus": 0.5,
    "logging": {"driver": "json-file", "options": {"max-size": "10m", "max-file": "3"}},
    "healthcheck": {"test": ["CMD", "python", "-c", "import urllib.request;urllib.request.urlopen('http://127.0.0.1:47910/health',timeout=5).read()"],
                    "interval": "30s", "timeout": "10s", "retries": 3, "start_period": "20s"},
}
(ROOT / "bridge.compose.json").write_text(json.dumps({"name": "dify-workbench-bridge", "services": {"bridge": service}}, indent=2))
print(json.dumps({"runtime_image": runtime, "listen": "127.0.0.1:47910"}))
