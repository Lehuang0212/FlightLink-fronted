# FlightLink-Console 前端部署 / Frontend Deployment

## 中文

本指南部署 Vue 前端到 Ubuntu 或 Rocky Linux ECS：Nginx 在 TCP `18443` 提供 HTTPS 静态页面，并把同源 `/api/` 请求转发给本机 FastAPI。Node.js 只用于开发和构建，不作为生产常驻服务。后端、`mavlink-router`、抓包服务和 RAM 角色按 [FlightLink-backend 仓库说明](https://github.com/Lehuang0212/FlightLink-backend) 配置。

### 1. 准备后端

先按后端仓库说明安装并启动 `flightlink-api.service`。确认 Uvicorn 只监听 `127.0.0.1:8000`，且 `/etc/flightlink/api.env` 中设置：

```ini
FLIGHTLINK_SESSION_COOKIE_SECURE=true
```

更改环境文件后重启 API。可在 ECS 上确认本机健康接口可用：

```bash
curl -i http://127.0.0.1:8000/api/v1/health
```

不要为 FastAPI 的 `8000` 端口创建公网安全组规则。

### 2. 构建前端

在开发机安装 Node.js `22.12.0` 或更高版本，然后在前端仓库根目录运行：

```bash
npm ci
npm run test -- --run
npm run lint
npm run build
```

成功后，待发布的静态文件位于 `dist/`。将 `dist/` 的内容复制到 ECS 的 `/var/www/flightlink-console/`。不要把 `.env.local`、管理员密码或其他运行时密钥复制到服务器静态目录。生产构建不启用仅供开发演示的本地预览 API。

### 3. 安装 Nginx 并部署静态文件

在 ECS 安装 Nginx：

```bash
# Ubuntu
sudo apt install nginx

# Rocky Linux
sudo dnf install nginx
```

创建静态目录并复制已经构建好的 `dist/` 内容。以下命令假设你已把前端仓库放在当前目录：

```bash
sudo install -d -o root -g root -m 0755 /var/www/flightlink-console
sudo cp -a dist/. /var/www/flightlink-console/
```

为管理域名准备有效的 TLS 证书和私钥。复制 [Nginx 示例](../deploy/nginx/flightlink-console.conf.example) 到 `/etc/nginx/conf.d/flightlink-console.conf`，并按下一节修改域名、证书路径和管理员来源地址。

### 4. 修改 Nginx 示例

编辑 `/etc/nginx/conf.d/flightlink-console.conf`：

- 将 `console.example.com` 改为证书对应的管理域名。
- 将 `ssl_certificate` 和 `ssl_certificate_key` 改为 ECS 上真实证书和私钥路径。
- 将示例地址 `203.0.113.10/32` 改为管理员当前公网 IPv4 的 `/32`。该地址是文档保留地址，必须替换；`deny all` 会拒绝其他来源。
- 若静态文件放在其他目录，同步修改 `root`。

示例中的 `proxy_pass http://127.0.0.1:8000;` 故意没有在端口后添加路径，这样 `/api/v1/...` 会原样到达 FastAPI。前端和 API 使用同一个 HTTPS 来源，登录 Cookie 由后端设置为 Secure、HttpOnly。

#### Rocky Linux 的 SELinux

仅当 Rocky Linux 上 `getenforce` 返回 `Enforcing` 时，才需要为自定义 TCP `18443` 端口添加 Web 服务端口标签，并允许 Nginx 连接反向代理上游：

```bash
sudo dnf install policycoreutils-python-utils
sudo semanage port -l | grep 18443
# 仅当上面没有 18443 标签时，添加下方端口规则。
sudo semanage port -a -t http_port_t -p tcp 18443
sudo setsebool -P httpd_can_network_connect 1
```

如果 `18443` 已有 SELinux 端口标签，若已是 `http_port_t` 就跳过添加命令；若是其他类型，不要直接覆盖，先核对该端口的用途。`httpd_can_network_connect` 会赋予 Nginx 较宽的出站网络连接权限，并不会把连接范围限制到 `127.0.0.1:8000`；FlightLink 的反代实际只访问本机 FastAPI。需要更窄限制时，应另行编写并审查专用 SELinux 策略。这些命令调整 SELinux 策略，不配置主机防火墙或阿里云安全组。详细依据见 [Red Hat 的 NGINX 反向代理 SELinux 指引](https://docs.redhat.com/en/documentation/red_hat_enterprise_linux/9/html/deploying_web_servers_and_reverse_proxies/configuring-nginx-as-a-reverse-proxy-for-the-http-traffic) 与[非标准 Web 端口标签说明](https://docs.redhat.com/en/documentation/red_hat_enterprise_linux/9/html/using_selinux/troubleshooting-problems-related-to-selinux_using-selinux)。

配置语法通过后启用 Nginx：

```bash
sudo nginx -t
sudo systemctl enable --now nginx
sudo systemctl reload nginx
```

### 5. 配置阿里云安全组并检查

在 ECS 关联的阿里云安全组中添加管理入口入方向规则：TCP `18443`，来源为管理员公网 IPv4 `/32`。同一条 Nginx 配置也限制来源地址。若管理员公网地址变化，需要同时更新安全组规则和 Nginx 的 `allow` 地址，然后检查并重新加载 Nginx。

不要开放公网 TCP `8000` 或 `8080`。无人机 DTU 的 UDP 端口和 QGC 端口由后端按端口组和 RAM 角色同步到阿里云安全组；首次真实连接验收按后端部署说明进行。

从允许的管理员网络检查：

```bash
curl -I https://console.example.com:18443/
curl -i https://console.example.com:18443/api/v1/health
```

之后用浏览器打开 `https://console.example.com:18443/` 并使用通过后端 `ConsoleUseradd` 创建的管理员登录。前端没有注册入口。`npm run dev` 和本地预览模式只用于开发，不要作为生产 Web 服务运行。

## English

This guide deploys the Vue frontend to an Ubuntu or Rocky Linux ECS. Nginx serves the HTTPS application on TCP `18443` and proxies same-origin `/api/` requests to the local FastAPI service. Node.js is used for development and builds; it is not a production service. Configure the backend, `mavlink-router`, capture services, and RAM role using the [FlightLink-backend repository guide](https://github.com/Lehuang0212/FlightLink-backend).

### 1. Prepare the backend

Install and start `flightlink-api.service` using the backend repository guide. Confirm that Uvicorn listens only on `127.0.0.1:8000`, and set this value in `/etc/flightlink/api.env`:

```ini
FLIGHTLINK_SESSION_COOKIE_SECURE=true
```

Restart the API after changing its environment file. Check the local health endpoint on the ECS:

```bash
curl -i http://127.0.0.1:8000/api/v1/health
```

Do not create a public security-group rule for FastAPI port `8000`.

### 2. Build the frontend

Install Node.js `22.12.0` or later on the development machine, then run these commands from the frontend repository root:

```bash
npm ci
npm run test -- --run
npm run lint
npm run build
```

The production static files are written to `dist/`. Copy the contents of `dist/` to `/var/www/flightlink-console/` on the ECS. Do not copy `.env.local`, administrator passwords, or other runtime secrets into the static web root. The production build does not enable the local preview API, which is for development demonstrations only.

### 3. Install Nginx and publish the static files

Install Nginx on the ECS:

```bash
# Ubuntu
sudo apt install nginx

# Rocky Linux
sudo dnf install nginx
```

Create the web root and copy the already-built `dist/` contents. These commands assume the frontend repository is available in the current directory:

```bash
sudo install -d -o root -g root -m 0755 /var/www/flightlink-console
sudo cp -a dist/. /var/www/flightlink-console/
```

Obtain a valid TLS certificate and private key for the management domain. Copy the [Nginx example](../deploy/nginx/flightlink-console.conf.example) to `/etc/nginx/conf.d/flightlink-console.conf`, then update the domain, certificate paths, and administrator source address as described below.

### 4. Edit the Nginx example

Edit `/etc/nginx/conf.d/flightlink-console.conf`:

- Replace `console.example.com` with the domain covered by the certificate.
- Set `ssl_certificate` and `ssl_certificate_key` to the real certificate and private-key paths on the ECS.
- Replace `203.0.113.10/32` with the administrator's current public IPv4 address in `/32` form. This is a documentation-only address and must be changed; `deny all` rejects other sources.
- If the static files use a different directory, update `root` as well.

The example intentionally uses `proxy_pass http://127.0.0.1:8000;` without a URI after the port, so paths such as `/api/v1/...` reach FastAPI unchanged. The UI and API share one HTTPS origin; the backend sets the login cookie as Secure and HttpOnly.

#### SELinux on Rocky Linux

Only when `getenforce` reports `Enforcing` on Rocky Linux, add the web-server port label for custom TCP port `18443` and allow Nginx to connect to its reverse-proxy upstream:

```bash
sudo dnf install policycoreutils-python-utils
sudo semanage port -l | grep 18443
# Add the port rule below only if the command above shows no label for 18443.
sudo semanage port -a -t http_port_t -p tcp 18443
sudo setsebool -P httpd_can_network_connect 1
```

If port `18443` already has an SELinux port label, skip the add command when it is already `http_port_t`. If it has another type, do not replace it until you have checked what uses that port. `httpd_can_network_connect` grants Nginx broader outbound network-connect permission; it does not limit destinations to `127.0.0.1:8000`, although FlightLink's reverse proxy only needs the local FastAPI service. For a narrower restriction, write and review a dedicated SELinux policy. These commands change SELinux policy only; they do not configure the host firewall or Alibaba Cloud security group. See Red Hat's [NGINX reverse-proxy SELinux guidance](https://docs.redhat.com/en/documentation/red_hat_enterprise_linux/9/html/deploying_web_servers_and_reverse_proxies/configuring-nginx-as-a-reverse-proxy-for-the-http-traffic) and [non-standard web-port labeling instructions](https://docs.redhat.com/en/documentation/red_hat_enterprise_linux/9/html/using_selinux/troubleshooting-problems-related-to-selinux_using-selinux).

After the configuration syntax check succeeds, enable Nginx:

```bash
sudo nginx -t
sudo systemctl enable --now nginx
sudo systemctl reload nginx
```

### 5. Configure the Alibaba Cloud security group and verify

Add an inbound management rule to the Alibaba Cloud security group attached to the ECS: TCP `18443`, with the administrator's public IPv4 `/32` as the source. The Nginx configuration also restricts the source address. If the administrator's public address changes, update both the security-group rule and Nginx `allow` address, then validate and reload Nginx.

Do not expose public TCP `8000` or `8080`. The backend synchronizes UAV DTU UDP ports and QGC ports to the Alibaba Cloud security group per channel using the ECS RAM role. Follow the backend deployment guide for the first real connection acceptance.

From an allowed administrator network, check the site and API:

```bash
curl -I https://console.example.com:18443/
curl -i https://console.example.com:18443/api/v1/health
```

Then open `https://console.example.com:18443/` in a browser and sign in with an administrator created through the backend's `ConsoleUseradd` command. The frontend has no registration flow. Use `npm run dev` and local preview mode for development only, not as the production web server.
