# FlightLink Desktop 1.0 (Windows x64)

FlightLink 1.0 面向运维与飞控观测场景的 **Windows 原生桌面客户端**，用于连接并管理部署在阿里云 ECS 上的 FlightLink 1.0 服务端（MAVLink 转发通道、安全组规则与会话归档日志）。

> 旧版 v0.1 Web 前端保留在 `old-version-0.1` 分支；本 `main` 分支为正式版 FlightLink Desktop 1.0。

---

## 一、项目介绍

### 核心能力
- **安全认证与多实例隔离**
  - 支持远程 HTTPS 与本机回环 HTTP 隧道，保留显式端口、严格校验 TLS 证书。
  - 登录前先通过 `GET /api/v1/health` 探测连通性、RTT 与 `ecs_instance_id`。
  - 访问令牌仅存内存，刷新令牌存入 Windows 凭据库并绑定服务器与账号，不落盘明文密码；401 `TOKEN_EXPIRED` 采用单飞刷新机制；退出或切换服务器立即清空表单凭据与会话代次，彻底隔离旧连接响应。
- **实时监控与双通道日志**
  - 区分整机三组件（`flightlink-api`、`flightlink-agent`、`flightlink-archive`）与每组独立三服务（`Router`、`MAVProxy 会话`、`安全组`），状态、观测时间与过期标记独立展示。
  - 12 张遥测卡片严格区分 `null`（显示 `—`）与真实 `0` / `0.0` / `false`；地面站指令区只读观测。
  - 500 行增量环形缓冲日志，支持「暂停滚动」「清屏」「暂停实时更新」三开关互不干扰（且均不中断后台归档与已受理操作追踪）。
- **可追踪的异步管理操作**
  - 管理员可执行端口组新建、编辑（支持 `PATCH ?dry_run=true` 预演）、删除、Router 启停/重启及同步安全组；只读账号（`viewer`）禁止写操作，但仍可同步本机历史归档。
  - 严格落实 `Idempotency-Key` 防重、`If-Match`（ETag）防并发覆盖、`202` 操作步骤轮询、`409/412/422` 精细错误处理及 `needs_verification` 核验重试。
- **后台自动归档与系统托盘**
  - 登录后自动按 `ecs_instance_id` 隔离轮询 `/archive/changes`，将封存切片原子落盘并校验 SHA-256 至本地文档目录，云端 7 天到期或删组均不影响本地副本。
  - 点击右上角 `×` 时弹窗询问「后台运行」或「完全退出」：选择「后台运行」将最小化至 Windows 任务栏右下角小图标，后台持续自动归档，左键点击小图标可随时恢复主界面，右键支持快速打开或完全退出。

### 技术架构与目录结构
- **技术栈**：Python 3.11+、PySide6（`QGuiApplication` + `QQmlApplicationEngine`）、Qt Quick/QML、后台 `httpx`、SQLite（WAL）、原生 Win32 `Shell_NotifyIconW` 托盘（严格不含 `QtWidgets`、`QtWebEngine`、`PyQt6`、Electron 或内嵌 HTML）。
- **目录职责**：
  - `src/flightlink_desktop/api/`：HTTP 客户端、鉴权单飞协调、URL 校验与 Windows 凭据存储
  - `src/flightlink_desktop/models/`：GUI 线程 `QObject` ViewModel 与 `QAbstractListModel`
  - `src/flightlink_desktop/workers/`：后台线程池与 `202` 异步操作追踪状态机
  - `src/flightlink_desktop/archive/`：Known Folder 路径解析、防穿越与 SQLite 断点续传归档引擎
  - `src/flightlink_desktop/qml/`：主题单例 `Theme.qml`、通用组件与各业务页面
  - `src/flightlink_desktop/tray.py`：原生 Windows 任务栏托盘控制器
  - `packaging/`、`scripts/`：PyInstaller 打包配置、合规审计与 Inno Setup 安装包构建脚本

---

## 二、运行教程（推荐：直接安装可执行安装包）

普通用户无需配置 Python 或编译源码，直接下载安装即可使用：

### 1. 下载安装包
前往 GitHub Releases 页面下载最新版 Windows 安装程序：
- **Release 页面**：[FlightLinkDesktop-v1.0](https://github.com/Lehuang0212/FlightLink-fronted/releases/tag/FlightLinkDesktop-v1.0)
- **直接下载**：[`FlightLinkDesktop-v1.0-Setup.exe`](https://github.com/Lehuang0212/FlightLink-fronted/releases/download/FlightLinkDesktop-v1.0/FlightLinkDesktop-v1.0-Setup.exe)
- **校验文件**：[`SHA256SUMS.txt`](https://github.com/Lehuang0212/FlightLink-fronted/releases/download/FlightLinkDesktop-v1.0/SHA256SUMS.txt)

可选：在 PowerShell 中核对安装包 SHA-256：
```powershell
Get-FileHash .\FlightLinkDesktop-v1.0-Setup.exe -Algorithm SHA256
```

### 2. 一键安装与启动
1. 双击运行 `FlightLinkDesktop-v1.0-Setup.exe`，按向导完成安装（默认安装到当前用户目录，无需管理员权限，可勾选创建桌面快捷方式）。
2. 安装完成后勾选立即启动，或从桌面 / 开始菜单打开 **FlightLink Desktop**。

### 3. 连接 ECS 与日常使用
1. **输入服务器地址**：填写已部署的 ECS 地址（例如 `https://your-ecs-host:8000` 或本机 SSH 隧道 `http://127.0.0.1:8000`），点击「测连接」确认连通性、RTT 与 `ecs_instance_id`。
2. **登录账号**：输入管理员（`admin`）或只读（`viewer`）账号与密码登录；可勾选「使用 Windows 凭据库保持登录会话」实现跨启动免密恢复。
3. **常用快捷键**：
   - `Ctrl+K`：聚焦顶部全局搜索
   - `Ctrl+1` ~ `Ctrl+4`：快速切换「总览 / 端口组 / 日志 / 历史日志」
   - `Esc`：关闭搜索结果、弹窗或清除提示
4. **后台运行与退出**：
   - 点击窗口右上角 `×` 会弹出确认窗口：选择 **「后台运行」** 可隐藏到任务栏右下角托盘继续自动归档，点击托盘小图标即可恢复窗口；选择 **「完全退出」** 则彻底结束进程。
5. **本地数据与归档位置**：
   - 自动归档日志：`文档\FlightLink\Logs\<ecs_instance_id>\<group_id>\<session_id>\`（固定 `router.log`、`mavproxy.log`、`metadata.json`）
   - 本地任务数据库与配置：`%LOCALAPPDATA%\FlightLink\`
   - 卸载程序可通过 Windows「应用和功能」正常卸载，不会删除已保存到 `文档\FlightLink\Logs` 的历史归档副本。

---

## 三、Debug 开发与部署教程

适用于需要在本地调试源码、联调 ECS、运行自动化测试或自行重新打包的开发者。

### 1. 环境准备（Windows 10/11 x64 + Python 3.11+）
```powershell
git clone https://github.com/Lehuang0212/FlightLink-fronted.git
cd FlightLink-fronted

python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.lock.txt
.\.venv\Scripts\python.exe -m pip install --no-build-isolation --no-deps -e .
```

### 2. Debug 启动与本地联调
```powershell
# 标准启动（自动尝试从 Windows 凭据库恢复上次会话）
.\.venv\Scripts\python.exe -m flightlink_desktop

# Debug 常用：跳过自动恢复会话，直接进入干净登录页
.\.venv\Scripts\python.exe -m flightlink_desktop --skip-restore

# 使用独立数据目录进行隔离调试（不污染本机默认配置与 SQLite 任务库）
$env:FLIGHTLINK_DATA_DIR = "$env:TEMP\flightlink-debug-data"
.\.venv\Scripts\python.exe -m flightlink_desktop --skip-restore

# 快速启动冒烟验证（启动后 500ms 自动干净退出，退出码应为 0）
.\.venv\Scripts\python.exe -m flightlink_desktop --skip-restore --smoke-exit-ms 500
```

如需通过 SSH 隧道安全联调仅监听 `127.0.0.1:8000` 的 ECS 后端，可另开终端建立本地转发后在桌面端填写 `http://127.0.0.1:8000`：
```powershell
ssh -N -L 8000:127.0.0.1:8000 <user>@<ecs-ip>
```

> 可选调试环境变量：`$env:FLIGHTLINK_REDUCED_MOTION = "1"` 可强制开启减少动态效果模式；`$env:QT_SCALE_FACTOR = "1.25"` 可模拟 125% 高 DPI 缩放。

### 3. 运行自动化测试与静态检查
```powershell
# 全量测试（HTTP 契约/故障注入 + 归档恢复 + Qt Quick QML 交互与布局 + 禁入模块守卫）
.\.venv\Scripts\pytest.exe -v

# 单独运行 Qt Quick Test 套件
.\.venv\Scripts\python.exe tests\qml\run_qml_tests.py -platform offscreen

# QML 静态语法检查
.\.venv\Scripts\pyside6-qmllint.exe -I src\flightlink_desktop\qml src\flightlink_desktop\qml\Main.qml
```

### 4. 构建便携目录与 Windows 可执行安装包

#### 第一步：安装构建依赖并打包便携目录（PyInstaller）
```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-build.lock.txt
.\.venv\Scripts\python.exe scripts\build_windows.py
```
- 输出目录：`dist\FlightLinkDesktop\FlightLinkDesktop.exe`
- 构建脚本会自动审计并断言排除 `.agent/`、`QtWidgets`、`QtWebEngine`、`PyQt6`，并对打包后的 EXE 执行独立启动冒烟验证。

#### 第二步：编译单文件可执行安装包（Inno Setup 6）
1. 安装 Inno Setup 6（若本机尚未安装）：
   ```powershell
   winget install --id JRSoftware.InnoSetup --scope user --silent --accept-package-agreements --accept-source-agreements
   ```
2. 执行安装包构建脚本（默认版本标签 `FlightLinkDesktop-v1.0` / `1.0.0`，支持自定义参数）：
   ```powershell
   .\.venv\Scripts\python.exe scripts\build_installer.py FlightLinkDesktop-v1.0 1.0.0
   ```
- 输出产物：
  - `dist\release\FlightLinkDesktop-v1.0-Setup.exe`
  - `dist\release\SHA256SUMS.txt`

---

## 四、文档索引

- 产品范围与架构契约：[docs/desktop-client-handoff.md](docs/desktop-client-handoff.md)
- 唯一 HTTP 契约（OpenAPI）：[docs/api/openapi.yaml](docs/api/openapi.yaml)
- 桌面端验收报告：[docs/desktop/acceptance-report.md](docs/desktop/acceptance-report.md)
- 实机 ECS 联调验收报告：[docs/desktop/live-e2e-test-report.md](docs/desktop/live-e2e-test-report.md)
- 实机问题与修复记录：[docs/desktop/live-issues-record.md](docs/desktop/live-issues-record.md)
- OpenAPI 契约映射：[docs/desktop/api-mapping.md](docs/desktop/api-mapping.md)
- 视觉验收截图索引：[docs/desktop/screenshots/INDEX.md](docs/desktop/screenshots/INDEX.md)
- Skills 锁定记录：[docs/desktop/skills.lock.md](docs/desktop/skills.lock.md)
