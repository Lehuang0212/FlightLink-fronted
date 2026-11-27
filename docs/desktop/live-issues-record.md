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
