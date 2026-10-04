# FlightLink-Console 前端

[中文](README.md) | [English](../README-us/README.md) | [仓库首页](../README.md)

## 项目介绍

FlightLink-Console 前端是无人机 4G MAVLink 链路管理控制台，用于查看端口组、飞控与 QGC 连接状态、遥测、MAVLink 链路质量、飞控消息、Router 日志和抓包文件，并管理端口组和 Router 服务。

本仓库只提供网页界面；飞控通信、服务控制和阿里云 API 由[后端仓库](https://github.com/Lehuang0212/FlightLink-backend)实现。界面使用中文，文档提供中英两版。

## 项目结构

```text
src/
├── api/                 后端 API 与类型
├── auth/                登录和会话
├── components/          遥测卡片、信号阶梯、终端与表单
├── composables/         轮询与稳定数据更新
├── pages/               总览、端口组、飞控消息、抓包页面
├── router/              页面路由
├── styles/              样式
├── format.ts            两位小数格式化
└── main.ts              应用入口
dev/                     本地模拟 API
deploy/nginx/            HTTPS 配置示例
docs/                    设计、实施与部署入口
.env.example             开发环境示例
package.json             依赖与命令
package-lock.json        依赖锁定
vite.config.ts           构建与开发代理
```

## 实现说明

- Vue 3、TypeScript、Vite、Vue Router、Element Plus；构建产物为 `dist/`。
- Nginx 提供静态文件，将同源 `/api/` 代理到 FastAPI；Node.js 仅用于开发和构建。
- 遥测、飞控消息、实时摘要每 1 秒更新；Router 日志每 2 秒、抓包文件每 15 秒更新。隐藏页面暂停轮询，相同数据保持显示稳定。
- Router 终端保留原始大括号和缩进；链路质量、海拔、地速等小数指标保留两位小数。
- 登录使用后端管理员账号；本地演示账号不用于生产。无注册入口。

## 使用教程

### 1. 安装环境

与后端共用一台 ECS，先部署[后端](https://github.com/Lehuang0212/FlightLink-backend/blob/main/README-cn/README.md)。Node.js 要求 `>=22.12.0`；已有合适版本时跳过 NodeSource 安装。

**Ubuntu 24.04：**

```bash
sudo apt-get update
sudo apt-get install -y git curl ca-certificates nginx
curl -fsSL https://deb.nodesource.com/setup_22.x -o /tmp/flightlink-node-setup.sh
sudo bash /tmp/flightlink-node-setup.sh
sudo apt-get install -y nodejs
```

**Rocky Linux 9：**

```bash
sudo dnf install -y git curl ca-certificates nginx
curl -fsSL https://rpm.nodesource.com/setup_22.x -o /tmp/flightlink-node-setup.sh
sudo bash /tmp/flightlink-node-setup.sh
sudo dnf install -y nodejs
```

```bash
node --version
npm --version
```

安装方法参考 [NodeSource](https://github.com/nodesource/distributions/blob/master/DEV_README.md)。

### 2. 下载、构建

仓库名实际为 `FlightLink-fronted`。以下命令在 ECS 登录用户下执行：

```bash
sudo install -d -o root -g root -m 0755 /opt/flightlink
sudo git clone https://github.com/Lehuang0212/FlightLink-fronted.git /opt/flightlink/frontend
sudo chown -R "$(id -un):$(id -gn)" /opt/flightlink/frontend
cd /opt/flightlink/frontend
npm ci
npm run build
sudo install -d -o root -g root -m 0755 /var/www/flightlink-console
sudo cp -a dist/. /var/www/flightlink-console/
```

已有仓库直接执行第 7 节更新命令。只发布 `dist/`，不发布 `.env.local`。

### 3. 新建 Nginx 配置

在 `/etc/nginx/conf.d/` 新建 `flight-frontend.conf`。若旧 FlightLink 配置已监听 `18443`，先将旧文件移出 `*.conf`，同一入口只保留一份配置。

以下为 **HTTP 实测配置**；公网 HTTP 不加密登录信息，正式使用切换第 6 节 HTTPS：

```bash
sudo tee /etc/nginx/conf.d/flight-frontend.conf >/dev/null <<'EOF'
server {
    listen 18443;
    server_name _;
    root /var/www/flightlink-console;
    index index.html;
    server_tokens off;

    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_connect_timeout 5s;
        proxy_read_timeout 60s;
    }

    location = /index.html {
        add_header Cache-Control "no-cache";
    }

    location / {
        try_files $uri $uri/ /index.html;
    }
}
EOF
```

后端 HTTP 登录配置：

```bash
sudo vi /etc/flightlink/api.env
```

```ini
FLIGHTLINK_SESSION_COOKIE_SECURE=false
```

```bash
sudo systemctl restart flightlink-api.service
```

### 4. Rocky SELinux

仅 Rocky 的 `getenforce` 返回 `Enforcing` 时执行：

```bash
getenforce
sudo dnf install -y policycoreutils-python-utils
sudo semanage port -l | grep 18443
```

仅当没有 `18443` 标签时添加；已有 `http_port_t` 则跳过，其他标签先核对用途：

```bash
sudo semanage port -a -t http_port_t -p tcp 18443
sudo setsebool -P httpd_can_network_connect 1
sudo restorecon -Rv /var/www/flightlink-console
```

`httpd_can_network_connect` 允许 Nginx 出站连接，实际代理目标为本机 `8000`；它不是只允许该端口的策略。[Red Hat 指引](https://docs.redhat.com/en/documentation/red_hat_enterprise_linux/9/html/deploying_web_servers_and_reverse_proxies/configuring-nginx-as-a-reverse-proxy-for-the-http-traffic)

### 5. 启动与访问

阿里云安全组手动添加 TCP `18443` 入方向规则，来源为管理员公网 IPv4 `/32`。本教程按主机防火墙已关闭部署；不开放公网 `8000`。

```bash
sudo nginx -t
sudo systemctl enable --now nginx
sudo systemctl reload nginx
curl -fsS http://127.0.0.1:18443/api/v1/health
```

本地电脑打开 `http://ECS公网IP:18443/`，使用后端 `ConsoleUseradd` 创建的管理员登录。此配置不需要 SSH 隧道。

### 6. 切换 HTTPS

先准备域名及匹配的有效证书。编辑同一个文件：

```bash
sudo vi /etc/nginx/conf.d/flight-frontend.conf
```

将 `listen`、`server_name` 替换，并添加证书路径，其他配置保留：

```nginx
listen 18443 ssl;
server_name console.example.com;
ssl_certificate /etc/letsencrypt/live/console.example.com/fullchain.pem;
ssl_certificate_key /etc/letsencrypt/live/console.example.com/privkey.pem;
```

将域名、证书路径替换为实际值，后端配置改为：

```ini
FLIGHTLINK_SESSION_COOKIE_SECURE=true
```

```bash
sudo systemctl restart flightlink-api.service
sudo nginx -t
sudo systemctl reload nginx
```

访问 `https://你的域名:18443/`。完整示例见 [Nginx 示例](../deploy/nginx/flightlink-console.conf.example)；复制使用时一并替换示例中的管理员 `allow` 地址。

### 7. 更新前端

```bash
cd /opt/flightlink/frontend
git pull --ff-only origin main
npm ci
npm run build
sudo cp -a dist/. /var/www/flightlink-console/
```

Rocky 启用 SELinux 时：

```bash
sudo restorecon -Rv /var/www/flightlink-console
```

每一步成功再继续。静态文件更新不用重启后端或 Nginx；浏览器按 `Ctrl + F5`。

### 8. 本地开发

```bash
npm ci
npm run dev
```

开发代理默认指向 `http://127.0.0.1:8000`。模拟预览配置见 [.env.example](../.env.example)，仅开发使用。

## 阿里云安全组配置

以下角色和策略供运行后端的 ECS 使用；静态前端不保存阿里云凭证。

### 1. 创建实例 RAM 角色

RAM 控制台 → 身份管理 → 角色 → 创建角色：

| 配置 | 示例 |
| --- | --- |
| 可信实体 | 阿里云服务 / 云服务 |
| 可信服务 | 云服务器 ECS |
| 角色类型 | 普通服务角色（页面提供此选项时） |
| 角色名称 | `FlightLinkEcsRole` |

角色的信任策略应包含：

```json
{
  "Version": "1",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Service": ["ecs.aliyuncs.com"]
      },
      "Action": "sts:AssumeRole"
    }
  ]
}
```

`Principal.Service` 指定可信服务 ECS；`sts:AssumeRole` 允许该服务扮演角色。**信任策略不授予安全组操作权限**，操作权限由下一步策略提供。[官方角色教程](https://www.alibabacloud.com/help/en/ram/user-guide/create-a-ram-role-for-a-trusted-alibaba-cloud-service)

### 2. 创建自定义权限策略

RAM 控制台 → 权限管理 → 权限策略 → 创建权限策略 → 脚本编辑。名称示例：`FlightLinkSecurityGroupPolicy`。

```json
{
  "Version": "1",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "ecs:DescribeSecurityGroupAttribute",
        "ecs:AuthorizeSecurityGroup",
        "ecs:RevokeSecurityGroup"
      ],
      "Resource": "*"
    }
  ]
}
```

策略解释：

| 字段 / 操作 | 含义 |
| --- | --- |
| `Version: "1"` | RAM 策略语法版本 |
| `Statement` | 权限规则列表 |
| `Effect: "Allow"` | 允许所列操作 |
| `DescribeSecurityGroupAttribute` | 读取目标安全组规则，支持预检和同步 |
| `AuthorizeSecurityGroup` | 添加 DTU / QGC 入方向规则 |
| `RevokeSecurityGroup` | 撤销后端记录并托管的规则 |
| `Resource: "*"` | 这些操作适用于账号下所有匹配资源，不是仅限某一个安全组 |

此示例便于部署；后端仅操作环境文件配置的安全组，但该配置**不是 RAM 权限边界**。需要更窄权限时按官方授权表限制支持资源级授权的操作。当前代码不需要 `ecs:ModifySecurityGroupRule` 或 `ecs:DescribeSecurityGroups`。[自定义策略教程](https://www.alibabacloud.com/help/zh/ram/create-a-custom-policy)，[ECS 授权表](https://www.alibabacloud.com/help/en/ram/api-elastic-compute-service)。

### 3. 授权并绑定 ECS

1. RAM 角色 `FlightLinkEcsRole` → 新增授权 → 附加 `FlightLinkSecurityGroupPolicy`。
2. ECS 控制台 → 选择地域、实例 → 实例设置 → 授予或收回 RAM 角色 → 选择该角色。
3. 实例详情 → 安全组，记录实际安全组 ID；地域 ID 可在 ECS / OpenAPI 页面查看，例如 `cn-hangzhou`。
4. 将这些值填写到安装提示或 `/etc/flightlink/api.env`，重启 API。SDK 自动获取临时凭证，不填写长期 AccessKey。

如果 ECS 已绑定其他角色，将策略附加到现有角色，避免直接替换。[官方绑定教程](https://www.alibabacloud.com/help/zh/ecs/user-guide/attach-an-instance-ram-role-to-an-ecs-instance)

### 4. 设置网络入口

| 用途 | 入方向规则 | 来源 |
| --- | --- | --- |
| SSH | 当前 SSH TCP 端口 | 管理员公网 IPv4 /32 |
| 管理网页 | TCP `18443`，手动添加 | 管理员公网 IPv4 /32 |
| DTU | UDP `5760`，后端创建 | `0.0.0.0/0` |
| QGC | TCP `14552`，后端创建 | QGC 公网 IPv4 /32 |

来源使用公网地址；地址变化后更新对应配置或规则。后端不修改主机防火墙，也不管理安全组出方向规则。
