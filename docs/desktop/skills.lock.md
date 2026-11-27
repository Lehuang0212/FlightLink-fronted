# FlightLink Desktop 1.0 Skills Lockfile

> Project-scoped development skills installed under `.agent/skills/<name>/`.
> Not installed globally, not copied as whole plugin marketplaces, and excluded from Windows release builds/installers.

| Skill | Upstream Repository | Pinned Commit | Upstream Subdirectory | License | Relative Path | Installed Files | Local Adjustments |
|---|---|---|---|---|---|---|---|
| `qt-qml` | `https://github.com/TheQtCompanyRnD/agent-skills` | `dce029506599e3a01bd628d106b005b37c17f525` | `skills/qt-qml` | `LicenseRef-Qt-Commercial OR BSD-3-Clause` (Copyright (c) 2026, The Qt Company Ltd.) | `.agent/skills/qt-qml/` | `SKILL.md`, `LICENSE.txt`, `SOURCE.md` | Omitted IDE adapter `platforms/windsurf.md`; `SKILL.md` and `LICENSE.txt` kept verbatim. |
| `qt-qml-test` | `https://github.com/TheQtCompanyRnD/agent-skills` | `dce029506599e3a01bd628d106b005b37c17f525` | `skills/qt-qml-test` | `LicenseRef-Qt-Commercial OR BSD-3-Clause` (Copyright (c) 2026, The Qt Company Ltd.) | `.agent/skills/qt-qml-test/` | `SKILL.md`, `LICENSE.txt`, `SOURCE.md`, `references/qt-quick-test-controls.md`, `references/qt-quick-test-pitfalls.md`, `references/qt-quick-test-pre-send-scan.md`, `references/qt-quick-test-project-context.md`, `references/qt-quick-test-properties.md`, `references/qt-quick-test-rules.md`, `references/qt-quick-test-source-import.md`, `references/qt-quick-test-template.md` | Omitted IDE adapter `platforms/copilot.prompt.md`; `SKILL.md`, `LICENSE.txt`, and all 8 `references/*.md` kept verbatim. |
| `python-testing-patterns` | `https://github.com/wshobson/agents` | `c96b5f6552dba32e4492307493ee613581430715` | `plugins/python-development/skills/python-testing-patterns` | `MIT` (Copyright (c) 2024 Seth Hobson) | `.agent/skills/python-testing-patterns/` | `SKILL.md`, `LICENSE`, `SOURCE.md`, `references/advanced-patterns.md`, `references/details.md` | None (upstream `SKILL.md`, `references/`, and root `LICENSE` preserved verbatim). |
| `flightlink-desktop-contract` | Local project skill (authored from repository handoff docs) | N/A (tracked in this repo) | N/A | Project-internal | `.agent/skills/flightlink-desktop-contract/` | `SKILL.md` | Authored from `docs/desktop-client-handoff.md`, `docs/api/openapi.yaml`, `docs/frontend-integration.md`, and `docs/examples/python_archive_sync.py`. References OpenAPI instead of duplicating endpoint tables. |

## Discovery Mechanism Verification

- **Result**: **Native discovery (`原生发现`) confirmed.**
- **Method**: Spawned a clean subagent (`0bf12a02-d457-41df-b78a-05606ad1b5c5`) in `D:\Workspace\Mavproxy\FlightLink-frontend` without filesystem search or `GEMINI.md` hints and inspected its injected `<skills>` list.
- **Observed**: All four skills under `.agent/skills/<name>/SKILL.md` (`flightlink-desktop-contract`, `python-testing-patterns`, `qt-qml`, `qt-qml-test`) were automatically discovered and injected by the host.
- **Note**: Directory remains singular `.agent/skills/` with no duplicate copy under `.agents/skills/`. `GEMINI.md` also documents stage-by-stage usage timing for clarity across sessions.
