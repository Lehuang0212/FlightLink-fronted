# FlightLink Desktop 1.0 — Project Instructions

## Workspace Boundaries
- Active development directory: `D:\Workspace\Mavproxy\FlightLink-frontend`
- Read-only visual reference: `D:\Workspace\Mavproxy\FLightLink1.0-preview` (never write here)
- Read-only backend reference: `D:\Workspace\Mavproxy\FlightLink-backend` (never write here)
- Preserve all original handoff files under `docs/`; place desktop-specific records under `docs/desktop/`.

## Project Skills (`.agent/skills/`)
The host natively discovers `.agent/skills/<name>/SKILL.md`. Read each skill at the corresponding stage:

1. `.agent/skills/flightlink-desktop-contract/SKILL.md` — Read before implementing or reviewing any stage (P1–P5): Qt main-thread boundary, `202`/`412`, instance isolation, 7-day retention, missing source vs failure, forbidden UI download controls.
2. `.agent/skills/qt-qml/SKILL.md` — Read when authoring or refactoring QML views, `Theme.qml`, layouts, property bindings, and `ListView` delegates (P1–P3).
3. `.agent/skills/qt-qml-test/SKILL.md` — Read when authoring or extending Qt Quick Test (`tst_*.qml`) cases for shortcuts, modal focus, tab switching, and save states (P0, P2–P5).
4. `.agent/skills/python-testing-patterns/SKILL.md` — Read when writing `pytest` suites with controllable clocks, temp directories, and `httpx.MockTransport` doubles (P0–P5).

Do not install skills globally, do not duplicate them into `.agents/skills/`, and exclude `.agent/` from Windows release packages.

## Hard Architecture Constraints
- Python 3.11+, PySide6 (`QGuiApplication` + `QQmlApplicationEngine`), Qt Quick/QML, background `httpx`, `QObject` ViewModels, `QAbstractListModel`.
- Never introduce `Qt Widgets` (`QApplication`/`QWidget`/`QMainWindow`), `PyQt6`, `QtWebEngine`, Electron, or embedded HTML.
- Keep `docs/api/openapi.yaml` as the sole HTTP contract; record any live mismatch (request, response, `request_id`) under `docs/desktop/` without editing the backend or inventing compatibility fields.
