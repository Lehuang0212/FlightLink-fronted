# FlightLink Desktop 1.0 — OpenAPI 契约映射表

> 唯一 HTTP 契约来源：[docs/api/openapi.yaml](../api/openapi.yaml)（25 个接口）。
> 桌面端未改动后端、未编造兼容字段；常规桌面 UI 严禁调用 `/api/v1/logs/export` 与 `/api/v1/archive/sessions/{session_id}/download`。

| # | Tag | Method & Path | `operationId` | 桌面端调用方 | 轮询 / 约束策略 |
|---|---|---|---|---|---|
| 1 | Health | `GET /api/v1/health` | `getHealth` | `api/client.py::probe_health` -> `SessionViewModel.probeHealth` / `login` | 登录前测连通性与 RTT，获取 `ecs_instance_id`；只读无副作用 |
| 2 | Auth | `POST /api/v1/auth/login` | `login` | `api/client.py::login` -> `SessionViewModel.login` | 无演示账号/预填凭据；401 `INVALID_CREDENTIALS` 不触发 refresh |
| 3 | Auth | `POST /api/v1/auth/refresh` | `refreshToken` | `api/client.py::_raw_refresh` -> `AuthCoordinator.refresh_single_flight` | 仅 `401 TOKEN_EXPIRED` 触发单飞刷新（页面与归档共享），最多重放一次 |
| 4 | Auth | `POST /api/v1/auth/logout` | `logout` | `api/client.py::logout` -> `SessionViewModel.logout` | 立即递增会话 epoch 清态并撤销远端 refresh_token |
| 5 | Auth | `GET /api/v1/auth/me` | `getCurrentUser` | `api/client.py::get_me` | 校验当前会话与角色（`admin`/`viewer`） |
| 6 | Overview | `GET /api/v1/overview` | `getOverview` | `WorkspaceViewModel.pollOverview` -> `OverviewPage.qml` | 总览页每 2.5s 非重叠轮询；离页或暂停实时更新即停 |
| 7 | Groups | `GET /api/v1/groups` | `listGroups` | `WorkspaceViewModel.pollGroups` -> `GroupsPage.qml` | 端口组页每 2.5s 非重叠轮询；支持 `q`/`filter`；按 `group_id` 就地更新不丢焦点 |
| 8 | Groups | `POST /api/v1/groups` | `createGroup` | `OperationsViewModel.submitDialog` -> `GroupFormDialog.qml` | 仅 `admin`；双端口（DTU 固定 UDP，无 SYSID）；`Idempotency-Key`；`202` 追踪 |
| 9 | Groups | `GET /api/v1/groups/{group_id}` | `getGroup` | `WorkspaceViewModel.pollGroupDetail` -> `GroupDetailPage.qml` | 详情页每 1.5s 非重叠轮询；记录 `ETag`；`404 GROUP_NOT_FOUND` 转查 `/archive/groups/{id}` |
| 10 | Groups | `PATCH /api/v1/groups/{group_id}` | `updateGroup` | `OperationsViewModel.runEditDryRun` / `submitDialog` | `?dry_run=true` 返回 `200` 预演；正式提交带 `If-Match`+`Idempotency-Key` 返回 `202`；`412` 保草稿重载 |
| 11 | Groups | `DELETE /api/v1/groups/{group_id}` | `deleteGroup` | `OperationsViewModel.confirmDeleteGroup` -> `DeleteGroupDialog.qml` | 二次确认说明历史保留；带 `If-Match`+`Idempotency-Key` 返回 `202` |
| 12 | Groups | `POST /api/v1/groups/{group_id}/actions/{action}` | `triggerGroupAction` | `OperationsViewModel.triggerGroupAction` -> `GroupDetailPage.qml` | `start`/`stop`/`restart`/`sync-security-group`/`verify`；带 `Idempotency-Key` 返回 `202` |
| 13 | Operations | `GET /api/v1/operations` | `listOperations` | `api/client.py::list_operations` | 查询最近异步操作记录 |
| 14 | Operations | `GET /api/v1/operations/{operation_id}` | `getOperation` | `OperationsViewModel._poll_active_operation` | 前 5s 每 500ms，之后每 1.5s；`needs_verification` 停轮询；网络恢复继续查原操作 |
| 15 | Operations | `POST /api/v1/operations/{operation_id}/retry` | `retryOperation` | `OperationsViewModel.retryActiveOperation` | 仅 `admin` 且 `retryable=true` 时可见；返回 `202` |
| 16 | Logs | `GET /api/v1/logs` | `queryLiveLogs` | `WorkspaceViewModel.pollLiveLogs` / `_poll_detail_log` -> `LogPane.qml` | 每 1.5s 游标增量追加至 500 行环形模型；`410 CURSOR_EXPIRED` 重置游标 |
| 17 | Logs | `GET /api/v1/logs/export` | `exportLiveLogs` | **常规桌面 UI 禁用（未调用）** | 仅 CLI/排障用途，自动化测试守卫禁止源码引用 |
| 18 | Archive | `GET /api/v1/archive/groups` | `listArchiveGroups` | `WorkspaceViewModel.loadArchiveGroups` -> `HistoryPage.qml` | `include_deleted=true`；仅元数据；保留已删组与空组，不按名称合并 |
| 19 | Archive | `GET /api/v1/archive/groups/{group_id}` | `getArchiveGroup` | `WorkspaceViewModel.pollGroupDetail` / `loadArchiveGroupDetail` | 删组 404 后判定 `200` 才跳转历史页 |
| 20 | Archive | `GET /api/v1/archive/groups/{group_id}/sessions` | `listArchiveGroupSessions` | `WorkspaceViewModel.loadArchiveGroupDetail` -> `HistoryDetailPage.qml` | 仅元数据，保留展开状态 |
| 21 | Archive | `GET /api/v1/archive/sessions/{session_id}` | `getArchiveSession` | `api/client.py::get_archive_session` | 切片元数据与来源缺口详情 |
| 22 | Archive | `GET /api/v1/archive/sessions/{session_id}/entries` | `getArchiveSessionEntries` | `WorkspaceViewModel.loadSliceEntries` -> `HistoryDetailPage.qml` | 仅展开切片后按 `router`/`mavproxy` 懒加载分页正文 |
| 23 | Archive | `GET /api/v1/archive/changes` | `listArchiveChanges` | `ArchiveSyncEngine.poll_manifest` (`ArchiveSyncWorker`) | 登录后自动每 15s 轮询；按 `ecs_instance_id` 隔离游标；先事务落任务再推游标；`410 CURSOR_EXPIRED` 记缺口并限次空游标对账 |
| 24 | Archive | `GET /api/v1/archive/sessions/{session_id}/files/{file_id}` | `readArchiveSessionFile` | `ArchiveSyncEngine._download_and_verify_one` | `httpx.stream()` 写 `.part` 核对长度与双重 SHA-256 后 `os.replace()`；`viewer` 亦可执行；`410 ARCHIVE_EXPIRED` 停重试 |
| 25 | Archive | `GET /api/v1/archive/sessions/{session_id}/download` | `downloadArchiveSession` | **常规桌面 UI 禁用（未调用）** | 仅 CLI/兼容用途，自动化测试守卫禁止源码引用 |
