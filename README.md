# FlightLink-Console 前端

## 中文

FlightLink-Console 前端是一个 Vue 3、TypeScript 和 Vite 单页应用，用于查看和管理端口组、飞控消息与 PCAP 抓包文件。界面文案使用中文；MAVLink、QGC、TCP、UDP、PCAP 等技术名称保留原文。

### 本地开发

需要 Node.js `22.12.0` 或更高版本。安装依赖并启动开发服务器：

```bash
npm ci
npm run dev
```

开发服务器默认将 `/api/` 转发至 `http://127.0.0.1:8000`。如需在没有后端时查看演示界面，可在未纳入 Git 的 `.env.local` 中开启仅开发使用的本地预览模式，并设置本机演示账号。预览模式使用模拟数据，不会调用 FastAPI 或阿里云；演示账号不得用于生产环境。

### 数据刷新与 Router 终端

总览、端口组状态、飞控消息和实时报文摘要每 1 秒更新；Router 日志每 2 秒读取最近 500 条 journal 记录，抓包文件和端口选择列表每 15 秒更新。自动更新不切换加载提示或刷新按钮，相同的数据分支保留原对象；页面隐藏时暂停轮询，慢请求不会积压自动补刷。

Router 终端保留原始 `Endpoint { Received messages { ... } Transmitted messages { ... } }` 文本和缩进，显示每个端点在最近日志窗口中的最新完整区块，不转换为 JSON，不自行计算或补造 Router 计数。截断区块不覆盖完整区块；数字变化不触发自动滚动，新的运行事件才按自动滚动开关处理。统计对应原生端点名称，例如 `uav_uplink`；只有 Router 实际输出的端点才显示，未启用的 BinLog/TLog 不会被模拟成真实端点。

需同时更新后端及其安装在 ECS 上的 `flightlink-routerctl`，才能获得无 journal 前缀的原始文本和当前服务运行批次的日志。开发预览中的统计已标为模拟数据。

MAVLink 链路质量百分比统一四舍五入显示整数（例如 `98.76% → 99%`），包括无障碍文字；信号阶梯和后端计算仍使用原始精度。

### 检查与构建

```bash
npm test -- --run
npm run lint
npm run build
```

生产静态文件输出到 `dist/`。Node.js 只用于开发与构建；生产环境由 ECS 上的 Nginx 提供静态文件，并在 TCP `18443` 上提供 HTTPS。Nginx 将同源 `/api/` 请求代理至仅监听 `127.0.0.1:8000` 的 FastAPI。不要将公网 TCP `8000` 或 `8080` 开放给管理界面。

生产登录账户由后端 `ConsoleUseradd` 命令创建；前端不提供注册功能。请按[部署指南](docs/deployment.md)配置 Nginx、TLS 证书、管理员 IPv4 `/32` 和阿里云安全组。后端部署及真实 DTU/QGC 连通验收见 [FlightLink-backend 仓库](https://github.com/Lehuang0212/FlightLink-backend)。

## English

The FlightLink-Console frontend is a Vue 3, TypeScript, and Vite single-page application for viewing and managing port groups, flight-controller messages, and PCAP capture files. The interface is in Chinese; technical names such as MAVLink, QGC, TCP, UDP, and PCAP remain unchanged.

### Local development

Node.js `22.12.0` or later is required. Install dependencies and start the development server:

```bash
npm ci
npm run dev
```

By default, the development server proxies `/api/` to `http://127.0.0.1:8000`. To view the interface without a backend, enable the development-only local preview mode in an untracked `.env.local` file and set a local demo account. Preview mode uses simulated data and does not call FastAPI or Alibaba Cloud. Do not use demo credentials in production.

### Refresh and Router terminal

Overview, channel telemetry, flight messages and live packet summaries refresh every second. Router logs poll the latest 500 journal entries every two seconds; capture files and channel selectors refresh every 15 seconds. Background polls keep loading prompts and refresh buttons stable, reuse unchanged data branches, pause when the page is hidden, and skip ticks while a request is pending.

The Router terminal preserves native endpoint blocks, braces and indentation, showing the latest complete block per endpoint within the recent log window. It does not convert statistics to JSON or calculate substitute Router counters. Truncated blocks do not replace complete blocks within that window. Counter changes do not cause automatic scrolling; new runtime events follow the auto-scroll setting. Names such as `uav_uplink` come from Router output; BinLog/TLog endpoints appear only when actually emitted. Local preview statistics are explicitly simulated.

Update both the backend and its installed ECS `flightlink-routerctl` helper to obtain unprefixed text from the current service invocation.

MAVLink link quality is rounded to an integer for visible and accessible percentage text (for example, `98.76% → 99%`). Signal-bar thresholds and backend calculations retain their original precision.

### Checks and build

```bash
npm test -- --run
npm run lint
npm run build
```

Production static files are written to `dist/`. Node.js is used for development and builds only. In production, Nginx on the ECS serves the static files over HTTPS on TCP `18443` and proxies same-origin `/api/` requests to FastAPI, which listens only on `127.0.0.1:8000`. Do not expose public TCP `8000` or `8080` for the management UI.

Production administrator accounts are created with the backend's `ConsoleUseradd` command; the frontend has no registration flow. Follow the [deployment guide](docs/deployment.md) to configure Nginx, TLS certificates, the administrator IPv4 `/32`, and the Alibaba Cloud security group. See the [FlightLink-backend repository](https://github.com/Lehuang0212/FlightLink-backend) for backend deployment and real DTU/QGC connectivity acceptance.
