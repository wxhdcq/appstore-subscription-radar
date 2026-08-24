# App Store 全球订阅雷达

可挂载在服务器上的 Apple App Store 订阅价格监测初版。系统按 storefront 采集公开展示的 IAP/订阅价格，对齐同一 SKU，保存当前价和原币价格变更历史，并提供中文比较界面与 API。

## 当前能力

- 根据名称、Apple ID 或 App Store 链接搜索应用。
- 默认查询中国大陆、美国、日本、土耳其、印度、尼日利亚等 30 个重点地区。
- 按 Apple IAP ID 和订阅周期对齐不同地区、不同语言的同一产品。
- 显示当地原币价格、人民币和美元等值、最低价与最大价差。
- 将当前价格和价格变更快照保存到数据库。
- 每日自动刷新所有启用的应用。
- 支持 SQLite 本地运行和 PostgreSQL 容器部署。
- 提供 `/docs` OpenAPI 调试页面。

## 数据源与边界

应用搜索使用 Apple 官方 iTunes Search/Lookup API。订阅数据使用 App Store 网页公开请求中的 Catalog 接口；后者不是 Apple 正式承诺的开发者 API，路径、字段和可用性可能变化。

`top-in-app-purchasables` 可能仅包含热门内购。系统把未返回数据标记为缺失或失败，不把它直接解释成“该地区没有订阅”。所有结果仅用于价格研究，最终价格和购买资格以 App Store 结算页面为准。

请勿用本项目绕过认证、安全控制、地区支付要求或平台条款。公开商业化前应单独审查数据授权和 Apple 相关条款。

## 本地启动

需要 Python 3.12 或更高版本。

```powershell
cd C:\Users\wxhdcq\OneDrive\Desktop\github\appstore-subscription-radar
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
Copy-Item .env.example .env
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

访问：

- 管理界面：<http://127.0.0.1:8000>
- API 文档：<http://127.0.0.1:8000/docs>
- 健康检查：<http://127.0.0.1:8000/api/health>

如果 `.env` 中设置了 `ADMIN_TOKEN`，点击页面左下角“设置管理令牌”，输入相同值。令牌只保存在当前浏览器的 `sessionStorage`。

## Docker Compose 部署

服务器需要 Docker Engine 和 Compose 插件。先创建 `.env`：

```dotenv
POSTGRES_PASSWORD=替换为高强度数据库密码
ADMIN_TOKEN=替换为高强度管理令牌
RADAR_PORT=8766
REFRESH_HOUR=3
REFRESH_MINUTE=20
ROOT_PATH=/appstore-radar
```

然后启动：

```bash
docker compose up -d --build
docker compose ps
```

生产环境应在服务前配置 Caddy、Nginx 或云负载均衡器提供 HTTPS。不要直接使用 Compose 文件中的默认密码。
Compose 默认只监听服务器回环地址 `127.0.0.1:8766`，需要通过反向代理对外提供访问，避免直接暴露应用管理接口。

### 挂载到域名子路径

生产 Compose 默认设置 `ROOT_PATH=/appstore-radar`。将 [deploy/nginx-appstore-radar.conf](./deploy/nginx-appstore-radar.conf) 放入站点的 OpenResty/Nginx `server` 配置中，即可通过以下地址访问：

```text
https://你的域名/appstore-radar/
```

配置使用不带结尾斜杠的 `proxy_pass http://127.0.0.1:8766;`，将 `/appstore-radar/` 前缀原样传给 FastAPI；`ROOT_PATH` 与之保持一致，使 OpenAPI、静态资源和数据请求共用同一公共前缀。直接访问 `/appstore-radar` 会跳转到带 `/` 的规范地址。

## 主要 API

| 方法 | 地址 | 说明 | 管理令牌 |
|---|---|---|---|
| GET | `/api/search?q=ChatGPT` | 搜索 App Store 应用 | 否 |
| GET | `/api/apps` | 监测应用列表 | 否 |
| POST | `/api/apps` | 添加应用 | 是 |
| GET | `/api/apps/{id}` | 应用、订阅产品和当前价 | 否 |
| POST | `/api/apps/{id}/refresh` | 刷新默认 30 区 | 是 |
| POST | `/api/apps/{id}/refresh?regions=US,CN,JP` | 刷新指定地区 | 是 |
| GET | `/api/products/{id}/history` | 原币价格变化历史 | 否 |
| GET | `/api/stats` | 监测统计 | 否 |

管理请求通过 `X-Admin-Token` Header 传递令牌。

## 调度和规模

默认每天北京时间 `03:20` 刷新。时间可通过 `REFRESH_HOUR` 和 `REFRESH_MINUTE` 修改。初版调度器运行在 API 进程内，因此 Uvicorn 必须保持一个 worker，避免重复任务。

30 个 App × 30 个地区约为每轮 900 次 Catalog 请求。扩展到全部 storefront 前，应先连续观察成功率、429/403 和服务器出口 IP 的稳定性。

## 数据表

- `apps`：监测应用和最后刷新状态。
- `products`：以 IAP ID、App、周期唯一标识订阅产品。
- `current_prices`：每个产品在各 storefront 的最新价格。
- `price_snapshots`：首次发现和原币价格变化快照。
- `fetch_runs`：每轮刷新成功率与错误摘要。

## 验证

```powershell
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m ruff check .
```

## 参考项目

- [AppPriceTracker-iOS](https://github.com/paradossio/AppPriceTracker-iOS)：跨地区 IAP 查询和 SKU 对齐思路。
- [appstore-discounts](https://github.com/appstore-discounts/appstore-discounts)：定时价格变更检测和通知流程。
- [Apple iTunes Search API](https://performance-partners.apple.com/search-api)：应用搜索和元数据。

详细版本变化见 [CHANGELOG.md](./CHANGELOG.md)。

当前甲骨文服务器部署状态和更新命令见 [DEPLOYMENT.md](./DEPLOYMENT.md)。
