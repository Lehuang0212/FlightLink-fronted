# FlightLink Desktop 1.0 — 视觉对照截图索引

- **生成方式**：`.\.venv\Scripts\python.exe scripts\capture_screenshots.py` 与 `QT_SCALE_FACTOR=1.25` 附加检查（使用测试侧 `httpx.MockTransport` 驱动真实 `QGuiApplication` + `QQmlApplicationEngine` 窗口 `grabWindow()`，生产版无 Mock 模式）。
- **宿主机 Windows 缩放记录**：Windows 11 宿主机原生缩放 `125%`（`devicePixelRatio=1.25`, `logicalDpi=96.0`），即 `1280×800` 逻辑尺寸输出 `1600×1000` 物理像素；额外叠加 `QT_SCALE_FACTOR=1.25`（等效 `1.5625x`）复检高 DPI 排版。
- **视觉核查结论**：三档分辨率及高 DPI 下均无横向溢出、无截断；`1280×800` 详情首屏可见三项独立服务与 12 张遥测卡且日志为双标签，`1440×900` / `1600×1000` 自动切换双窗格并排；正常已保存切片无下载/导出按钮。

## 1. 三档验收分辨率（7 大视图）

| 页面 | `1280×800`（逻辑） | `1440×900`（逻辑） | `1600×1000`（逻辑） |
|---|---|---|---|
| 登录页 | [login_1280x800.png](login_1280x800.png) | [login_1440x900.png](login_1440x900.png) | [login_1600x1000.png](login_1600x1000.png) |
| 总览页 | [overview_1280x800.png](overview_1280x800.png) | [overview_1440x900.png](overview_1440x900.png) | [overview_1600x1000.png](overview_1600x1000.png) |
| 端口组列表 | [groups_1280x800.png](groups_1280x800.png) | [groups_1440x900.png](groups_1440x900.png) | [groups_1600x1000.png](groups_1600x1000.png) |
| 端口组详情 | [detail_1280x800.png](detail_1280x800.png) | [detail_1440x900.png](detail_1440x900.png) | [detail_1600x1000.png](detail_1600x1000.png) |
| 实时日志 | [logs_1280x800.png](logs_1280x800.png) | [logs_1440x900.png](logs_1440x900.png) | [logs_1600x1000.png](logs_1600x1000.png) |
| 历史日志列表 | [history_1280x800.png](history_1280x800.png) | [history_1440x900.png](history_1440x900.png) | [history_1600x1000.png](history_1600x1000.png) |
| 历史切片详情 | [history_detail_1280x800.png](history_detail_1280x800.png) | [history_detail_1440x900.png](history_detail_1440x900.png) | [history_detail_1600x1000.png](history_detail_1600x1000.png) |

## 2. 关键异常、权限、异步操作、归档与 125% DPI 状态

| 场景 | 截图文件 | 核验要点 |
|---|---|---|
| 登录错误 | [state_login_error_1280.png](state_login_error_1280.png) | 无演示入口与预填凭据，内联红色错误条，不触发刷新 |
| 只读角色（`viewer`） | [state_viewer_1280.png](state_viewer_1280.png) | 隐藏左侧新建 FAB 与详情页全部写操作按钮，保留自动归档 |
| `202` 异步操作进行中 | [state_op_202_running_1280.png](state_op_202_running_1280.png) | 明确展示操作号、步骤进度与“执行中（尚未完成）” |
| `needs_verification` 待核实 | [state_needs_verification_1280.png](state_needs_verification_1280.png) | 停止自动轮询，展示步骤、`retry_hint` 与管理员「重试核验」 |
| 空遥测（全部 `null`） | [state_empty_telemetry_1280.png](state_empty_telemetry_1280.png) | 12 张遥测卡严格渲染 `—`，不伪造 `0` 或 `false` |
| 云端缺源（`saved_with_source_gaps`） | [state_source_gaps_1280.png](state_source_gaps_1280.png) | 展示缺源说明，绝不提示重新下载，无重试按钮 |
| 本机归档失败 | [state_archive_failed_1280.png](state_archive_failed_1280.png) | 顶栏、状态栏及失败切片展示分类原因与「重新下载日志」 |
| 重试补下载成功 | [state_archive_retry_ok_1280.png](state_archive_retry_ok_1280.png) | 恢复为「已自动保存」，所有下载按钮自动消失 |
| 125% 附加 DPI（登录） | [state_login_1280_dpi125.png](state_login_1280_dpi125.png) | `QT_SCALE_FACTOR=1.25`（总计 `1.5625x`）居中无截断 |
| 125% 附加 DPI（详情） | [state_detail_1280_dpi125.png](state_detail_1280_dpi125.png) | 三项服务 + 12 张遥测卡 + 双标签无溢出 |
