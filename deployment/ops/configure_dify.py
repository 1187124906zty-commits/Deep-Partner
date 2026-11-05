"""Configure the unmodified official Dify release for a small shared server."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import secrets


def configure(root: Path, lock: dict[str, str]):
    docker = root / "upstream" / "docker"
    environment = docker / ".env"
    if environment.exists():
        raise SystemExit("Existing environment retained; use the documented upgrade procedure.")
    values = {}
    for line in (docker / ".env.example").read_text().splitlines():
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            values[key] = value
    for name in ["SECRET_KEY", "DB_PASSWORD", "REDIS_PASSWORD", "QDRANT_API_KEY",
                 "CODE_EXECUTION_API_KEY", "PLUGIN_DAEMON_KEY", "PLUGIN_DIFY_INNER_API_KEY",
                 "DIFY_AGENT_SERVER_SECRET_KEY", "DIFY_AGENT_API_TOKEN",
                 "DIFY_AGENT_LOCAL_SANDBOX_AUTH_TOKEN"]:
        values[name] = secrets.token_hex(32)
    values.update({
        "COMPOSE_PROFILES": "qdrant,postgresql",
        "VECTOR_STORE": "qdrant", "QDRANT_URL": "http://qdrant:6333",
        "ENABLE_COLLABORATION_MODE": "false",
        "NEXT_PUBLIC_ENABLE_AGENT_V2": "false",
        "SERVER_WORKER_AMOUNT": "1", "CELERY_WORKER_AMOUNT": "1",
        "CELERY_AUTO_SCALE": "false", "SQLALCHEMY_POOL_SIZE": "5",
        "SQLALCHEMY_MAX_OVERFLOW": "5", "POSTGRES_MAX_CONNECTIONS": "60",
        "POSTGRES_SHARED_BUFFERS": "64MB", "POSTGRES_EFFECTIVE_CACHE_SIZE": "512MB",
        "POSTGRES_MAINTENANCE_WORK_MEM": "32MB", "POSTGRES_WORK_MEM": "2MB",
        "EXPOSE_NGINX_PORT": "8088", "EXPOSE_NGINX_SSL_PORT": "8448",
        "SANDBOX_API_KEY": values["CODE_EXECUTION_API_KEY"],
        "NEXT_TELEMETRY_DISABLED": "1", "CHECK_UPDATE_URL": "",
    })
    values["CELERY_BROKER_URL"] = "redis://:" + values["REDIS_PASSWORD"] + "@redis:6379/1"
    environment.write_text("\n".join(f"{k}={v}" for k, v in values.items()) + "\n")
    environment.chmod(0o600)
    overrides = {
        "api": ("langgenius/dify-api:1.18.0", "768m"),
        "worker": ("langgenius/dify-api:1.18.0", "768m"),
        "worker_beat": ("langgenius/dify-api:1.18.0", "384m"),
        "web": ("langgenius/dify-web:1.18.0", "384m"),
        "plugin_daemon": ("langgenius/dify-plugin-daemon:0.6.10-local", "256m"),
        "db_postgres": ("postgres:15-alpine", "256m"),
        "redis": ("redis:6-alpine", "128m"),
        "qdrant": ("langgenius/qdrant:v1.8.3", "192m"),
        "sandbox": ("langgenius/dify-sandbox:0.2.15", "128m"),
        "ssrf_proxy": ("ubuntu/squid:latest", "128m"),
        "nginx": ("nginx:latest", "96m"),
        "init_permissions": ("busybox:latest", "32m"),
    }
    lines = ["name: dify-research", "services:"]
    for service, (image, memory) in overrides.items():
        lines.extend([f"  {service}:", f"    image: {image}@{lock[image]}",
                      f"    mem_limit: {memory}", "    logging:", "      driver: json-file",
                      "      options:", "        max-size: 10m", '        max-file: "3"'])
        if service in {"api", "worker"}:
            lines.extend(["    depends_on:", "      agent_backend:", "        required: false"])
        if service == "web":
            lines.extend(["    environment:", "      NODE_OPTIONS: --max-old-space-size=256",
                          '      NEXT_PUBLIC_ENABLE_AGENT_V2: "false"'])
        if service == "plugin_daemon":
            lines.append("    ports: !reset []")
        if service == "nginx":
            lines.extend(["    ports: !override", '      - "127.0.0.1:8088:80"'])
    for service in ["agent_backend", "local_sandbox", "agent_ssrf_proxy"]:
        lines.extend([f"  {service}:", "    profiles: [agent-v2]"])
    (root / "compose.override.yaml").write_text("\n".join(lines) + "\n")
    print(json.dumps({"configured": True, "release": "1.18.0", "mode": "workflow",
                      "bind": "127.0.0.1:8088", "preserves_main_agent": "DeepTutor"}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--lock", type=Path, required=True)
    args = parser.parse_args()
    configure(args.root, json.loads(args.lock.read_text()))
