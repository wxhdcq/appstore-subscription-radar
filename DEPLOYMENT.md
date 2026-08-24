# 部署记录与运维手册

## 当前生产部署

| 项目 | 值 |
|---|---|
| 部署日期 | 2026-08-25 |
| GitHub | `wxhdcq/appstore-subscription-radar`（私有） |
| 服务器 SSH 别名 | `oracle-checkin` |
| 服务器架构 | ARM64 / Ubuntu 24.04 LTS |
| 部署目录 | `/opt/appstore-subscription-radar` |
| 应用监听 | `127.0.0.1:8766` |
| HTTPS 子路径 | `https://status.omniacct.com/appstore-radar/` |
| 应用容器 | `appstore-subscription-radar-radar-1` |
| 数据库容器 | `appstore-subscription-radar-postgres-1` |
| 持久化卷 | `appstore-subscription-radar_radar_postgres` |
| 重启策略 | `unless-stopped` |

服务器使用仓库专属、只读 GitHub Deploy Key。数据库密码和管理令牌由服务器部署脚本随机生成，只保存在权限为 `600` 的 `/opt/appstore-subscription-radar/.env`，不进入 Git。

## 已完成验收

- 应用和 PostgreSQL 容器均为 healthy。
- `/api/health`、首页和 `/docs` 均返回 HTTP 200。
- ChatGPT 的 `US,JP,CN` 小范围真实采集成功：美国、日本成功；中国大陆明确返回未上架或无公开数据。
- 首轮写入 8 个产品、13 条当前价和 13 条初始快照。
- 重启应用容器后数据保持不变。
- `.env` 权限为 `600`。
- 应用仅监听服务器回环地址，没有直接暴露管理接口。

## 查看状态

```bash
ssh oracle-checkin
cd /opt/appstore-subscription-radar
docker compose ps
docker compose logs --tail=100 radar
curl http://127.0.0.1:8766/api/health
```

## 更新部署

```bash
ssh oracle-checkin
cd /opt/appstore-subscription-radar
git pull --ff-only
docker compose build radar
docker compose up -d
docker compose ps
```

更新后必须再次检查健康接口、容器日志和价格数据。数据库 schema 发生变化时，应在构建前先备份数据库，并执行对应迁移流程。

## 数据库备份

```bash
cd /opt/appstore-subscription-radar
umask 077
install -d -m 700 backups
docker compose exec -T postgres pg_dump -U radar radar | gzip > "backups/radar-$(date +%Y%m%d-%H%M%S).sql.gz"
```

备份目录不在 Git 中。生产化后应增加远端加密备份和定期恢复演练。

## 公网入口

应用作为 `status.omniacct.com` 的第二个子项目挂载：

```text
https://status.omniacct.com/appstore-radar/
```

OpenResty 使用仓库中的 `deploy/nginx-appstore-radar.conf`，保留子路径前缀并转发到 `http://127.0.0.1:8766`。容器设置 `ROOT_PATH=/appstore-radar`，确保 OpenAPI、静态资源和 API 请求都使用正确的公共前缀。

反向代理配置位于：

```text
/opt/1panel/www/sites/status.omniact.com/proxy/appstore-radar.conf
```
