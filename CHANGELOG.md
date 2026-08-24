# 更新日志

本项目的所有重要变化都记录在此文件中。版本格式遵循 [Semantic Versioning](https://semver.org/lang/zh-CN/)。

## [未发布]

### 计划增加

- 价格变化 Webhook、Telegram 与邮件通知。
- 价格历史图表和历史最低价。
- 抓取运行记录管理页面。
- 全部 Apple storefront 配置和分组刷新。

## [0.1.0] - 2026-08-25

### 新增

- FastAPI 服务器和自动生成的 OpenAPI 文档。
- Apple iTunes Search/Lookup 应用搜索适配器。
- App Store 网页 Catalog IAP/订阅价格适配器。
- 默认覆盖 30 个重点 storefront，限制并发并记录地区级错误。
- 使用 `IAP ID + 订阅周期` 对齐跨地区订阅 SKU。
- PostgreSQL 生产模式和 SQLite 本地开发模式。
- 当前价格、原币价格变更快照和抓取运行记录数据模型。
- USD/CNY 汇率换算与六小时内存缓存；缺失汇率明确显示为“数据缺失”。
- 每日定时刷新任务，默认使用 Asia/Shanghai 时区。
- 中文响应式管理界面，支持应用搜索、添加、刷新、产品切换、地区排序和筛选。
- ChatGPT、Spotify、Notion、YouTube、Bumble、Tinder 六个初始监测项。
- 可选 `ADMIN_TOKEN` 保护新增应用和手动刷新接口。
- Dockerfile、Docker Compose、健康检查和 PostgreSQL 持久卷。
- Apple 解析器、汇率换算单元测试。

### 已知限制

- IAP 数据依赖 App Store 网页内部 Catalog 接口，接口没有稳定性承诺。
- `top-in-app-purchasables` 视图可能只返回热门 IAP，而不是应用的完整商品目录。
- 当前定时器随 API 进程运行，因此初版必须保持单个 Uvicorn worker。
- 初版尚未发送价格变化通知；变更会先保存在数据库。

### 修复

- 修复 CSS `display` 规则覆盖 HTML `hidden` 属性，导致欢迎页和空详情区同时出现的问题。
- 使用内嵌站点图标，消除浏览器请求 `/favicon.ico` 产生的无意义 404 控制台错误。
- 为前端静态资源增加版本参数，避免部署更新后浏览器继续使用旧 CSS/JavaScript 缓存。
- 修复订阅详情工具栏缺少 DOM 标识导致详情数据渲染提前中断的问题。
- 应用详情默认选择订阅产品；只有没有订阅时才回退到一次性 IAP。
- 修复 SQLite 丢失时区偏移后 API 输出裸时间的问题；所有 API 日期现在明确序列化为 UTC `Z` 时间。
- 复用同一刷新任务中的 HTTP 连接并在结束时显式关闭，减少 30 区并发时的连接开销。
- 修复汇率缓存只落在临时实例、导致不同应用重复请求汇率源的问题。
- 显式安装 IANA 时区数据，避免精简 Linux 容器缺失 `Asia/Shanghai` 调度时区。
