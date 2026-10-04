# FlightLink-Console Frontend

[中文](../README-cn/README.md) | [English](README.md) | [Repository home](../README.md)

## Introduction

FlightLink-Console is a web console for UAV 4G MAVLink links. It displays channels, flight-controller and QGC connectivity, telemetry, MAVLink link quality, flight messages, Router logs, and capture files. Administrators can manage channels and Router services.

This repository provides the UI. Flight-controller communication, service control, and Alibaba Cloud API integration belong to the [backend](https://github.com/Lehuang0212/FlightLink-backend). The interface is in Chinese; documentation is available in Chinese and English.

## Project structure

```text
src/
├── api/                 Backend requests and types
├── auth/                Login and sessions
├── components/          Telemetry cards, signal bars, terminals, and forms
├── composables/         Polling and stable data updates
├── pages/               Overview, channels, flight messages, and captures
├── router/              Page routes
├── styles/              Styles
├── format.ts            Two-decimal formatting
└── main.ts              Application entry point
dev/                     Local mock API
deploy/nginx/            HTTPS configuration example
docs/                    Design, implementation, and deployment links
.env.example             Development environment template
package.json             Dependencies and commands
package-lock.json        Dependency lockfile
vite.config.ts           Build and development proxy
```

## Implementation

- Vue 3, TypeScript, Vite, Vue Router, and Element Plus; production output is `dist/`.
- Nginx serves static files and proxies same-origin `/api/` to FastAPI. Node.js is used only for development and builds.
- Telemetry, flight messages, and packet summaries poll every second; Router logs every two seconds and captures every 15 seconds. Hidden pages pause polling; unchanged data remains stable.
- Router terminals preserve native braces and indentation. Decimal metrics such as link quality, altitude, and ground speed display two decimal places.
- Login uses backend administrator accounts. Local demo credentials are not production accounts. There is no registration page.

## Usage

### 1. Install prerequisites

Use the same ECS as the backend and [deploy the backend](https://github.com/Lehuang0212/FlightLink-backend/blob/main/README-us/README.md) first. Node.js must be `>=22.12.0`; skip NodeSource installation if a compatible version is already installed.

**Ubuntu 24.04:**

```bash
sudo apt-get update
sudo apt-get install -y git curl ca-certificates nginx
curl -fsSL https://deb.nodesource.com/setup_22.x -o /tmp/flightlink-node-setup.sh
sudo bash /tmp/flightlink-node-setup.sh
sudo apt-get install -y nodejs
```

**Rocky Linux 9:**

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

Installation source: [NodeSource](https://github.com/nodesource/distributions/blob/master/DEV_README.md).

### 2. Clone and build

The GitHub repository name is `FlightLink-fronted`. Run these commands as your ECS login user:

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

For an existing checkout, use the update commands in section 7. Publish only `dist/`, not `.env.local`.

### 3. Create the Nginx configuration

Create `flight-frontend.conf` in `/etc/nginx/conf.d/`. If an older FlightLink configuration already listens on `18443`, move it outside the `*.conf` pattern first; keep one configuration for this entry point.

The following is for **HTTP testing**. Public HTTP does not encrypt login information; use section 6 for HTTPS:

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

Set the backend cookie option for HTTP:

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

Only when Rocky reports `Enforcing`:

```bash
getenforce
sudo dnf install -y policycoreutils-python-utils
sudo semanage port -l | grep 18443
```

Add the port label only if absent. Skip the add command if it is already `http_port_t`; check its use first if another label exists:

```bash
sudo semanage port -a -t http_port_t -p tcp 18443
sudo setsebool -P httpd_can_network_connect 1
sudo restorecon -Rv /var/www/flightlink-console
```

`httpd_can_network_connect` permits Nginx outbound connections, not only port `8000`. FlightLink's proxy uses the local backend. [Red Hat guidance](https://docs.redhat.com/en/documentation/red_hat_enterprise_linux/9/html/deploying_web_servers_and_reverse_proxies/configuring-nginx-as-a-reverse-proxy-for-the-http-traffic).

### 5. Start and access

Manually allow inbound TCP `18443` in the ECS security group, with your administrator public IPv4 `/32` as source. This guide assumes the host firewall is disabled. Do not expose public port `8000`.

```bash
sudo nginx -t
sudo systemctl enable --now nginx
sudo systemctl reload nginx
curl -fsS http://127.0.0.1:18443/api/v1/health
```

Open `http://ECS_PUBLIC_IP:18443/` on your computer. Sign in with an administrator created by backend `ConsoleUseradd`. This configuration needs no SSH tunnel.

### 6. Enable HTTPS

Prepare a domain and a matching valid certificate. Edit the same file:

```bash
sudo vi /etc/nginx/conf.d/flight-frontend.conf
```

Replace `listen` and `server_name` and add certificate paths; retain the remaining configuration:

```nginx
listen 18443 ssl;
server_name console.example.com;
ssl_certificate /etc/letsencrypt/live/console.example.com/fullchain.pem;
ssl_certificate_key /etc/letsencrypt/live/console.example.com/privkey.pem;
```

Replace the domain and certificate paths. Change the backend option:

```ini
FLIGHTLINK_SESSION_COOKIE_SECURE=true
```

```bash
sudo systemctl restart flightlink-api.service
sudo nginx -t
sudo systemctl reload nginx
```

Open `https://YOUR_DOMAIN:18443/`. See the [full Nginx example](../deploy/nginx/flightlink-console.conf.example); when using it, also replace its example administrator `allow` address.

### 7. Update

```bash
cd /opt/flightlink/frontend
git pull --ff-only origin main
npm ci
npm run build
sudo cp -a dist/. /var/www/flightlink-console/
```

On Rocky with SELinux enabled:

```bash
sudo restorecon -Rv /var/www/flightlink-console
```

Continue only after each command succeeds. Static updates require no API or Nginx restart. Reload the browser with `Ctrl + F5`.

### 8. Local development

```bash
npm ci
npm run dev
```

The development proxy defaults to `http://127.0.0.1:8000`. See [.env.example](../.env.example) for development-only mock preview settings.

## Alibaba Cloud security-group configuration

These roles and policies are for the ECS running the backend. The static frontend stores no Alibaba Cloud credentials.

### 1. Create an Instance RAM Role

RAM console → Identities → Roles → Create Role:

| Setting | Example |
| --- | --- |
| Trusted entity / principal type | Alibaba Cloud service / Cloud Service |
| Trusted service / principal name | ECS |
| Role type | Normal Service Role, when this option is shown |
| Role name | `FlightLinkEcsRole` |

The role's trust policy should contain:

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

`Principal.Service` selects ECS as the trusted service. `sts:AssumeRole` lets that service assume the role. **The trust policy does not grant security-group permissions**; attach the access policy below. [Official role guide](https://www.alibabacloud.com/help/en/ram/user-guide/create-a-ram-role-for-a-trusted-alibaba-cloud-service).

### 2. Create a custom access policy

RAM console → Permissions → Policies → Create Policy → JSON / Script editor. Example name: `FlightLinkSecurityGroupPolicy`.

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

Policy explanation:

| Field / action | Meaning |
| --- | --- |
| `Version: "1"` | RAM policy syntax version |
| `Statement` | Permission statements |
| `Effect: "Allow"` | Allows the listed operations |
| `DescribeSecurityGroupAttribute` | Reads rules for preflight and synchronization |
| `AuthorizeSecurityGroup` | Adds DTU / QGC ingress rules |
| `RevokeSecurityGroup` | Removes rules recorded and managed by the backend |
| `Resource: "*"` | Applies these operations to all matching resources in the account, not a single security group |

This example simplifies deployment. The backend uses only its configured group, but that setting **is not a RAM permission boundary**. For narrower access, scope actions that support resource-level authorization using the official table. Current code does not require `ecs:ModifySecurityGroupRule` or `ecs:DescribeSecurityGroups`. [Custom policy guide](https://www.alibabacloud.com/help/en/ram/create-a-custom-policy), [ECS authorization table](https://www.alibabacloud.com/help/en/ram/api-elastic-compute-service).

### 3. Grant permissions and attach the role

1. Open `FlightLinkEcsRole` in RAM and attach `FlightLinkSecurityGroupPolicy`.
2. ECS console → select region and instance → Instance Settings → Attach/Detach RAM Role → select the role.
3. Open the instance's security groups and record the actual group ID. Find the region ID in ECS / OpenAPI, for example `cn-hangzhou`.
4. Enter these values in the installer or `/etc/flightlink/api.env`, then restart the API. The SDK obtains temporary credentials automatically; no long-lived AccessKey is needed.

If ECS already has a role, attach the policy to that role rather than replacing it. [Official attachment guide](https://www.alibabacloud.com/help/en/ecs/user-guide/attach-an-instance-ram-role-to-an-ecs-instance).

### 4. Configure ingress

| Purpose | Inbound rule | Source |
| --- | --- | --- |
| SSH | Current SSH TCP port | Administrator public IPv4 /32 |
| Management UI | TCP `18443`, added manually | Administrator public IPv4 /32 |
| DTU | UDP `5760`, created by backend | `0.0.0.0/0` |
| QGC | TCP `14552`, created by backend | QGC public IPv4 /32 |

Use public source addresses and update settings or rules when they change. The backend does not modify host firewalls or security-group egress rules.
