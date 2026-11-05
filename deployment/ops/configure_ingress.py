"""Add one specific authenticated adapter route to the existing Tutor site."""
from pathlib import Path
import subprocess

ROOT = Path("/srv/dify-research")
TARGET = "/etc/caddy/deeptutor.caddy"
IMPORT = "    import /etc/caddy/dify-workbench.caddy\n"


def read(path):
    return subprocess.check_output(["sudo", "-n", "cat", path], text=True)


def install(source, target):
    subprocess.run(["sudo", "-n", "install", "-m", "644", str(source), target], check=True)


original = read(TARGET)
module = ROOT / "dify-workbench.caddy"
module.write_text("handle /research/dify/* {\n    reverse_proxy 127.0.0.1:47910\n}\n")
install(module, "/etc/caddy/dify-workbench.caddy")
if IMPORT not in original:
    marker = "    handle /research {"
    if original.count(marker) != 1:
        raise SystemExit("Tutor Caddy layout changed; inspect the current configuration before editing.")
    private = ROOT / "private"
    before = private / "deeptutor.caddy.before"
    if not before.exists():
        before.write_text(original)
        before.chmod(0o600)
    proposed = private / "deeptutor.caddy.proposed"
    proposed.write_text(original.replace(marker, IMPORT + marker, 1))
    top = read("/etc/caddy/Caddyfile")
    marker_top = "import /etc/caddy/deeptutor.caddy"
    if marker_top not in top:
        raise SystemExit("Caddy root import changed")
    trial = private / "Caddyfile.trial"
    trial.write_text(top.replace(marker_top, "import " + str(proposed)))
    subprocess.run(["sudo", "-n", "caddy", "validate", "--config", str(trial), "--adapter", "caddyfile"], check=True)
    if read(TARGET) != original:
        raise SystemExit("Tutor Caddy changed concurrently; original preserved")
    install(proposed, TARGET)
subprocess.run(["sudo", "-n", "caddy", "validate", "--config", "/etc/caddy/Caddyfile"], check=True)
subprocess.run(["sudo", "-n", "systemctl", "reload", "caddy"], check=True)
print("Tutor research/dify route loaded")
