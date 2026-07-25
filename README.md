# TokenTide 🌊

TokenTide 是一个聚合 AI 平台预充值余额与余额历史的单用户 Dashboard。第一阶段支持 OpenRouter、DeepSeek、SiliconFlow 和 xAI，只调用官方公开 API。

## 工程结构

```text
.
├── backend/      # FastAPI API、定时刷新和 MySQL 持久化
├── frontend/     # React + TypeScript + Vite
└── docs/plan/    # 实施计划
```

前后端位于同一 Git 仓库，但依赖、启动入口和部署生命周期彼此独立。

## 环境要求

- Python 3.13+
- Node.js 20+
- pnpm 10+
- MySQL 8+

## 后端

### 1. 创建数据库

```sql
CREATE DATABASE token_tide
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;
```

创建独立数据库用户并只授予 `token_tide` 数据库所需权限。

### 2. 安装依赖

```bash
cd backend
python3.13 -m venv .venv
.venv/bin/pip install -e '.[test]'
```

### 3. 配置

```bash
cp application-example.yaml application-local.yaml
```

编辑 `application-local.yaml`：

- 修改 `database.url`
- 启用需要的平台
- 填入对应 API Key
- xAI 必须使用 Management API Key，并配置 Team ID
- 根据需要修改刷新 cron 和时区

实际 `application-*.yaml` 已被 Git 忽略，示例配置不会包含真实密钥。

### 4. 迁移与启动

```bash
export CONFIGURATION_TAIL=local
.venv/bin/alembic upgrade head
.venv/bin/token-tide
```

也可以使用：

```bash
CONFIGURATION_TAIL=local ./start.sh
```

APScheduler 当前运行在 Web 进程内。生产环境只能启动一个后端 Worker，否则每个 Worker 都会执行定时刷新。

### API

```text
GET  /
GET  /api/balances
GET  /api/balances/{provider}/history
POST /api/refresh
POST /api/refresh/{provider}
```

历史接口支持：

```text
currency
start-time
end-time
limit        # 默认 100，最大 1000
```

金额统一以十进制字符串返回。

## 前端

前端当前只提供路由、统一 API client 和余额数据流骨架，组件库、图表库与最终 Dashboard 视觉尚未确定。

```bash
cd frontend
cp .env.example .env.local
pnpm install
pnpm dev
```

开发服务器默认把 `/api` 代理到 `http://127.0.0.1:8800`。独立部署时将 `VITE_API_BASE` 指向后端公开地址，或由 Web Server 反向代理 `/api`。

## 刷新行为

- 后端启动后异步刷新一次全部已启用平台
- 定时任务按照配置 cron 刷新
- 页面可以刷新全部或单个平台
- 全量刷新并发执行，单个平台失败不会阻断其他平台
- 失败不会删除或覆盖最后一次成功余额
- 第一阶段不自动重试，也不自动清理历史快照

## 安全边界

- API Key 只从后端配置读取
- API Key 不写入数据库、不返回前端、不输出日志
- 不保存平台原始响应
- 不保存账号密码、Cookie，也不抓取网页或调用私有接口
