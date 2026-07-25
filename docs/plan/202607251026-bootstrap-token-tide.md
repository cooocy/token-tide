# TokenTide 第一阶段实施计划

## 总体方案

在同一个 Git 仓库中建立两个可独立运行、独立部署的工程：

```text
token-tide/
├── backend/
├── frontend/
├── docs/plan/
└── README.md
```

第一阶段按单用户、自部署设计。每个平台只配置一个账户，API Key 仅存在后端 YAML 配置中。默认数据库使用 MySQL，不提供 Docker 文件。

## 实施步骤

### 1. 建立 Monorepo 工程结构

- 后端参考 `melina-lab`，使用 Python 3.13+、FastAPI、Pydantic v2、SQLAlchemy 2、Alembic、APScheduler、HTTPX、PyYAML 和 PyMySQL。
- 使用 `CONFIGURATION_TAIL` 选择 `application-{tail}.yaml`。
- 前端参考 `melina-web` 的 React、TypeScript strict、Vite、目录规范、`@/` 别名和统一 API 层。
- 前端本轮只搭路由、API 层和页面占位骨架，不确定组件库、图表库和最终视觉方案。

### 2. 搭建后端基础能力

- 实现严格 YAML 配置、MySQL Engine/Session、Alembic、CORS、统一 `R<T>` 信封、应用信息接口和异常处理。
- Provider 配置统一包含 `enabled`、`api-key`、`base-url`；xAI 额外包含 `team-id`。
- 启用平台缺少必填项时拒绝启动，错误信息不得包含密钥。

### 3. 建立余额数据模型

- `balance_snapshot` 保存平台、币种、可用/充值/赠送余额、可用状态和查询时间。
- `refresh_run` 保存平台、触发来源、状态、开始/结束时间及脱敏错误。
- 金额统一使用 MySQL `DECIMAL` 和 Python `Decimal`，不做汇率换算。
- 每次成功刷新都保存快照；失败不写快照、不覆盖上一次成功余额。
- 不保存 Provider 原始响应；历史数据第一阶段不自动清理。

### 4. 实现四个平台适配器

- 统一 `fetch_balance() -> list[BalanceReading]` 接口。
- OpenRouter 使用累计充值减累计使用，币种 USD。
- DeepSeek 保存总余额、充值余额和赠送余额，允许多个币种。
- SiliconFlow 保存总余额、充值余额和赠送余额，币种 CNY。
- xAI 使用 Management API Key 与 Team ID，将官方记账方向的美分转换为 USD 可用余额。
- Provider 只负责请求和解析，数据库写入与调度由 Service 层处理。

### 5. 实现刷新流程

- 服务启动后异步刷新一次全部启用平台。
- 按 YAML 中的 cron 和 timezone 定时刷新。
- 支持并发刷新全部平台和刷新指定平台，单个平台失败不影响其他平台。
- 每个平台生成独立 `refresh_run`，第一阶段不自动重试。
- APScheduler 暂时运行在 FastAPI 进程内，生产环境限制为单 Worker。

### 6. 提供后端 API

```text
GET  /
GET  /api/balances
GET  /api/balances/{provider}/history
POST /api/refresh
POST /api/refresh/{provider}
```

- 最新余额返回全部已启用平台，以及最后成功时间和最后刷新状态；尚无快照时为 `NEVER_REFRESHED`。
- 金额以十进制字符串输出。
- 历史接口支持 `currency`、`start-time`、`end-time`、`limit`，默认最近 100 条、最大 1000 条，最终按时间升序返回。
- 手动刷新等待本轮完成并返回各平台结果。

### 7. 搭建前端骨架

- `/` 为余额总览占位页。
- `/providers/:provider/history` 为余额历史占位页。
- Axios client 统一解析 `R<T>`，定义最新余额、历史快照和刷新结果类型及请求函数。
- 配置开发环境 `/api` 代理和 `.env.example`。
- 不实现最终卡片、图表和视觉方案。

### 8. 文档与验证

- README 说明环境要求、MySQL/Alembic、YAML、前后端启动、xAI 配置、单 Worker 限制及独立部署关系。
- 后端覆盖配置、Provider 解析、金额精度、部分失败、最新余额、历史查询和 API 脱敏测试。
- 不执行任何前端 build、dev、preview、tsc 或 lint 命令。

## 验收标准

- 前后端位于同一仓库但可分别安装运行。
- 后端可连接 MySQL并执行 Alembic 迁移。
- 四个平台通过独立适配器接入。
- 启动、定时和手动刷新共用统一流程。
- 可查询最新余额和历史，平台失败不会清空历史或阻断其他平台。
- API Key 不进入数据库、前端、日志和 Git。
- 前端具备继续开发余额总览和历史页的完整工程骨架。
