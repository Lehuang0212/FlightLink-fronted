# FlightLink Desktop 1.0 — 最终验收报告

日期：2026-11-27  
开发目录：`D:\Workspace\Mavproxy\FlightLink-frontend`（远端 `https://github.com/Lehuang0212/FlightLink-fronted.git`，`main` 分支；旧版 v0.1 保留在 `old-version-0.1` 分支）

> **严格分层声明**：本报告严格区分三类证据来源——（1）自动化测试替身（`httpx.MockTransport`），（2）本机真实 Qt Quick 窗口、键盘、高 DPI 与 Windows x64 独立打包产物实测，（3）真实阿里云 ECS 联调与干净无开发环境 Windows 主机验收。**生产版无任何 Mock 模式**，绝不拿测试替身结果冒充真实 ECS 或干净主机验收结果。

---

## 一、固定版本与交付物清单

| 交付项 | 路径 / 版本 |
|---|---|
| 目标平台 | Windows 11 `x86_64` (`Windows-10-10.0.26300-SP0`, `AMD64`, 64-bit) |
| 运行环境 | `Python 3.11.15` + `PySide6-Essentials==6.12.0` (`Qt 6.12.0` MSVC 2022 x64) + `httpx==0.29.0` + `keyring==25.7.0` |
| 测试与打包工具 | `pytest==9.2.0`、`pytest-qt==4.5.0`、`PySide6.QtQuickTest.QUICK_TEST_MAIN`、`pyinstaller==6.19.0` |
| 依赖锁文件 | [pyproject.toml](../../pyproject.toml)、[requirements-dev.lock.txt](../../requirements-dev.lock.txt)（32 项）、[requirements-build.lock.txt](../../requirements-build.lock.txt)（36 项） |
| 项目 Skills 锁 | [docs/desktop/skills.lock.md](skills.lock.md)（原生发现已实测确认；打包已排除 `.agent/`） |
| OpenAPI 契约映射 | [docs/desktop/api-mapping.md](api-mapping.md)（全 25 接口，明确禁用 `/logs/export` 与 `/download`） |
| 视觉截图索引 | [docs/desktop/screenshots/INDEX.md](screenshots/INDEX.md)（31 张真实窗口截图，含三档分辨率、8 类异常/权限/归档态与 125% DPI） |
| Windows 便携产物 | `dist\FlightLinkDesktop\FlightLinkDesktop.exe`（本地构建产物，`.gitignore` 已忽略不入库，可通过 `scripts/build_windows.py` 复现） |

---

## 二、分层验收结果

### 第 1 层：HTTP 契约与故障注入测试（来源：`httpx.MockTransport` 测试替身）

执行命令：`.\.venv\Scripts\pytest.exe -v`  
实测结果：**`26 passed`（全部通过，0 失败）**

| 模块 | 测试文件 | 覆盖的关键契约与故障场景 | 状态 |
|---|---|---|---|
| P0 冒烟 | `tests/test_http_smoke.py` | `GET /api/v1/health` 响应契约 | 通过 |
| P1 认证与隔离 | `tests/test_p1_auth_and_isolation.py` | URL 规范化（默认端口 8000 / 保留显式端口 / 远程 HTTPS / 本机回环 HTTP / 严禁关闭 TLS 校验）；`CredentialStore` 不存明文密码且按 `(server, user)` 绑定刷新令牌；密码错误 `401 INVALID_CREDENTIALS` 不触发刷新；详情与归档并发过期仅触发 1 次单飞刷新并最多重放 1 次；刷新失败清态回登录；服务器 A 切至 B 时 A 的迟到响应被丢弃且令牌不串主机；`viewer` 禁止写操作（`403`）但允许本机归档读取 | 通过（7/7） |
| P2 数据与轮询 | `tests/test_p2_models_and_polling.py` | 12 张遥测卡 `null -> —` 且严格保留真实 `0`/`0.0`/`false`；三项服务（`router`/`mavproxy`/`security_group`）独立表达 `state`/`observed_at`/`stale`（过期≠离线）；实时日志 500 行增量环形模型仅发 `rowsInserted`/`rowsRemoved` 无 `modelReset`，本地清屏不丢服务端游标、暂停滚动保留位置并累计未读；删组详情 `404 GROUP_NOT_FOUND` -> 查 `/archive/groups/{id}` 返回 `200` 跳转历史页；历史元数据先行，展开才懒加载 `/entries` | 通过（4/4） |
| P3 异步写流程 | `tests/test_p3_async_operations.py` | 双击防重与响应丢失复用同一 `Idempotency-Key`、修改载荷自动换新键；`PATCH ?dry_run=true` 返回 `200` 预演不标已应用；正式写返回 `202` 启动前 5s 每 `500ms` 后 `1.5s` 轮询；`412 CONFIG_VERSION_MISMATCH` 保留用户草稿并重载最新 `ETag`；`needs_verification` 停止自动轮询、展示步骤与 `retry_hint` 且仅管理员可重试；网络中断恢复查原 `operation_id` 不重复建单；暂停实时更新与切换页面不丢操作追踪 | 通过（4/4） |
| P4 本机自动归档 | `tests/test_p4_archive_sync.py` | Windows `SHGetKnownFolderPath(FOLDERID_Documents)` 解析文档目录；恶意远端文件名与路径穿越拦截（固定 `router.log`/`mavproxy.log`/`metadata.json`）；双 ECS 实例（`ecs-A`/`ecs-B`）重复切片 ID 完全隔离不串档、各用各游标；**贯穿验收用例**（第 2 个文件下载中断 -> 重开恢复 -> 第 1 个文件不重下、已改名未提交崩溃文件磁盘校验直过、补齐缺失文件后变 `saved` 且无下载按钮）；合法零字节 `empty` 标 `saved`；`missing_on_server`/`degraded_quota_exceeded`（保存可读部分文件）标 `saved_with_source_gaps` 不提示重试；HTTP 200 校验不匹配绝不标 `saved`；`PermissionError`/`ENOSPC` 精确分类；`410 ARCHIVE_EXPIRED` 立即停重试且保留本地副本；`410 CURSOR_EXPIRED` 记缺口并限次空游标对账；归档流式下载与详情页并发 `401 TOKEN_EXPIRED` 共享单飞刷新 | 通过（5/5） |
| P5 契约与线程守卫 | `tests/test_p5_contract_and_ui_invariants.py` | 核对 `docs/api/openapi.yaml` 全部 25 个操作；静态扫描源码禁止 `/logs/export`、`/download`、`QtWidgets`、`QtWebEngine`、`PyQt6`；`ArchiveSyncWorker` 登录即启动并在关闭时干净退出后台线程 | 通过（2/2） |

---

### 第 2 层：真实 Qt Quick 窗口、键盘、高 DPI 与 Windows 独立打包实测（来源：本机 Windows 11 实测）

| 检查项 | 执行方式 | 实测结果 |
|---|---|---|
| Qt Quick Test（键盘、焦点、响应式、保存态） | `.\.venv\Scripts\python.exe tests\qml\run_qml_tests.py -platform offscreen`（由 `tests/test_qml_quick.py` 集成） | 全部通过：`tst_KeySmokeView.qml`（`Ctrl+K`/`Esc`）、`tst_LoginPage.qml`（360px 卡片、无预填凭据、密码显隐、回车登录、`Esc` 清错）、`tst_DetailLayout.qml`（1280 首屏三服务+12 遥测卡+双标签、1440/1600 双窗格、侧栏 `192px`/`208px`、`Ctrl+1~4`）、`tst_HistorySaveStates.qml`（仅 `failed` 显示「重新下载日志」，`saved`/`saved_with_source_gaps` 隐藏下载按钮） |
| QML 静态检查 | `.\.venv\Scripts\pyside6-qmllint.exe -I src\flightlink_desktop\qml ...` | 退出码 `0` |
| 原生 Windows 窗口启动与禁入模块守卫 | `.\.venv\Scripts\python.exe -m flightlink_desktop --smoke-exit-ms 300 --skip-restore` 与 `test_app_excludes_forbidden_qt_modules` | 退出码 `0`，运行时未加载 `QtWidgets`/`QtWebEngine`/`PyQt6`，后台线程干净退出 |
| 三档分辨率 + 8 类状态 + 125% DPI 视觉截图 | `scripts/capture_screenshots.py`（原生 Windows 125% DPI + 附加 `QT_SCALE_FACTOR=1.25`） | 31 张截图全部生成并人工目视复核无横向溢出与截断，详见 [screenshots/INDEX.md](screenshots/INDEX.md) |
| Windows x64 便携打包与独立启动验证 | `.\.venv\Scripts\python.exe scripts\build_windows.py` | 产出 `dist\FlightLinkDesktop\FlightLinkDesktop.exe`（2081 文件）：含 `qwindows.dll`、`QtQuick` QML 模块、`Main.qml`、`certifi/cacert.pem`；`.agent/`、`Qt6Widgets`、`Qt6WebEngine*`、`PyQt6` 命中数为 `0`；在隔离环境变量（无 `.venv` 与 `PYTHONPATH`）下直接启动 `FlightLinkDesktop.exe --smoke-exit-ms 400 --skip-restore` 退出码 `0` |

---

### 第 3 层：真实 ECS 联调与干净无开发环境 Windows 验证（待执行项 — 未冒充通过）

本会话未提供目标测试 ECS 的访问地址与正式账号密码，也未接入第二台无开发环境的干净 Windows 机器，因此以下实机项目**明确标记为未验证**，待提供测试环境后按下方步骤逐项补验并记录：

1. **真实 ECS 联调（待提供测试 ECS 地址与 `admin`/`viewer` 正式账号）**：
   - 使用 `dist\FlightLinkDesktop\FlightLinkDesktop.exe` 连接测试 ECS，先测 `GET /api/v1/health` 连通与 RTT，再分别以 `admin` 与 `viewer` 登录。
   - **贯穿全程验收用例**：查看“一号机”并等待一次真实飞控会话封存；在第 2 个文件下载时人工断网，关闭并重开客户端恢复，核实文档目录 `<Documents>\FlightLink\Logs\<ecs_instance_id>\<group_id>\<session_id>\` 下第 1 个文件未重下、缺失文件补齐且界面无下载按钮；删除该组并按同名同端口重建，验证新组获新 `group_id` 不继承旧组日志、原组本地文件仍完好。
   - 如发现任何实机响应与 `docs/api/openapi.yaml` 不一致，将完整请求、响应与 `request_id` 记录到 `docs/desktop/live-ecs-discrepancies.md`（不修改后端）。
2. **干净 Windows 10/11 `x86_64` 主机实测（无 Python / Qt 开发环境）**：
   - 拷贝 `dist\FlightLinkDesktop\` 整个目录到未安装 Python/PySide6 的干净 Windows 机器，直接双击运行 `FlightLinkDesktop.exe`，完整验证启动、HTTPS/TLS 握手、登录、查看日志、自动归档写入真实系统“文档”目录（含重定向文档目录场景）、退出与再启动恢复会话。
