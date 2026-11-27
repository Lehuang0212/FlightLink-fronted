# FlightLink Desktop 1.0｜Windows 桌面端 × 实机 ECS 验收

**结论：FAIL，不建议放行 `bc4fba2`。** 阻断原因是桌面端退出后仍保留上一个管理员的密码：服务端已 `204` 退出、Windows 凭据库也已清空，返回的登录框却仍持有原值。两个已知后端回归均通过，端口组核心写流程通过；另有一处归档列表与契约文字不符。未接入飞控/GCS，本报告不签发真实遥测、在线心跳或真实切片恢复的验收结论。

## 1. 环境与证据口径

| 项目 | 实测 |
|---|---|
| 时间与平台 | 2026-11-28，约 00:28–00:48（Windows 本地 UTC+8，含证据复核）；接口及 JSONL 记录为 UTC。Windows x64，build 26300，125% 缩放。尺寸表使用 Qt 逻辑像素。 |
| 源码 | `D:\Workspace\Mavproxy\FlightLink-frontend`，`main`，`bc4fba2106f809bc2fe0043ca9ec3de7d76e9cdb`。开测前工作树干净。 |
| 运行时 | 项目 `.venv`，Python **3.11.15**，PySide6 / Qt **6.12.0**。 |
| 便携版 | `dist\FlightLinkDesktop\FlightLinkDesktop.exe`；SHA-256 `B3108888DCBCB97C3B9A1A52A447699D75607364E643FF6AE9088E239BEF569D`。 |
| 实机 | **`http://8.152.223.204:18080/api/v1`**；`health.version=1.0.0`，`ecs_instance_id=ecs_03eacde19f2b2713`，`db_ok=true`。管理员 `ops_admin`，无已提供的 viewer 凭据。 |
| 硬件与数据 | 飞控、真实 GCS 均未接入。空游标增量清单 `items=[]`、`has_more=false`，本实例本机切片/文件任务均为 0。 |
| 测试方式 | EXE 在仓库外工作目录独立启动，使用 Win32 窗口操作和窗口级抓图。带逐请求观测的场景另启同提交的真实 `DesktopRuntime + QQmlApplicationEngine`，点击实际 QML 控件，部分步骤直接驱动 ViewModel 或同一鉴权 API 客户端。18 个打包 QML 文件与源码逐字节一致；PYZ 中 21 个应用模块与源码编译代码对象一致（忽略构建路径）。**并非把每次 API 探测都算作鼠标点击。** |

本次按指定 **HTTP** 执行；OpenAPI `servers` 和集成指南对生产远程入口另有 HTTPS 要求，这是**测试部署与生产配置的差异**，本次没有验证 TLS 握手或证书。没有修改前后端业务代码、后端配置、实机账号或原有端口组。

**证据索引**（同目录 [live-e2e-evidence/](live-e2e-evidence/)）：

- [请求流水](live-e2e-evidence/requests.jsonl)：324 条主流程响应，含时间、阶段、方法、路径、查询、白名单请求头/体与 `rid`（`X-Request-Id`）。此采集器遇到响应体本身含 `status` 时，`status` 列记的是**业务状态**（如 `ok/running/succeeded`），不要当作 HTTP 状态码；关键操作另见 [HTTP 状态与服务端操作复核](live-e2e-evidence/operations-check.json)。
- [阶段观测](live-e2e-evidence/observations.jsonl)、[认证与隔离补测](live-e2e-evidence/supplement.jsonl)、[密码登录与退出](live-e2e-evidence/password-flow.json)、[历史列表与详情原始响应（脱敏）](live-e2e-evidence/archive-contract.json)、[搜索行为](live-e2e-evidence/final-check.json)。
- [EXE 总览](live-e2e-evidence/exe-start.png)、[EXE 登录](live-e2e-evidence/exe-login.png)、[EXE 运行详情](live-e2e-evidence/exe-detail.png) 是便携版窗口截图；其余 UI 截图为 Windows 上的同提交桌面运行时。未使用项目旧截图或演示数据充当 ECS 证据。
- 表中 **PASS** 仅指该行注明的层级；**BLOCKED** 指缺少实机前提，**N/A** 指本轮硬件/数据不适用。真实 ECS、客户端受控故障注入和离线测试分别标注。

## 2. 阶段 0｜本地基线与打包

| 用例 | 结果 | 实测证据 |
|---|---|---|
| 原样运行 `.\.venv\Scripts\pytest.exe -v` | **FAIL** | `1 failed, 25 passed in 11.94s`。唯一失败 `test_qml_keyboard_shortcuts_via_qt_quick_test`；单独复跑也失败。QML 子进程退出 0，pytest 断言所见内容仅 `'\n'`。见 QA-08。 |
| 独立核实 QML、指定 Windows 输出环境再跑全量 | PASS | `-o <文件>,txt` 得 [18 passed, 0 failed, 0 skipped](live-e2e-evidence/qml-results.txt)，含各套件 init/cleanup；设置文末环境后全量 **26 passed in 10.19s**。两组计数有包含关系，不能相加。 |
| 独立启动、恢复会话、正常退出 | PASS | 仓库外工作目录启动 EXE，不调用 venv；登录态总览和详情正常。登录窗口与主窗口发 `WM_CLOSE` 均退出 0；另测 `--skip-restore --smoke-exit-ms 750` 也退出 0。[窗口记录](live-e2e-evidence/exe-window.json) |
| 违禁内容 | PASS | 递归含隐藏项共 2,205 个文件/目录，`.agent`、QtWidgets、QtWebEngine、PyQt6 及其 Qt5/6 DLL 命名命中 0；另查 EXE 的 CArchive/PYZ（773 个 PYZ 模块）未见上述模块。 |

## 3. 阶段 1｜连接、认证与权限

| 用例 | 结果 | 实测证据 |
|---|---|---|
| 健康、显式端口、RTT | PASS | 无鉴权 `GET /api/v1/health` → `200`，`req_01a21dd652fead2462e9b8e9`，含建连耗时 418.829 ms；桌面探测另测 91 ms，保留 `:18080`，[登录页](live-e2e-evidence/login.png)。TLS 校验开关源码 `api/client.py:65–70` 为 `verify=True`，不跟随重定向。 |
| `ecs_instance_id` 对用户可见 | **FAIL** | 响应及 Session VM 有正确实例 ID，登录探测栏只显示连通及 RTT；主界面详情可见文本中也无该 ID。见 QA-04。 |
| 初次登录无预填、无演示入口；超长错误 | PASS | 未恢复会话时两个输入框均空，未见演示按钮；长文本受控渲染 `clip=true`、`overflow=true`，内层 x 从 0 移到 −36.52，无横向撑开。[动效测量](live-e2e-evidence/motion.json)。退出后的表单另判。 |
| 错误密码 | PASS | `POST /auth/login` → `401 INVALID_CREDENTIALS`，`req_01a21ddacbd21c96f499d955`；UI“账号或密码错误。”，该次登录到错误提示间 refresh 计数 **0**。 |
| 密码登录、凭据库、应用数据无明文 | PASS | 实际登录 `200`（`req_01a21ddd34235d3d78203b8b`）→管理员主壳；Windows `WinVaultKeyring` 有令牌。为该轮使用独立的凭据项和应用数据目录：扫描其中应用文件，未发现本次密码、访问令牌或刷新令牌原值；退出后库项已清。默认配置文件只有 `recent_server_url`、`recent_username`。 |
| 401 单飞与双路重放 | PASS | **受控 401 + 实机刷新**：详情和归档两个并发请求在客户端接收边界各注入一次 `TOKEN_EXPIRED`；仅 1 次真实 `POST /auth/refresh` → `200`（`req_01a21ddccda8405f358ddb69`），两路真实重放均 `200`。未将注入的 401 记为 ECS 自然到期；流式文件并发另有 P4 自动化覆盖。 |
| 退出、重登、迟到响应隔离 | PASS | 两次退出均 `204`，重登 `200`（`req_01a21ddd366dde2511709a80`）。挂起一份真实旧详情响应→切换至另一地址（不向其发凭据）→恢复原 ECS→释放响应，抛 `SessionInvalidatedError`，新 epoch=3 留在总览。切换后内存无 access token；双实例同切片目录隔离另经离线测试通过。 |
| 退出/切换后清理登录控件 | **FAIL** | 实际 `logout 204` 后原账号和密码仍在输入框；独立用非敏感标记复核切换前开启“显示”后，返回登录页仍 `showPassword=true`、原标记仍在。**阻断：QA-01。** |
| viewer 写入口、服务端 403、本机归档 | **BLOCKED** | 未获 viewer 凭据。未把 admin 的 401 或本地拦截当作服务端 403；`test_viewer_blocked_from_server_writes_but_allowed_archive_reads` 仅证明客户端权限分支；需用真实 viewer 补测 UI、403 及其本机同步。 |

## 4. 阶段 2｜已知问题重点回归

| 用例 | 结果 | 实测证据 |
|---|---|---|
| 点击同步安全组 | PASS | `POST /groups/grp_01a21ddace6672a296da500e/actions/sync-security-group` → `202`，`req_01a21ddad790b6406b66a6ad`；`op_01a21ddad7962420d886a414` 两步骤 `reconcile_security_group → verify_security_group` 均 `succeeded`。 |
| 独立 `verify` | PASS | 同组 `/actions/verify` → `202`，`req_01a21ddadd6cf9a79b7cdd60`；`op_01a21ddadd7350ec2c25d48b` 实际步骤为 `inspect_actual_runtime → reconcile_state`，全部成功。两动作均无 `cancelled`、`STALE_GENERATION` 或代次错误。 |
| 云端 `needs_verification`、建议及管理员重试 | N/A | 实机未进入此终态；未人为切断 RAM/云网络。`test_needs_verification_stops_auto_poll_and_allows_admin_retry` 已过；不能作为实机重试成功。 |
| 无写静置 ≥45 s，列表/详情/界面 | PASS | 第 **0.12、15.05、31.05、46.06 s** 分别读取同组列表与详情，`group/router/mavproxy/security_group.stale` 八个位置每次均 `false`，VM 未标过期。末次列表 `req_01a21ddb94f32dbef73226f8`、详情 `req_01a21ddb952ea9d29559068e`。 |
| `observed_at` 是否真的更新 | PASS | 临时组 group/router/mavproxy 从 `16:33:32.963Z` 推进至 `16:34:14.258Z`。安全组在这 46 s 内没有刷新，另对**未写入的原组**跨云巡检窗口补测，安全组从 `16:35:24.297Z` 推进到 `16:37:24.852Z`，而非仅把 `stale` 写死为 false。只读参考配置默认本地巡检 10 s、云端 120 s。 |
| 已连接飞控不被改回 waiting | N/A | 无真实飞控心跳；无依据推断在线巡检行为。 |
| 服务卡标题、连线中心 | PASS | 新建 [configured](live-e2e-evidence/configured.png)：`MAVProxy 会话`、中心 `未启动`；[启动后](live-e2e-evidence/running.png)：中心 `转发中`、Router 标签 `运行中`、MAVProxy `等待心跳`；均来自对应独立服务。 |
| 整个详情页清除旧文案 | **FAIL** | 服务卡已改，但宽屏右侧日志仍是“MAVProxy 旁路会话日志”。见 QA-06。 |

## 5. 阶段 3｜端口组写操作

| 用例 | 结果 | 实测证据 |
|---|---|---|
| 新建双端口、异步初态 | PASS | 正式创建体仅 `name,dtu_port=31060,gcs_protocol=tcp,gcs_port=31061`，无 SYSID；`202`，后续 GET 追踪。落态 `configured_stopped/stopped/disconnected`，安全组 `synced`，未自动启动。 |
| 轮询节奏 | PASS | `restart` 真实轮询相邻响应约 0.55–0.61 s（含网络）；末尾另一次验收读回不计入调度。在所测 UI 操作中未取得跨 5 s 的后段轮询样本；后段 1–2 s 由 `test_intent_key_manager_and_operation_polling_cadence` 的时钟测试验证。 |
| 启动 → 重启 → 停止 | PASS | `op_01a21ddb9565db9783a998ac`、`op_01a21ddb9cc63f3b0ede29d6`、`op_01a21ddbe096dcc8cb0d8d17` 均 `succeeded`。运行时 Router `running`、MAVProxy `waiting`；停止后 `configured_stopped/stopped/disconnected`。 |
| 编辑预演 | PASS | `PATCH ?dry_run=true`、`If-Match: "v1"` → `200`，`req_01a21ddd8119a7fe027acf61`；草稿 UDP，回读仍 TCP，UI 明示“预演结果（未执行，HTTP 200）”，无“配置已应用”。[截图](live-e2e-evidence/dry-run.png) |
| 正式编辑 | PASS | `PATCH` 带 UUID 幂等键及 `"v1"` → `202`，`req_01a21ddd838f5e95ee871a53`；`op_01a21ddd8395def9d5b1994d` 五步成功。 |
| 双击、防重、同意图重发 | PASS | 按钮提交后立即再次调用同一提交槽，首次只发出一份；重建另按原键和原载荷真实重发，两次 202 绑定同一 `op_01a21ddda835426740763f90`。该新组服务端操作列表仅一条 create。模拟丢包重试另由 P3 测试覆盖。 |
| 412 保留草稿 | PASS | 编辑器持 v2，另一请求只改本测试组至 v3；旧 `"v2"` → `412 CONFIG_VERSION_MISMATCH`，`req_01a21ddd9331ffc4e6d85359`。`expected=2,current=3`；名称、协议及两端口保留，自动加载 v3，重新确认后 `"v3"` → 202 并成功。[截图](live-e2e-evidence/conflict-412.png) |
| 409 端口冲突 | PASS | 临时重名以外的另一组名申请已占用 `31060` → `409 PORT_CONFLICT`，`req_01a21ddd9e7bbb62a6e78844`；UI/字段模型有占用者、`dtu_port` 与具体端口。 |
| 422 字段定位 | PASS | UI 输入端口 0，被本地 `dtu_port` 校验挡住；同载荷通过 API 发至 ECS → `422 VALIDATION_ERROR`，`details[0].field=dtu_port`，`req_01a21ddd9eb6143a038ea400`。这是两层证据，UI 的本地提示不是从服务端收到的 422。 |
| 未保存离开 | PASS | 带草稿点“取消”出现“继续编辑 / 放弃更改”。[截图](live-e2e-evidence/unsaved.png) |
| 删除提示、ETag、归档跳转 | PASS | 提示保留未到期历史及本机副本；`DELETE` 带 `"v4"` → `202`（`req_01a21ddda06ec26bf2f6bb8d`），五步成功；原详情 `404 GROUP_NOT_FOUND`（`req_01a21ddda5f633d09961fbab`）→归档 GET `200`（`req_01a21ddda617557abc89a178`）→`historyDetail`，ID 一致。 |
| 同名同端口重建 | PASS | `QA-1ef75364` 的旧 ID `grp_01a21ddd71aee438126b18e4`，新 ID `grp_01a21ddda83489fe084d902d`。两个归档详情分别 `deleted=true/false`。历史**列表**的缺项单列在 QA-02，不算独立展示全面通过。 |

## 6. 阶段 4｜只读视图、日志、交互与视觉

| 用例 | 结果 | 实测证据 |
|---|---|---|
| 整机与分组状态独立 | PASS | [EXE 总览](live-e2e-evidence/exe-start.png)有 `flightlink-api/agent/archive` 三项独立观测；[EXE 详情](live-e2e-evidence/exe-detail.png)为 Router、MAVProxy 会话、安全组。 |
| 遥测与 GCS 指令 | PASS | 同一真实空组 12 卡值均为 `—`，非模拟 0；[展开指令](live-e2e-evidence/gcs-expanded.png)为空态只读，无发送入口。 |
| 真实 0 / 0.0 / false 与链路流光 | N/A | 无硬件。离线格式化测试确认 `0.0 V`、`0.0 m`、`false → 未解锁`（不是 `—`）。实际启动但未连接截图中没有伪造流光。 |
| 500 行增量、清屏、暂停滚动 | PASS | 真实 QML ListView 注入**仅本机**的 520 行标记数据：插入 3 批，裁剪/清屏合计 remove 2、modelReset 0；暂停后追加 40 行，视口 `contentY=3500` 未跳走；清屏前 500 行、清后 0，游标不变，该时段无写请求。[测量](live-e2e-evidence/supplement.jsonl) |
| 暂停页面轮询，归档与 operation 继续 | PASS | 停止周期详情/日志轮询期间，重启 operation 持续 GET 到 `succeeded`；约 17 s 观察窗中后台 `/archive/changes` 返回 200（`req_01a21ddbbc98e2d193dd7a75`）。 |
| 暂停期间严格冻结页面读数 | **FAIL** | operation 到终态时仍另外发一次详情 GET（`req_01a21ddbac6d6c5e30e9ba49`），会应用回包。并非持续轮询，也不是归档请求。见 QA-07。 |
| 登录窗口拖拽、缩放 | PASS | 独立 EXE 实际标题栏拖动、右下角缩放：物理外框从 `(720,168)-(1200,853)` 移至 `(756,191)-(1236,876)`，再放大至 `(756,191)-(1288,915)`。[记录](live-e2e-evidence/exe-window.json) |
| 登录最小尺寸无裁切 | **FAIL** | 在受支持的 `360×480` 空表单触发错误，卡片盖住标题栏、底部说明不可见。见 QA-03。 |
| 主窗口三档布局 | PASS | 1280×800 / 1440×900 / 1600×1000 的侧栏实测 192/208/208；详情 `contentWidth == viewportWidth` 分别 1088/1232/1392；三项服务及 12 卡齐全，遥测区底部 y=594/640/640。窄屏日志标签、两档宽屏双窗格。[1280](live-e2e-evidence/detail-1280.png) · [1440](live-e2e-evidence/detail-1440.png) · [1600](live-e2e-evidence/detail-1600.png) |
| 快捷键、焦点及原生窗口 | PASS | Ctrl+1/2/3/4 对应四页。总览轮询中 Ctrl+K 输入 `qa`，3 s 后仍有焦点；Esc 清空文本，搜索结果 1→0、弹层关闭。原生状态 `Maximized → Windowed → Minimized`；EXE 关闭退出 0。 |
| 控件主题与动效 | **FAIL** | 详情动作、编辑弹窗和历史页中可见 Qt Basic 方形灰按钮，与同屏圆角字段和主按钮不一致。展开区直接切换，减少动画设置没有接入系统。见 QA-05；不以静态截图判定帧率。 |

## 7. 阶段 5｜本机自动归档与恢复

| 用例 | 结果 | 实测证据 |
|---|---|---|
| 登录即同步、实例隔离 | PASS | 首次密码登录、尚未打开历史时 `/archive/changes` → `200`（`req_01a21ddd35ef0ccdf7d1d155`）；恢复会话后也在约 15 s 周期读取。SQLite `sync_cursors` 只有当前 ECS 的一条记录；两实例同 ID 不串目录已有 P4 实际临时文件测试。 |
| Known Folder、SQLite、临时文件 | PASS | Windows 文档解析到 `C:\Users\Lehuang\Documents\FlightLink\Logs`；`%LOCALAPPDATA%\FlightLink\archive_sync.sqlite3` 实有 `sync_cursors/local_sessions/local_files`，任务 0/0；本实例目录树 `.part` 数 0。 |
| 真切片三文件、远端 SHA-256/字节数 | N/A | 无已封存切片，所以“0 个残留”不等同于已验证下载。真实三文件与 `X-Content-SHA256` 比对待有切片再做；P4 的临时目录用例实际覆盖固定文件名、校验、原子替换。 |
| 常规 UI 无下载/导出 | PASS | 实际界面和 QML/路由约束测试未见常规导出、下载入口；仅最终失败有“重新下载日志”分支。 |
| saved / saved_with_source_gaps / failed / expired_on_server | PASS | **离线状态机及 QML**：完整落盘为 saved；缺源可用部分保存且不提示重试；损坏校验为 failed；410 停重试并保留已校验文件。真机无相应切片，不报这四种 ECS 数据态已目测。 |
| 元数据优先、展开后 `/entries` | PASS | 实机历史列表/详情只读 `archive/groups`、单组元数据及 `/sessions`；未展开没有 `/entries`。有切片的懒加载/分页路径经 `test_deleted_group_404_redirects_to_archive_only_when_archive_200_and_lazy_entries` 及客户端代码核查；实机翻页无样本。 |
| 活动空组、已删空组详情 | PASS | 同名新旧组直达归档详情均可呈现空态，旧 `deleted=true`、新 `false`。 |
| 已删组在历史列表可发现 | **FAIL** | `include_deleted=true` 的列表省略已删空组，而同一 ID 的详情仍 `200/deleted=true`。见 QA-02。 |
| 同步时关闭再重启、已验文件不重复下 | N/A | 实机清单为空，无正在传输的文件可中断。已跑 P4 的第二文件中断、重启只补缺件、改名后数据库未提交的恢复用例；不能替代真实 ECS 文件流。 |

## 8. 缺陷与定位

### P1｜QA-01：退出后密码仍留在登录页（桌面端，阻断）

1. 在新启动的登录页输入测试账号与密码，正常登录，再从用户菜单退出；在同一进程检查登录表单是否为空。**复测只比较是否为空，不记录文本，也不要截取显隐后的界面。**
2. `POST /api/v1/auth/login`，JSON `{username:ops_admin,password:[redacted]}` → `200`；`POST /api/v1/auth/logout`，`Authorization: Bearer [redacted]`、体 `{refresh_token:[redacted]}` → `204`，空体，`request_id=req_01a21ddd36066d0da10ff3c6`。库项已清；`password_retained_after_logout=true`，重登成功。非敏感标记的切换测试还证明显隐状态可一并保留。[布尔证据](live-e2e-evidence/password-flow.json)。
3. `qml/Main.qml:225–230` 用 `visible` 切换同一个 `LoginPage`；`LoginPage.qml` 未在认证边界清除密码及显隐状态。建议成功登录后立即清空密码，退出、过期、换址都重置输入状态；对“上一会话已开启显示”增加窗口级回归。

### P2｜QA-02：历史列表漏掉已删除且无保留切片的组（后端）

1. 新建不接飞控的组，等 202 成功后删除；记录旧 ID。可用同名同端口重建以检查两者的可发现性。打开历史列表，再按旧 ID 读归档详情。
2. 契约 `openapi.yaml:595–606,617–625` 描述含已删组，`include_deleted` 默认 true，未声明“仅含有未过期切片的已删组”。两个读取均 `Authorization: Bearer [redacted]`，无请求体：

   | 方法与路径 | HTTP / request_id | 响应体要点 |
   |---|---|---|
   | `GET /api/v1/archive/groups?include_deleted=true` | `200` / `req_01a21ddfa2c5e3f3b4ee3f74` | `items` 仅原活动组 `grp_01a21dba3397d66c38551786`，无已删测试组。 |
   | `GET /api/v1/archive/groups/grp_01a21ddd71aee438126b18e4` | `200` / `req_01a21ddfa2f249cc4cbe7f65` | 同 ID、`name_snapshot=QA-1ef75364`、`deleted=true`，活动/封存数均 0，`latest_session=null`。 |

   **[两份完整响应体、请求与关联 ID](live-e2e-evidence/archive-contract.json)**。这是业务语义偏差，两响应本身都能满足 JSON schema。
3. 只读后端参考 `src/flightlink/archive/service.py:834–836` 显式跳过此类组。建议按现契约返回；若产品决定空的已删组应隐藏，先明确契约和验收范围。不要让桌面端按名称补拼旧组。

### P2｜QA-03～QA-08

| 编号 / 归属 | 最短复现、实测与定位 | 建议 |
|---|---|---|
| QA-03 登录最小窗口裁切 / 桌面端 | 缩至 `360×480`，空账号提交。错误横幅出现，卡片顶端 y=18 落入 40 px 标题栏，底部说明出界。[截图](live-e2e-evidence/login-min-error.png)。本地校验，无 HTTP/request_id。`Main.qml:26–27`、`LoginPage.qml:60–79`。 | 按含错误态的内容计算最小高度，或给登录主体提供垂直滚动；保持标题栏可操作。 |
| QA-04 实例 ID 不可见 / 桌面端 | 探测连接，只有“ECS 已连接，…ms”；`GET /api/v1/health` 无头/体，`200`，响应有正确 `ecs_instance_id`，[完整体](live-e2e-evidence/archive-contract.json)，`req_01a21ddf9c860bd303cbd3b3`。`session_vm.py:198–205` 保存了 ID，但未放进状态文案，QML 无对应展示。 | 在服务器信息或状态详情显示可复制的实例 ID，保留简短 RTT。 |
| QA-05 主题与动效不一致 / 桌面端 | [EXE 详情](live-e2e-evidence/exe-detail.png)的启动、重启、同步、删除均为同形方灰块；[预演弹窗](live-e2e-evidence/dry-run.png)的协议选择、预演、取消与圆角提交按钮不成套；[历史页](live-e2e-evidence/history.png)刷新/查看历史同样如此。`GroupDetailPage.qml:78–118`、`GroupFormDialog.qml:190–198,310–325` 使用未定制 Basic 控件。指令展开直接切 `visible`（`GroupDetailPage.qml:395,425`）；`Theme.qml:93–95` 的 reducedMotion 默认 false，未见系统偏好绑定。窗口交互无独立 request_id。 | 优先统一次级/禁用/危险按钮的圆角、焦点、间距及色彩；展开用短过渡，接系统减少动画设置。未评测真实飞控流光的流畅度。 |
| QA-06 旧文案残留 / 桌面端 | 宽度 1440/1600 打开详情，或窄屏切 MAVProxy 日志，标题仍含“旁路”。[宽屏证据](live-e2e-evidence/detail-1440.png)。`GroupDetailPage.qml:555` 硬编码；与接口无关，无独立 request_id。 | 日志标题统一为“MAVProxy 会话日志”，把可见子页面文案也纳入回归。 |
| QA-07 暂停时终态回调仍刷新读数 / 桌面端 | 在详情暂停实时更新，再重启本测试组；周期轮询停止、归档和 operation 正常，但终态回调额外 `GET /api/v1/groups/grp_01a21ddace6672a296da500e`，鉴权头已脱敏、无体，`200`，`ETag: "v1"`、`lifecycle_state=running`，`req_01a21ddbac6d6c5e30e9ba49`。`operations_vm.py:789–796` 直接刷新当前页，未判断暂停。 | 继续展示独立 operation 进度；暂停时延迟页面刷新至恢复。若终态刷新是特例，需在产品规则中明示。 |
| QA-08 默认 pytest 未取到 QML 输出 / 桌面端测试工具（Windows 环境触发） | 原命令及 `pytest --lf` 均失败在 `tests/test_qml_quick.py:29`，子进程 rc=0 但未捕获 PASS 行；显式写文件则 18 passed。无 HTTP/request_id。 | Qt 测试显式输出至临时文件、按指定编码解析，或在测试入口设置可复现的日志环境。 |

**P0：无实测发现。** 另有一次只读操作列表补抓没有收到 HTTP 响应，因而无状态码或 request_id；独立重读四个测试组均 `200`，未定位为后端缺陷。实机抽样进行了状态码及 JSON 响应 schema 检查；对于列出的异常场景，401/404/409/412/422 都是预期错误，不计作契约偏差。

## 9. 复现、清理与放行条件

在前端仓库根目录使用 PowerShell：

```powershell
git rev-parse HEAD
.\.venv\Scripts\pytest.exe -v
# 独立 QML 输出（Qt 进程的统计含 init/cleanup）
$env:QT_QPA_PLATFORM='offscreen'
$env:QT_QUICK_CONTROLS_STYLE='Basic'
.\.venv\Scripts\python.exe tests\qml\run_qml_tests.py -o "$env:TEMP/flightlink-e2e-qml.txt,txt"
# 本机复现全量通过时使用的组合
$env:QT_FORCE_STDERR_LOGGING='1'
$env:QTEST_WINRT_STDERR='1'
$env:PYTHONUTF8='1'
.\.venv\Scripts\pytest.exe -v
```

**桌面复测另开新 PowerShell**（不继承 `offscreen`），运行 `.\dist\FlightLinkDesktop\FlightLinkDesktop.exe --skip-restore`，显式输入完整 HTTP 地址，在掩码框输入密码。先记录 `/groups` 的原有 ID；用独一测试名及两个未占用端口，按阶段 2–3 表操作。每个写意图使用不同 UUID，同一次重放使用原 UUID；只对本次创建的 ID 做写操作。追踪 202 时保存 operation ID 和接收响应的 request ID，直到终态，不以 202 代替成功。静置以本机单调时钟计时，安全组时间戳跨约 120 s 的巡检周期再比。

**实机清理已确认。** 含采集器中途收尾及续测，共产生 **4 个临时 group_id、16 个独立 operation，全部 `succeeded`**。[按 group_id 复核](live-e2e-evidence/operations-check.json)；每个临时 ID 均有成功的 delete。最后 `GET /api/v1/groups?filter=all` → `200`，`req_01a21dde72f225f26f275447`，`total=1`，只剩原有 `grp_01a21dba3397d66c38551786`，与开测基线一致。测试未保留任何运行组；按产品语义保留已删组归档元数据。组删除的步骤报告了撤销规则和释放端口成功，未另行登录云控制台核验。

**复验门槛：** 先修 QA-01 并在重打的便携版上复验正常登录、显示密码、退出、切换、过期四种边界；修复或书面裁决 QA-02 和暂停语义，再复验最小尺寸、主题及默认测试命令。真实 viewer 的 403/本机归档与真实切片校验/中断恢复需补独立证据；硬件在线项保留 N/A，直至有飞控/GCS 的专场验收。
