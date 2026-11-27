# FlightLink Desktop 1.0 — P0 Preparation & Verification Record

Date: 2026-11-27

## 1. Repository & Branch Migration

- Remote repository: `https://github.com/Lehuang0212/FlightLink-fronted.git`
- Legacy v0.1 frontend (`e6689e6a36a390b91b3f1be6e68ca389f1a031c7`) preserved and pushed to branch `old-version-0.1`.
- New FlightLink Desktop 1.0 workspace committed and pushed to `main` (fast-forward descendant of `e6689e6` so no force-push was needed).
- All original handoff files under `docs/` (`docs/desktop-client-handoff.md`, `docs/api/openapi.yaml`, `docs/frontend-integration.md`, `docs/examples/python_archive_sync.py`, `docs/implementation-plan.md`, `docs/dev-skills.lock.md`, `docs/acceptance.md`, `docs/operations-and-packaging.md`) preserved untouched.
- Read-only reference directories `D:\Workspace\Mavproxy\FLightLink1.0-preview` and `D:\Workspace\Mavproxy\FlightLink-backend` untouched.

## 2. Project Skills & Discovery Verification

Installed under `.agent/skills/<name>/` (singular `.agent`, not global, excluded from Windows packages) and recorded in `docs/desktop/skills.lock.md`:

- `.agent/skills/qt-qml/` (`TheQtCompanyRnD/agent-skills @ dce029506599e3a01bd628d106b005b37c17f525`, `LicenseRef-Qt-Commercial OR BSD-3-Clause`)
- `.agent/skills/qt-qml-test/` (`TheQtCompanyRnD/agent-skills @ dce029506599e3a01bd628d106b005b37c17f525`, `LicenseRef-Qt-Commercial OR BSD-3-Clause`)
- `.agent/skills/python-testing-patterns/` (`wshobson/agents @ c96b5f6552dba32e4492307493ee613581430715`, `MIT`)
- `.agent/skills/flightlink-desktop-contract/` (project-authored contract guardrails)

**Measured discovery result**: **Native discovery (`原生发现`) confirmed** via clean subagent verification (`0bf12a02-d457-41df-b78a-05606ad1b5c5`) — all four skills under `.agent/skills/` were auto-discovered without renaming to `.agents/skills/`. `GEMINI.md` also explicitly documents their paths and stage-by-stage usage timing.

## 3. Target Platform, Toolchain & Locked Dependencies

| Item | Verified Value |
|---|---|
| Target OS & Architecture | Windows 11 `x86_64` (`Windows-10-10.0.26300-SP0`, `AMD64`, 64-bit) |
| Python | `CPython 3.11.15` (64-bit) in `.venv` |
| PySide6 / Qt | `PySide6-Essentials==6.12.0` (`shiboken6==6.12.0`, Qt runtime & compiled `6.12.0`, MSVC 2022 `x86_64`) |
| Qt Quick Test Runner | `PySide6.QtQuickTest.QUICK_TEST_MAIN` via `tests/qml/run_qml_tests.py` (no C++ app skeleton) |
| Qt CLI Tools Verified | `pyside6-qmllint.exe`, `pyside6-qmlformat.exe`, `pyside6-qmlimportscanner.exe`, `pyside6-lupdate.exe`, `pyside6-rcc.exe` |
| HTTP / Credentials / Testing | `httpx==0.29.0`, `keyring==25.7.0`, `pytest==9.2.0`, `pytest-qt==4.5.0`, `pytest-cov==7.1.0`, `freezegun==1.5.5`, `PyYAML==6.0.4` |
| Dependency Lockfile | `requirements-dev.lock.txt` (32 locked packages, UTF-8) + `pyproject.toml` |

## 4. P0 Exit Gate Execution & Results

All commands run from `D:\Workspace\Mavproxy\FlightLink-frontend`:

1. **QML lint check**:
   ```powershell
   .\.venv\Scripts\pyside6-qmllint.exe src\flightlink_desktop\qml\Main.qml src\flightlink_desktop\qml\components\KeySmokeView.qml
   ```
   Result: Exit code `0`, zero warnings/errors.

2. **Native Windows `QGuiApplication` + `QQmlApplicationEngine` launch**:
   ```powershell
   .\.venv\Scripts\python.exe -m flightlink_desktop --smoke-exit-ms 300
   ```
   Result: Exit code `0` (native Windows QPA platform opened root `ApplicationWindow` and exited cleanly).

3. **Qt Quick Test keyboard shortcut verification (`tst_KeySmokeView.qml`)**:
   ```powershell
   .\.venv\Scripts\python.exe tests\qml\run_qml_tests.py -platform offscreen
   ```
   Result: Exit code `0` (`Totals: 4 passed, 0 failed, 0 skipped, 0 blacklisted`, covering `Ctrl+K` focus + `SignalSpy` and `Esc` clear + `SignalSpy`).

4. **Combined pytest suite (HTTP `MockTransport` + Qt Quick Test + window launch + forbidden Qt module guard)**:
   ```powershell
   .\.venv\Scripts\pytest.exe -v
   ```
   Result: `4 passed` (`tests/test_http_smoke.py::test_health_endpoint_contract_with_mock_transport`, `tests/test_qml_quick.py::test_qml_keyboard_shortcuts_via_qt_quick_test`, `tests/test_qml_quick.py::test_minimal_qguiapplication_window_launch_and_clean_exit`, `tests/test_qml_quick.py::test_app_excludes_forbidden_qt_modules`).
