# FlightLink Desktop 1.0 (Windows x64)

FlightLink 1.0 本地 Windows 桌面客户端，基于 **Python 3.11 + PySide6 (`QGuiApplication` + `QQmlApplicationEngine`) + Qt Quick/QML + 后台 `httpx` + 本机 SQLite 自动归档引擎**。

> 旧版 v0.1 前端保留在 `old-version-0.1` 分支；本 `main` 分支为正式版 FlightLink Desktop 1.0。

## 环境准备

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.lock.txt
.\.venv\Scripts\python.exe -m pip install --no-build-isolation --no-deps -e .
```

## 运行桌面端

```powershell
.\.venv\Scripts\python.exe -m flightlink_desktop
```

## 运行测试与 QML 检查

```powershell
# 全部自动化测试（HTTP 契约与故障注入 + Qt Quick Test 键盘/焦点/响应式/保存态 + 窗口与禁入模块守卫）
.\.venv\Scripts\pytest.exe -v

# 单独运行 Qt Quick Test（无需 C++ 应用骨架）
.\.venv\Scripts\python.exe tests\qml\run_qml_tests.py -platform offscreen

# QML 静态检查
.\.venv\Scripts\pyside6-qmllint.exe -I src\flightlink_desktop\qml src\flightlink_desktop\qml\Main.qml
```

## 生成视觉对照截图

```powershell
.\.venv\Scripts\python.exe scripts\capture_screenshots.py
$env:QT_SCALE_FACTOR="1.25"; .\.venv\Scripts\python.exe scripts\capture_screenshots.py --dpi125
```

## 打包 Windows x64 便携目录

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-build.lock.txt
.\.venv\Scripts\python.exe scripts\build_windows.py
```

输出产物位于 `dist\FlightLinkDesktop\FlightLinkDesktop.exe`（自动校验排除 `.agent/`、`QtWidgets`、`QtWebEngine`、`PyQt6`，并验证独立启动退出）。

## 核心文档索引

- 验收报告：[docs/desktop/acceptance-report.md](docs/desktop/acceptance-report.md)
- OpenAPI 契约映射：[docs/desktop/api-mapping.md](docs/desktop/api-mapping.md)
- 截图索引：[docs/desktop/screenshots/INDEX.md](docs/desktop/screenshots/INDEX.md)
- Skills 锁定记录：[docs/desktop/skills.lock.md](docs/desktop/skills.lock.md)
- P0 准备验收记录：[docs/desktop/p0-verification.md](docs/desktop/p0-verification.md)
