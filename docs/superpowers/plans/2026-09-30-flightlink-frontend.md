# FlightLink-Console 前端实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在现有 FastAPI 后端上交付一个可部署的 FlightLink-Console 管理前端，支持端口组监控、管理、飞控消息查看和 PCAP 下载。

**Architecture:** 使用 Vue SPA 和同源 REST API；Nginx 提供构建后的静态文件并将 `/api/` 代理到本机 FastAPI。通过带 Cookie 的 Fetch 客户端、Vue Router 会话守卫和可暂停的轮询 composable 管理请求；页面按 overview、channel detail、messages、captures 拆分。

**Tech Stack:** Node.js LTS、npm、Vue 3、TypeScript、Vite、Vue Router、Element Plus、原生 Fetch API；开发验证使用 Vitest 与 Vue Test Utils。

**Spec:** `docs/superpowers/specs/2026-09-30-flightlink-frontend-design.md`

## Global Constraints

- 支持首期 1–5 组端口；通道身份由服务器端口组合确定，不绑定固定无人机设备身份。
- 不显示 EC05-DNC 蜂窝信号强度，不把 MAVLink 链路质量解释为 4G 信号。
- 管理员账户没有网页注册流程，只能由后端 `ConsoleUseradd` 命令创建。
- 不制作阿里云安全组管理页面；安全组规则仍由后端按端口组同步。
- 管理员会话使用后端 HttpOnly Cookie；前端不把会话令牌放入 `localStorage`。
- 首期使用 REST 轮询，不引入 WebSocket、SSE 或额外 Node 服务。
- 总览/端口组状态每 3 秒、打开的单组遥测详情每 2 秒、消息和路由日志每 2 秒、抓包摘要在抓包页可见时每 1 秒、PCAP 列表手动或每 15 秒更新；页面隐藏时暂停轮询。
- Vue 构建产物由 ECS 上的 Nginx 提供；Nginx 外网 HTTPS 监听 TCP `18443`，来源限为管理员公网 IPv4 `/32`。
- `/api/` 由 Nginx 代理到 `http://127.0.0.1:8000`；FastAPI 继续只监听 `127.0.0.1:8000`，不开放 TCP `8000` 或 `8080`。
- HTTPS 部署将 `FLIGHTLINK_SESSION_COOKIE_SECURE=true`；Node.js 只用于开发和构建。
- README 内容必须同时提供中文和英文。
- 按阶段实现；每阶段交付后向用户汇报结果并等待确认，再进入下一阶段。

## Review Focus

- 受保护页面轮询期间会话过期或被撤销时，清除管理员状态并转到登录页；由 Task 3 的 `expires protected session redirects to login` 验证。
- 无遥测、陈旧遥测、通道禁用、路由服务失败、抓包失败和安全组同步失败必须区分显示；由 Task 5 的 `channel summary preserves independent status states` 验证。
- 标签页隐藏、恢复或慢请求时，轮询不能重复并行请求；由 Task 4 的 `polling pauses while hidden and prevents overlap` 验证。
- 端口冲突及安全组同步错误不能误报成功，表单必须保留便于修正；由 Task 5 的 `channel mutation surfaces conflict and provider failures` 验证。
- 当前写入中的 PCAP 不可下载，已关闭文件须携带会话 Cookie 下载；由 Task 6 的 `capture download excludes current segment and downloads closed file` 验证。

---

## 文件结构

前端目录目前只有设计文档与样图，没有现有项目结构；以下路径由本计划新建。

```text
FlightLink-frontend/
├── package.json                         # 开发、检查、构建命令和依赖
├── package-lock.json                    # 锁定 npm 依赖
├── index.html                           # SPA HTML 入口
├── vite.config.ts                       # Vue 插件、路径别名、Vitest 配置
├── tsconfig.json                        # TypeScript 严格检查
├── eslint.config.js                     # Vue/TypeScript 静态检查
├── src/
│   ├── main.ts                          # 创建 Vue 应用、路由及 Element Plus
│   ├── App.vue                          # 根视图
│   ├── router/index.ts                  # 登录守卫和页面路由
│   ├── api/{http,auth,channels,health,types}.ts # HTTP、领域 API 与响应类型
│   ├── auth/session.ts                  # 管理员会话状态与过期处理
│   ├── composables/usePolling.ts         # 可见性、间隔和请求去重
│   ├── components/                      # 布局、状态、终端、表单和卡片
│   ├── pages/                           # Login、Overview、Channels、Detail、Messages、Captures
│   └── styles/                          # 设计 token、全局样式、终端样式
├── src/__tests__/                       # API、会话、轮询、页面和下载验证
├── deploy/nginx/flightlink-console.conf.example
├── docs/deployment.md                   # 中英双语部署步骤
└── README.md                            # 中英双语项目说明
```

## 实施阶段

### 阶段 1：项目脚手架与验证基线

### Task 1：初始化 Vue/TypeScript/Vite 项目结构

**Files:**
- Create: `package.json`, `package-lock.json`, `index.html`, `vite.config.ts`, `tsconfig.json`, `tsconfig.app.json`, `tsconfig.node.json`, `eslint.config.js`
- Create: `src/main.ts`, `src/App.vue`, `src/styles/tokens.css`, `src/styles/global.css`
- Create: `src/__tests__/smoke.spec.ts`

**Interfaces:**
- Produces: `#app` 挂载点；Vue 应用入口；`npm run dev`、`npm run build`、`npm run lint`、`npm run test` 命令。

- [x] **Step 1: 先写 SPA 入口 smoke 测试**
  - `smoke.spec.ts` 读取项目根目录的 `index.html`（文件不存在时按空内容处理），断言包含 `<div id="app"></div>` 和 `/src/main.ts` 模块入口。
- [x] **Step 2: 添加 Vue、TypeScript、Vite、Element Plus、Vitest 和 Vue Test Utils 依赖**
  - 使用创建项目时受支持的 Node.js LTS；将锁文件纳入版本控制。
- [x] **Step 3: 配置 Vue 单文件组件、TypeScript 严格模式、`@` 指向 `src/`、Vitest 和 ESLint**
  - 不加入 UI 模板以外的全套组件库或状态管理框架。
- [x] **Step 4: 运行 smoke 测试确认入口断言失败**
  - Run: `npm test -- --run src/__tests__/smoke.spec.ts`
  - Expected: FAIL，报告 HTML 缺少 `#app` 挂载点；不得因测试导入错误或配置错误失败。
- [x] **Step 5: 创建应用入口和基础样式**
  - `src/main.ts` 挂载 `App.vue`；基础样式建立颜色、字体、间距 token 和窄屏布局基础。
- [x] **Step 6: 验证脚手架**
  - Run: `npm test -- --run src/__tests__/smoke.spec.ts`
  - Expected: smoke 测试通过。
  - Run: `npm run build`
  - Expected: Vite 生成 `dist/`。

**阶段交付：** 可运行的空 SPA、锁定依赖和基础校验命令。交付后暂停并向用户汇报，获批后进入阶段 2。

### 阶段 2：后端 API、登录和控制台框架

### Task 2：实现类型化 HTTP/API 客户端与会话管理

**Files:**
- Create: `src/api/types.ts`, `src/api/http.ts`, `src/api/auth.ts`, `src/api/channels.ts`, `src/api/health.ts`, `src/auth/session.ts`
- Modify: `vite.config.ts` for local `/api` proxying to FastAPI during development.
- Create: `src/__tests__/http.spec.ts`, `src/__tests__/session.spec.ts`, `src/__tests__/channels-api.spec.ts`

**Interfaces:**
- Produces: `apiRequest<T>(path: string, init?: RequestInit): Promise<T>`；`apiDownload(path: string): Promise<Blob>`；API client 将相对路径统一加上 `/api/v1`。
- Produces: `useAuthSession(): { admin: Ref<AdminPublic | null>; isAuthenticated: ComputedRef<boolean>; restore(): Promise<AdminPublic | null>; login(input: LoginRequest): Promise<AdminPublic>; logout(): Promise<void> }`。
- Produces: `listChannels(): Promise<ChannelPublic[]>`、`getChannel(id: string): Promise<ChannelPublic>`、`createChannel(input: ChannelWrite): Promise<ChannelPublic>`、`updateChannel(id: string, input: ChannelWrite): Promise<ChannelPublic>`、`deleteChannel(id: string): Promise<void>`、`restartChannel(id: string): Promise<ChannelPublic>`、`getChannelLogs(id: string, limit?: number): Promise<string[]>`、`getFlightMessages(id: string, limit?: number): Promise<FlightMessagePublic[]>`、`getPacketSummaries(id: string, limit?: number): Promise<PacketSummaryPublic[]>`、`listCaptures(id: string): Promise<CaptureFilePublic[]>`、`downloadCapture(id: string, fileName: string): Promise<Blob>`。
- API 类型必须映射后端 `ChannelPublic`、`ChannelTelemetryPublic`、`RouterRuntimePublic`、`SecurityGroupChannelPublic`、`FlightMessagePublic`、`PacketSummaryPublic` 和 `CaptureFilePublic` 字段。

- [x] **Step 1: 编写 Fetch 客户端行为测试**
  - 验证请求使用相对 `/api/v1` 路径和 `credentials: 'include'`；204 成功不解析 JSON；FastAPI `{detail: ...}` 错误可读；受保护 API 的 401 发出统一会话失效事件，登录凭据错误保留在登录页展示。
- [x] **Step 2: 实现 `src/api/http.ts`**
  - JSON 请求与二进制下载共用凭据和错误映射；不在 URL、日志或浏览器存储中写会话令牌。
- [x] **Step 3: 定义后端响应和请求类型**
  - 创建/更新 payload 为 `{ uav_udp_port, ground_station_port, ground_station_protocol, enabled }`；协议限定为 `'tcp' | 'udp'`。
- [x] **Step 4: 实现 auth 与 channel API 函数**
  - 路径对应后端 `POST /auth/login`、`POST /auth/logout`、`GET /auth/me` 及 `/channels` 路由；PCAP 下载返回 Blob。
- [x] **Step 5: 实现健康状态 API 函数**
  - `getHealth(): Promise<HealthPublic>` 调用 `GET /health`；响应类型为 `{ status: string; database: string }`。
- [x] **Step 6: 实现会话状态和失效处理**
  - 页面恢复时请求 `/auth/me`；登录成功更新状态；退出清理状态；任一受保护请求 401 时清理状态并触发路由回登录页。
- [x] **Step 7: 运行 HTTP 与会话验证**
  - Run: `npm test -- --run src/__tests__/http.spec.ts src/__tests__/session.spec.ts src/__tests__/channels-api.spec.ts`
  - Expected: 凭据、错误、登录恢复、退出、401 过期、路由和请求 payload 场景通过。

### Task 3：实现路由守卫、登录页和管理布局

**Files:**
- Create: `src/router/index.ts`, `src/composables/useHealthStatus.ts`, `src/components/AdminLayout.vue`, `src/components/StatusBadge.vue`, `src/components/RoutePlaceholder.vue`, `src/pages/LoginPage.vue`, `src/pages/NotFoundPage.vue`, `src/pages/OverviewPage.vue`, `src/pages/ChannelsPage.vue`, `src/pages/ChannelDetailPage.vue`, `src/pages/FlightMessagesPage.vue`, `src/pages/CapturesPage.vue`
- Modify: `src/main.ts`, `src/App.vue`
- Create: `src/__tests__/router.spec.ts`, `src/__tests__/health-status.spec.ts`

**Interfaces:**
- Consumes: Task 2 的 `useAuthSession()`。
- Produces: `/login`、`/`、`/channels`、`/channels/:id`、`/messages`、`/captures` 路由；受保护页面使用同一管理布局。

- [x] **Step 1: 编写未登录/已登录路由守卫验证**
  - 验证未登录访问受保护页面转到 `/login`，已登录访问 `/login` 转到 `/`，受保护轮询遇到 401 后转到 `/login`，登录后的 return path 受限于本应用内部路由。
- [x] **Step 2: 实现登录页**
  - 用户名、密码提交到后端；提供提交中、凭据错误和 API 不可用状态；不提供注册或找回管理员密码入口。
- [x] **Step 3: 实现管理布局和路由**
  - 左侧导航显示总览、端口组、飞控消息、抓包文件；顶部展示由 `GET /health` 每 15 秒轮询得到的 API/数据库状态与当前管理员；窄屏侧栏折叠。为总览、端口组、详情、消息、抓包五个后续实现的页面建立轻量占位视图，确保路由导入和当前阶段构建通过。
- [x] **Step 4: 验证路由和登录视图**
  - Run: `npm test -- --run src/__tests__/router.spec.ts src/__tests__/health-status.spec.ts`
  - Expected: 守卫、路径恢复、登录错误、健康在线/异常/恢复状态通过。

**阶段交付：** 登录与会话路由、同一套控制台框架。交付后暂停并向用户汇报，获批后进入阶段 3。

### 阶段 3：总览与端口组监控

### Task 4：实现轮询 composable、总览页和端口组列表

**Files:**
- Create: `src/composables/usePolling.ts`, `src/components/SummaryCard.vue`, `src/components/ChannelCard.vue`
- Modify: `src/pages/OverviewPage.vue`, `src/pages/ChannelsPage.vue`
- Create: `src/__tests__/polling.spec.ts`, `src/__tests__/overview.spec.ts`

**Interfaces:**
- Consumes: `GET /api/v1/channels` 返回 `ChannelPublic[]`；Task 2 的 `apiRequest`。
- Produces: `usePolling<T>(loader: () => Promise<T>, intervalMs: number, enabled?: MaybeRefOrGetter<boolean>)` 暴露 `data: Ref<T | undefined>`、`error: Ref<unknown>`、`loading: Ref<boolean>`、`refresh(): Promise<void>`；文档规定的可见性暂停与请求去重。

- [x] **Step 1: 编写 `polling pauses while hidden and prevents overlap` 验证**
  - 验证隐藏时不发新请求；显示时触发一次刷新；上次请求未完成时不会再并行启动相同 loader。
- [x] **Step 2: 实现 `usePolling`**
  - 使用 `document.visibilityState`；组件卸载时清理计时器；出错时保留最近成功数据并标记数据可能过期。
- [x] **Step 3: 实现总览指标和临时活动记录**
  - 汇总端口组总数、`telemetry.uav_online` 数量、`telemetry.ground_station_connected` 数量；不显示跨组 MAVLink 质量。活动记录只由页面打开期间观察到的状态转变生成，初始加载不伪造历史记录。
- [x] **Step 4: 实现端口组状态卡片和列表**
  - 显示通道端口、协议、飞控/地面站状态、SYSID、单组链路质量和可用关键遥测；最多 5 组；缺失数据显示“—”。
- [x] **Step 5: 验证汇总和状态展示**
  - Run: `npm test -- --run src/__tests__/polling.spec.ts src/__tests__/overview.spec.ts`
  - Expected: 3 秒轮询、隐藏页行为、空列表及单组质量显示通过。

**阶段交付：** 总览和端口组列表以真实后端数据更新。交付后暂停并向用户汇报，获批后进入阶段 4。

### 阶段 4：单组详情与管理操作

### Task 5：实现详情页、端口组表单和运行状态展示

**Files:**
- Modify: `src/pages/ChannelDetailPage.vue`
- Create: `src/components/ChannelFormDialog.vue`, `src/components/LinkQuality.vue`, `src/components/TerminalPanel.vue`, `src/components/ChannelRuntime.vue`
- Create: `src/__tests__/channel-detail.spec.ts`, `src/__tests__/channel-operations.spec.ts`

**Interfaces:**
- Consumes: Task 2 的 `ChannelPublic` 类型和 channel API；Task 4 的 `usePolling`。
- Produces: 每次只绑定一个 `{id}`；写操作通过对应 channel API 并刷新该通道数据。
- Produces: `TerminalPanel` props `{ title: string; lines: readonly string[]; loading?: boolean; error?: string | null; autoScroll?: boolean }`，并通过 `update:autoScroll` 事件通知自动滚动开关变化。

- [x] **Step 1: 编写单组状态组合和写操作错误验证**
  - `channel summary preserves independent status states` 验证 telemetry `unavailable`、从未收到数据与最近断连、通道 disabled、router `failed`、capture `failed`、security group `error` 各自显示。`channel mutation surfaces conflict and provider failures` 验证 HTTP 409/503 显示对应中文提示且不清空表单输入；不向界面透出后端内部错误详情。
- [x] **Step 2: 实现端口组详情遥测区**
  - 每 2 秒读取单组详情；展示飞行模式、armed、电池、GPS 卫星数、海拔、相对高度、地速、飞控 peer/最近包、收发速率和地面站连接；从未收到数据与最近断连分别显示；缺值显示“—”。
- [x] **Step 3: 实现小型阶梯链路质量指示器**
  - 从左至右阶梯条加百分比；单组 `link_quality_percent` 为 null 时显示未知，不映射成 0% 或蜂窝信号。
- [x] **Step 4: 实现端口、运行时和终端面板**
  - TCP/UDP 端口与 peer 分开呈现；router 和 capture 状态分别显示；通过 `getChannelLogs` 读取 mavlink-router systemd 日志，通过 `getFlightMessages` 读取 STATUSTEXT，通过 `getPacketSummaries` 读取报文摘要；均用深色等宽终端面板展示。detail 上日志/消息每 2 秒、报文摘要每 2 秒刷新。
- [x] **Step 5: 实现新增、修改、删除和重启**
  - DTU 入口固定为 UDP；地面站协议默认 TCP，可选 UDP。达到 5 组时禁用新增；删除对话框展示端口对；重启/删除显示进行中状态；成功后刷新列表和详情。通道变更返回 2xx 时仍单独呈现 `security_group.state`、`runtime.state`、`capture_runtime.state`。
- [x] **Step 6: 运行详情与操作验证**
  - Run: `npm test -- --run src/__tests__/channel-detail.spec.ts src/__tests__/channel-operations.spec.ts`
  - Expected: 未知/失败状态区分、缺失遥测、端口冲突和安全组失败行为通过。

- 阶段 4 UI 语言要求：页面、导航、无障碍标签、状态、错误和空状态统一使用中文；FlightLink-Console、MAVLink、Router、TCP、UDP、QGC、SYSID、PCAP 等专名和协议缩写保留。
- 本地预览 API 补充单组详情、日志、STATUSTEXT、报文摘要和内存态端口组增删改/重启模拟；仅开发预览中生效，不访问 FastAPI 或阿里云。
- 端口占用按 `(传输协议, 端口号)` 判断，因此 TCP 与 UDP 可共用数字；两个 UDP 监听端点不能共用数字。预览冲突行为与后端一致。
- 详情页以端口组 ID 作为轮询键；切换端口组时清空旧数据并丢弃旧请求响应。保存、重启、删除也会固定使用操作开始时的端口组 ID；切换页面后，旧操作不能更新新组数据、提示或导航。
- 新增接口即使成功返回，也根据 `security_group.state` 展示已同步、待同步或失败；端口组卡片同时显示 Router、抓包和安全组状态。终端按内容变化滚动，即使每次仍为 100 行也能跟随最新行。
- 安全组服务错误兼容后端的 `security-group` 连字符文本；本地预览可在删空示例组后重新创建。

**阶段交付：** 单端口组详情、配置增删改、重启和各服务状态显示。交付后暂停并向用户汇报，获批后进入阶段 5。

### 阶段 5：飞控消息与抓包文件

### Task 6：实现消息、实时报文和 PCAP 页面

**Files:**
- Modify: `src/pages/FlightMessagesPage.vue`, `src/pages/CapturesPage.vue`
- Create: `src/components/CaptureFileList.vue`
- Create: `src/__tests__/messages.spec.ts`, `src/__tests__/captures.spec.ts`
- Modify: `src/api/error-message.ts`, `dev/preview-api.ts`; extend channel API, error-mapping, and preview API tests.

**Interfaces:**
- Consumes: `GET /channels/{id}/messages?limit=100` 返回 `FlightMessagePublic[]`；`GET /channels/{id}/packets?limit=100` 返回 `PacketSummaryPublic[]`；`GET /channels/{id}/captures` 返回 `CaptureFilePublic[]`。
- Consumes: Task 2 的 `apiDownload('/channels/{id}/captures/{file_name}')`；API client 统一加 `/api/v1` 前缀。
- Consumes: Task 5 的 `TerminalPanel` props，用于飞控消息和实时抓包摘要的终端式展示。

- [x] **Step 1: 编写级别过滤、当前片段与 Cookie 下载验证**
  - `capture download excludes current segment and downloads closed file` 验证当前抓包片段不可下载；已关闭 PCAP 下载请求携带 Cookie 并作为文件保存。飞控消息级别过滤在前端执行。
- [x] **Step 2: 实现飞控消息页**
  - 端口组选择、消息级别过滤、手动刷新、自动滚动开关；每 2 秒轮询最近消息，使用 `severity_name` 和 `text` 呈现。
- [x] **Step 3: 实现抓包文件页**
  - 端口组选择；可见期间每 1 秒轮询报文摘要；PCAP 列表手动或每 15 秒轮询；展示开始时间、文件名、大小、写入中状态；仅对关闭文件启用下载。
- [x] **Step 4: 处理下载错误**
  - 409 提示片段仍在写入；404 提示文件已不可用；401 按统一会话流程回登录页；文件名 URL 编码。
- [x] **Step 5: 运行消息和抓包验证**
  - Run: `npm test -- --run src/__tests__/messages.spec.ts src/__tests__/captures.spec.ts`
  - Expected: 级别筛选、轮询节奏、当前片段禁用、Cookie 下载和 404/409 错误展示通过。

- 飞控消息级别由英文 `severity_name` 匹配、在界面显示中文级别；`STATUSTEXT` 原文保持不变。
- 本地预览提供两个抓包条目、仅开发环境可用的 PCAP 下载和当前片段 409 模拟；示例 PCAP 是有效但不含报文记录的 24 字节文件，列表大小与下载内容一致，不访问真实后端或阿里云。
- PCAP 下载使用现有带 Cookie 的二进制 API，并对端口组 ID 和文件名做 URL 编码；当前写入片段禁用下载，后端竞态返回的 409 与文件清理后的 404 分别显示中文提示。

**阶段交付：** 飞控消息、近实时包摘要和 PCAP 文件浏览/下载。交付后暂停并向用户汇报，获批后进入阶段 6。

### 阶段 6：部署配置、双语说明与整体验收

### Task 7：补齐 Nginx 示例、双语文档并进行整合验收

**Files:**
- Create: `deploy/nginx/flightlink-console.conf.example`, `docs/deployment.md`, `README.md`
- Modify: `package.json`（若最终脚手架命令需要调整）

**Interfaces:**
- Nginx 使用 `dist/` 静态目录；`/api/` 代理 `http://127.0.0.1:8000` 并保留 `/api/` 前缀。
- 部署文档包含证书/域名占位配置、管理员 IPv4 `/32` 占位、TCP `18443` 入方向规则、FastAPI loopback 与 Secure Cookie 配置。

- [x] **Step 1: 编写 Nginx SPA 静态和 API 代理配置样例**
  - HTTPS 监听 TCP `18443`；`try_files` 回落到 `index.html`；`/api/` 反向代理到 loopback；配置替换证书、域名和管理员 `/32` 的注释说明；不暴露 `8000`/`8080`。
- [x] **Step 2: 编写中英双语 README 和部署指南**
  - 说明 Node 本地开发/构建、`dist/` 发布、Nginx 安装、FastAPI 同源代理、Cookie Secure 和阿里云安全组需手工允许的端口。
- [x] **Step 3: 运行全量前端验证**
  - Run: `npm test -- --run`
  - Expected: 全部 Vitest 验证通过。
  - Run: `npm run lint`
  - Expected: ESLint 无错误。
  - Run: `npm run build`
  - Expected: 生产构建成功并生成 `dist/`。
- [x] **Step 4: 按设计样图人工检查主要视图**
  - 检查总览不含全局链路质量卡、详情阶梯质量与 GPS 卫星数、终端显示、窄屏布局、抓包当前片段不可下载、登录/401 回跳。

**阶段交付：** 可由 Nginx 提供的前端构建产物、部署示例与中英双语文档。真实 ECS/RAM/DTU/QGC 连通验收仍按设计文档安排在前端交付后单独进行。

## Git 与执行备注

- 仓库已存在；实现使用本地功能分支，按任务提交到该分支，不推送、不合并。
- 设计和计划已获用户确认；实施依照阶段边界暂停汇报，等待确认后再进入下一阶段。
