#!/usr/bin/env bash
set -euo pipefail
umask 077
task_root=/srv/dify-research
backup_dir="$task_root/private/backups/$(date -u +%Y%m%dT%H%M%SZ)"
mkdir -p "$backup_dir"
docker exec dify-research-db_postgres-1 pg_dump -U postgres -d dify -Fc > "$backup_dir/dify.dump"
docker exec dify-research-db_postgres-1 pg_dump -U postgres -d dify_plugin -Fc > "$backup_dir/dify_plugin.dump"
python3 - "$task_root/state/deliveries.sqlite3" "$backup_dir/deliveries.sqlite3" <<'PY'
import sqlite3,sys
with sqlite3.connect(sys.argv[1]) as source, sqlite3.connect(sys.argv[2]) as target:
    source.backup(target)
PY

python3 - /srv/deeptutor/data/research-workbench/workbench.sqlite3 "$backup_dir/workbench.sqlite3" <<'PY'
import sqlite3,sys
with sqlite3.connect(sys.argv[1]) as source, sqlite3.connect(sys.argv[2]) as target:
    source.backup(target)
PY
tar -C "$task_root" -czf "$backup_dir/config-and-storage.tar.gz" \
  upstream/docker/.env upstream/docker/volumes/app/storage \
  compose.override.yaml images.lock.json app.json research-delivery.dsl.json \
  private/admin-login.json private/workflow-key bridge tutor-extension ops dify-workbench.caddy

# App metadata and credentials must travel together for a usable workflow restore.
extra_paths=()
for task_path in web-reader-app.json evidence-app.json event-app.json schedule-app.json mcp-registration.json \
  private/mcp-key private/web-reader-key private/evidence-key private/automation-config.json tenant-storage; do
  if [[ -e "$task_root/$task_path" ]]; then extra_paths+=("$task_path"); fi
done
if (( ${#extra_paths[@]} )); then
  tar -C "$task_root" -czf "$backup_dir/extension-state.tar.gz" "${extra_paths[@]}"
fi
if [[ -f /srv/deeptutor/data/research-workbench/download-workers.json ]]; then
  cp /srv/deeptutor/data/research-workbench/download-workers.json "$backup_dir/download-workers.json"
fi
cat > "$backup_dir/COVERAGE.txt" <<'EOF'
Dify databases, application files/configuration/credentials, adapter state,
workbench metadata and quota policies, and download-device registration.
This is not a full backup of native accounts, source knowledge bases, project
files or cluster objects. Full user-data recovery needs the separate data backup.
EOF
test -s "$backup_dir/dify.dump"
test -s "$backup_dir/dify_plugin.dump"
printf '%s\n' "$backup_dir"
