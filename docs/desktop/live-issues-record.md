# FlightLink Desktop 1.0 — 实机联调问题记录

> 遵循项目契约约束：仅以 `docs/api/openapi.yaml` 作为唯一 HTTP 契约；不在桌面端编造兼容字段，也不修改只读后端参考目录 `D:\Workspace\Mavproxy\FlightLink-backend`。

---

## 一、后端实机问题（待后端修复）

### 1. `sync-security-group` / `verify` 操作必现 `STALE_GENERATION` 取消

* **记录日期**：2026-11-28
* **触发请求**：`POST /api/v1/groups/{group_id}/actions/sync-security-group`
* **实机观察响应**：
  * 受理返回 `202 Accepted`，获得操作号 `op_01a21dbba9eddcde0656fdae`。
  * 轮询 `GET /api/v1/operations/op_01a21dbba9eddcde0656fdae` 后立即终态为：
    * `status`: `cancelled`
    * `error_code`: `STALE_GENERATION`
    * `error_message`: `Superseded by newer operation generation.`
    * `steps`: `[pending] reconcile_security_group` → `[pending] verify_security_group`（均未执行）
* **后端根因定位（只读核查）**：
  * `FlightLink-backend/src/flightlink/domain/operations_repo.py`（`enqueue_group_action`，L1079–L1163）计算了 `new_gen = int(group["operation_generation"]) + 1`，但 `sync_security_group` 与 `verify` 分支漏写了对 `port_groups.operation_generation = new_gen` 的更新，仅在 `operations` 表写入了 `generation = new_gen`。
  * `FlightLink-backend/src/flightlink/domain/lifecycle.py`（`execute_operation`，L535–L543）随后校验 `int(group["operation_generation"]) != op_gen` 恒为真，直接将操作取消。
* **桌面端处理策略**：保持严格按 OpenAPI 契约提交并如实展示后端状态，不做客户端绕过或伪造。

### 2. 无写操作 30 秒后 `router`、`security_group` 及 `group` 持续返回 `stale: true`

* **记录日期**：2026-11-28
* **触发接口**：`GET /api/v1/groups`、`GET /api/v1/groups/{group_id}`
* **实机观察现象**：
  * 端口组创建并静置超过 30 秒后，页面上 `Router` 与 `安全组` 持续显示「已过期」（`router.stale = true`、`security_group.stale = true`），而尚未启动过的组因 `mavproxy_observed_at IS NULL`，`mavproxy.stale` 暂时返回 `false`。
* **后端根因定位（只读核查）**：
  * `FlightLink-backend/src/flightlink/config.py`（L54）配置 `stale_after_seconds = 30`，`operations_repo.py`（L1254–L1342）统一据此判定各服务及整组是否过期。
  * `FlightLink-backend/src/flightlink/domain/agent_runner.py`（L48–L65）主循环仅在启动时执行 `reconcile_on_startup()`，运行期间只调用 `process_pending_operations()`，未周期性刷新各端口组的本地运行态与云安全组观测时间戳。
* **桌面端处理策略**：按契约继续独立渲染 `state`、`observed_at`、`stale`，不在前端隐藏或吞掉后端返回的 `stale: true`。

---

## 二、桌面端 UI 文案与状态展示修复

### 1. `MAVProxy 旁路` 改为 `MAVProxy 会话`
* **问题**：此前在 `formatters.py` 中将服务卡标题写为内部架构术语 `MAVProxy 旁路`（及运行态副文本 `旁路观测中`），容易让使用者误解为“被绕过/未启用”，且与视觉参考稿（`Mavproxy 会话`）不一致。
* **修复**：
  * `src/flightlink_desktop/models/formatters.py`：服务卡标题改为 `MAVProxy 会话`，运行态兜底副文本改为 `会话观测中`。
  * 同步更新单元测试 `tests/test_p2_models_and_polling.py` 与 QML 测试 `tests/qml/tst_DetailLayout.qml`。

### 2. 连线图中心节点 `已停机` 与 Router 实际状态标签对齐
* **问题**：新建端口组默认处于 `configured_stopped`（正常未启动），状态标签显示为 `未启动`，但 `LinkWireCard.qml` 中心节点硬编码显示为 `已停机`，容易引起“异常宕机”误解；同时连线图此前按整组 `lifecycle_state === "running"` 判定转发态，未直接使用独立的 `router.state`。
* **修复**：
  * `src/flightlink_desktop/qml/components/LinkWireCard.qml`：新增 `routerStatusText` 属性，运行中显示 `转发中`，非运行态优先显示对应 `router` 状态文案，默认兜底 `未启动`（不再使用 `已停机`）。
  * `src/flightlink_desktop/models/list_models.py`、`OverviewPage.qml`、`GroupDetailPage.qml`：连线图直接使用 `router.state === "running"` 与 `router.stateLabel`，保持与「服务状态卡片」完全一致。

---

## 三、实机 E2E 验收（`live-e2e-test-report.md`）后续修复记录

对照 2026-11-28 实机全量验收报告，桌面端已完成全部 7 项修复，后端 1 项（QA-02）待后端修复：

* **QA-01（P1 阻断，已修）**：`LoginPage.qml` 在登录成功、退出登录、会话过期及切换服务器时立即清空密码框、账号框并重置 `showPassword = false`，防止同进程返回登录页残留凭据或明文显隐状态。
* **QA-02（P2 后端）**：`GET /api/v1/archive/groups?include_deleted=true` 省略已删空组（`FlightLink-backend/src/flightlink/archive/service.py:834-836`），与单组 `GET /archive/groups/{id}` 返回 `200 / deleted=true` 不一致；桌面端不编造兼容，交由后端按 OpenAPI 契约修复。
* **QA-03（P2，已修）**：`Main.qml` 主体容器增加 `clip: true`，`LoginPage.qml` 改为带 `Flickable` 的居中滚动容器（`y >= 12`），在 `360×480` 最小尺寸显示错误横幅时绝不覆盖 40px 标题栏，底部说明完整可滚可见。
* **QA-04（P2，已修）**：`session_vm.py` 在健康探测与登录状态文案中纳入 `ecs_instance_id`，并在 `AppShell.qml` 底栏、侧栏用户菜单和 `OverviewPage.qml` 头部展示且支持一键复制。
* **QA-05（P2，已修）**：新增 `AppButton.qml` 与 `AppComboBox.qml`，全站替换裸 Qt Basic 按钮/下拉框，统一圆角、色阶、禁用态与焦点环；为详情页地面站指令折叠区补充受 `Theme.reducedMotion` 控制的短过渡，并在 `app.py` 接入 Windows 系统 `SPI_GETCLIENTAREAANIMATION` 减少动态偏好。
* **QA-06（P2，已修）**：将 `GroupDetailPage.qml` 右侧日志标题由 `MAVProxy 旁路会话日志` 统一为 `MAVProxy 会话日志`，全仓已无「旁路」UI 残留。
* **QA-07（P2，已修）**：`operations_vm.py` 的 `_on_operation_terminal()` 检查 `workspace.liveUpdatesEnabled`，在「暂停实时更新」期间不再额外发起页面 GET，待用户恢复实时更新时自动刷新。
* **QA-08（P2，已修）**：`tests/test_qml_quick.py` 显式通过 `-o <tmp_file>,txt` 写入 UTF-8 结果文件并解析，消除 Windows 默认控制台下 `pytest -v` 捕获不到 QtTest 输出的问题。

