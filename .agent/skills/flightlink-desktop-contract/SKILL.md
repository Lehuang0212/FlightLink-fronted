---
name: flightlink-desktop-contract
description: >-
  Project-specific FlightLink Desktop 1.0 contract guardrails and error-prone
  rules mapped to the authoritative handoff and OpenAPI documents. Read before
  implementing or reviewing auth, polling, QML views, async write operations,
  or local archive auto-save.
---

# FlightLink Desktop 1.0 Contract Guardrails

Authoritative contract sources (never duplicate endpoint tables here; read directly from source):
- Product scope & Qt hard constraints: `docs/desktop-client-handoff.md`
- Sole HTTP contract (paths, schemas, enums, status codes, headers): `docs/api/openapi.yaml`
- Page call sequence, polling cadence & error handling: `docs/frontend-integration.md`
- Local archive algorithm reference (not a runnable desktop service): `docs/examples/python_archive_sync.py`

When live ECS behavior disagrees with these docs, record the request, response, and `request_id` under `docs/desktop/` — never edit the backend or invent compatibility fields.

## 1. Qt Main Thread Boundary & Hard Tech Stack
- Required stack: Python 3.11+, PySide6 (`QGuiApplication` + `QQmlApplicationEngine`), Qt Quick/QML, background `httpx`, `QObject` ViewModels, `QAbstractListModel` (`docs/desktop-client-handoff.md` §1).
- Forbidden: `Qt Widgets` (`QApplication`, `QWidget`, `QMainWindow`), `PyQt6`, `QtWebEngine`, Electron, embedded HTML.
- All HTTP, SQLite, disk I/O, and SHA-256 hashing run off the GUI thread; results return via Qt queued signals. Workers must never touch QML objects or mutate `QAbstractListModel` directly.

## 2. Auth, Roles, Single-Flight Refresh & Isolation
- No demo mode and no prefilled credentials. Server URL is editable (default port `8000`; keep explicit port; never disable TLS verification). Probe `GET /api/v1/health` (RTT + `ecs_instance_id`) before login (`docs/desktop-client-handoff.md` §2.2, §3).
- Access token lives in memory only; refresh token (if persisted) uses Windows Credential Manager bound to server + account; never save plaintext passwords.
- Only `401 TOKEN_EXPIRED` triggers a single-flight `POST /api/v1/auth/refresh` shared by UI pollers and archive workers (concurrent requests refresh once, replay at most once). Wrong credentials never refresh; refresh failure clears state and returns to login.
- After logout or server switch, late responses from the old connection must be discarded and must never update UI, write to the wrong local directory, or leak old tokens to the new host.
- `viewer` cannot invoke server write operations (`403 INSUFFICIENT_ROLE`), but **can** run automatic and manual local archive downloads (authenticated read endpoints).

## 3. Async Writes (`202` vs `200`), Idempotency & `412`
- `PATCH /api/v1/groups/{group_id}?dry_run=true` returns `200` (preview only). Formal writes (`POST/PATCH/DELETE /groups`, `/actions/{action}`, `/operations/{id}/retry`) return `202 Accepted` (accepted, NOT applied) (`docs/frontend-integration.md` §4; `docs/api/openapi.yaml`).
- One user intent = one `Idempotency-Key` (UUIDv4). Timeout retries reuse the same key; changing payload generates a new key (`409 IDEMPOTENCY_CONFLICT` otherwise).
- Edits and deletes send the `ETag` obtained from `GET /groups/{group_id}` as `If-Match`. On `412 CONFIG_VERSION_MISMATCH`, preserve the user's draft and reload the latest version.
- Poll `GET /api/v1/operations/{operation_id}` every `500ms` for the first 5s, then `1–2s`. On `needs_verification`, stop auto-polling, show `steps` + `retry_hint`, and expose `POST /operations/{id}/retry` only when `role == admin` and `retryable == true`.
- Create/edit only configures `dtu_port` (fixed UDP) + `gcs_port` (`tcp`/`udp`), never SYSID.

## 4. Telemetry, Services, Live Logs & Toggle Separation
- 12 telemetry cards come from `GroupDetail.telemetry` (plus `recent_gcs_commands`, strictly read-only). Render `null` as `—`; **never** coerce `null` to `0` or `false`, and preserve genuine `0` and `false` (`docs/desktop-client-handoff.md` §3; `docs/api/openapi.yaml` `TelemetrySnapshot`).
- Distinguish host components (`flightlink-api`, `flightlink-agent`, `flightlink-archive`) from per-group services (`router`, `mavproxy`, `security_group`). Each service renders `state`, `observed_at`, and `stale` independently — `stale` is NOT offline.
- Live logs use an incremental 500-row model (append/trim by cursor, no full reset). Local clear moves display start only; pause scroll preserves viewport.
- Keep three switches independent: **pause scroll** (viewport only), **pause live updates** (UI reads only), and **background archive + accepted operation tracking** (never paused by either UI switch).

## 5. Instance Isolation, 7-Day Retention & Deleted Groups
- Archive path is resolved locally via Windows Known Folder `FOLDERID_Documents`: `<Documents>\FlightLink\Logs\<ecs_instance_id>\<group_id>\<session_id>\` with fixed filenames `router.log`, `mavproxy.log`, `metadata.json`; task DB lives in `%LOCALAPPDATA%\FlightLink\`. Treat server IDs as opaque and validate resolved paths stay under logs root (`docs/desktop-client-handoff.md` §4).
- Scope cursors and pending tasks by `ecs_instance_id` from `/health` — **never** pick "latest cursor" across instances. Persist deduplicated tasks before advancing `next_cursor` in one SQLite transaction.
- When `GET /groups/{id}` returns `404 GROUP_NOT_FOUND`, check `GET /archive/groups/{id}` and jump to history only on `200`. Same-name/same-port recreated groups get a new `group_id` and must never merge histories.
- Cloud retention is 7×24h; cloud deletion or expiry **never** deletes local files. `410 ARCHIVE_EXPIRED` stops retrying that file; `410 CURSOR_EXPIRED` records a retention gap and reconciles from empty cursor with a per-cycle reset cap.

## 6. Missing Source vs Failure & No Regular Download Buttons
- Local status comes only from verified disk state (`httpx.stream()` -> `.part` -> check size, manifest SHA-256, and `X-Content-SHA256` -> `os.replace()` -> SQLite commit). Never infer saved from HTTP 200 (`docs/frontend-integration.md` §6.2; `docs/examples/python_archive_sync.py`).
- `saved`: all available files verified, no gaps -> **no download button, export button, auto-save toggle, source selector, or save dialog**.
- `saved_with_source_gaps`: cloud had `missing_on_server` or `degraded_quota_exceeded` (download readable partial files if present) -> show what is missing and why, **never** prompt user to retry. Legal zero-byte `empty` files are NOT missing sources.
- `failed`: only after automatic retries exhaust (network, `PermissionError`/`EACCES`, `ENOSPC`, checksum mismatch) -> show classified error and「重新下载日志」linking to the slice, downloading only missing files via the shared task queue.
- Regular desktop UI must **never** call `GET /api/v1/logs/export` or `GET /api/v1/archive/sessions/{session_id}/download`.
