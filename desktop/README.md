# DeepPartner 0.4

Windows x64 desktop host for the shared DeepTutor research UI. The frontend in `ui-dist/` is embedded in the executable at build time. The installed application never automatically replaces its frontend with a remote webpage. Frontend and native upgrades use a manually installed release; compatible server capabilities remain server data.

## Build and run

```powershell
& scripts/package-native.ps1 -Action submit
& scripts/package-native.ps1 -Action status
& scripts/package-native.ps1 -Action fetch
```

The packaging entry submits the Windows compilation and NSIS packaging to the existing Slurm cluster. Toolchains, dependencies and compilation caches stay on the cluster; fetch downloads the finished binaries for verification and release. The build requires the actual shared frontend and refuses to package an empty UI. WebView2 Runtime is required on the target Windows computer. The installer packages `Deep partner.exe`, `dp.exe` and font licenses into the existing per-user install location. It does not change the user's PATH. Run dp by its full installed path or add that folder to PATH yourself.

The original egui implementation remains available through `cargo run --features legacy-egui --bin deep-partner-legacy`. The dp/core build has no default egui, wgpu or Tauri feature.

## Native session and proxy

Rust owns the remote cookie jar. A random loopback port serves the bundled UI and authenticated API/WebSocket proxy. A one-time, five-minute local bootstrap issues an HttpOnly SameSite=Strict local cookie; remote cookies are never sent to JavaScript or copied to local response cookies. API/WS requests require this local session and exact local Origin (same-origin browser GET/HEAD may prove the origin through Referer). The host checks Host and binds only 127.0.0.1. Upstream redirects are not followed with credentials.

When a device credential already exists in Windows DPAPI storage, startup attempts the existing quick-login endpoint before the frontend checks authentication. The attempt has a seven-second deadline; offline or revoked credentials fall back to the normal login screen. A new profile does not make this request or create a trusted-device record.

Routes include `/api/*`, `/research/api/*`, `/research/dify/*`, `/files/*`, `/ws`, and `/desktop/*`. The frontend uses ordinary same-origin fetch and WebSocket. `/desktop/status` returns installed engines, jobs and explicit owner SSH bridge state. `/desktop/jobs` creates local CLI jobs; status/events/cancel share the dp implementation. Native file tools and the selected shared directory remain available. External HTTP/HTTPS links open the system browser. WebView download requests use a native save dialog.

`deep-partner.exe --headless-ui` starts the same host and prints JSON with a one-time local bootstrap URL for automated QA. Keep that output local; it grants that running instance's local session. It is not a remote login token.

## Project files

```powershell
dp login --username YOUR_USERNAME
dp project list
dp project upload --project "Project name or ID" "D:\Research\main.py"
dp project upload --project "Project name or ID" "D:\Research\materials" --recursive --dry-run
dp project upload --project "Project name or ID" "D:\Research\materials" --recursive --json
dp project upload --project "Project name or ID" "D:\Research\method.pdf" --purpose methods
dp project files --project "Project name or ID" --path src
dp logout
```

Interactive login hides the password; scripts can use `--password-stdin`. The CLI session is encrypted with Windows DPAPI and bound to the configured server. Existing remembered-device credentials can also restore a session. Project names must match exactly; use the ID when names are duplicated.

Automatic classification puts PDF files in the literature library and other files under project `src/`, `data/`, `figures/`, `slides/`, `docs/` or `files/`. Use `--category` to override the type and `--path` to choose a project-relative directory for non-library uploads. PDF `--purpose` accepts `references`, `methods`, `validation` or `reading` and uses the existing metadata identification flow. Uploading a file does not start knowledge-base indexing or replace the current manuscript or presentation template. Existing same-name files use the workbench's recoverable version history. Recursive uploads retain the source directory hierarchy, skipping known runtime folders, symlinks and `.env*`; a dry run shows exact destinations without writing. Progress goes to stderr and `--json` returns per-file receipts on stdout; any failed file makes the command exit nonzero.

## dp tasks

```powershell
dp doctor --json
dp task run --engine codex --cwd C:\Research\project --prompt 'Explain this project' --json
dp task status JOB_ID --json
dp task events JOB_ID --after 0 --jsonl
dp task cancel JOB_ID
```

Tasks run the installed `codex exec --json` or `claude -p --output-format stream-json --verbose`, with prompt over stdin, explicit working directory and each CLI's existing login. Availability is checked with `--version`; an installed executable is not a claim that the account is authenticated. Codex uses workspace-write sandbox. The host does not pass approval bypass flags. These are noninteractive jobs and do not implement interactive approval conversations or a full terminal.

A hidden independent dp worker owns each process. Task metadata and ordered stdout/stderr/lifecycle JSONL survive window closure under `%LOCALAPPDATA%/DeepPartner/jobs/<job_id>/`. Cancellation terminates the Windows child process tree. Provider-reported failures (`turn.failed`, Claude `is_error`) remain failed even if the process exits zero. Failed/interrupted jobs retain their evidence and are not automatically replayed. Optional `DEEP_PARTNER_CODEX` / `DEEP_PARTNER_CLAUDE` executable overrides support managed installs and process harnesses; they are local environment settings, not API parameters.

## Existing owner bridge

The app still starts the existing token-protected local MCP endpoint on the configured bridge port. Explicit `/desktop/bridge/connect` and `/desktop/bridge/disconnect` actions control the existing SSH Tunnel. No SSH enrollment is automatic. This path requires the existing owner's SSH alias and deployment permissions; it is not ordinary multi-user device pairing. Port conflicts are reported in `/desktop/status`.

MCP exposes `cli_engines`, `cli_task_start`, `cli_task_status`, `cli_task_events`, `cli_task_cancel`, using the same job registry. Remote MCP task starts must stay within the selected shared folder; direct local dp/UI requests use their explicit cwd. Existing file/browser/Windows tools remain available. Bridge token and optional DPAPI-protected trusted credential remain in the current user's DeepPartner data directory.

## Verification

```powershell
cargo test --features desktop-web --lib --test remote_contract --test cli_worker
```

The process harnesses do not call models. Native tests cover bootstrap/origin/replay, private cookie/redirect behavior, actual WebSocket proxy, text download response, provider error semantics, persistence, detached worker behavior and descendant cancellation. The separately authorized real Codex integration check is recorded in `verification/cli-e2e-summary.json`; it must not be confused with a mocked process result. Current native build/tests are recorded in `verification/native-0.4-build.log` and `verification/native-0.4-tests.log`.
