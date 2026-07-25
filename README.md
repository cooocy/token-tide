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

- Python 3.12+
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
python3.12 -m venv .venv
.venv/bin/pip install -e '.[test]'
```

### 3. 配置

`application-example.yaml` 只用于说明配置结构。实际配置存放在远端配置仓库的：

```text
token-tide/application-{CONFIGURATION_TAIL}.yaml
```

启动时通过 Bookstore 下载到 `backend/application-{CONFIGURATION_TAIL}.yaml`。支持以下配置源：

```bash
# GitHub Raw
export BOOKSTORE_ENGINE=github
export BOOKSTORE_GITHUB_URL=https://raw.githubusercontent.com/<owner>/<repo>/main
export BOOKSTORE_GITHUB_TOKEN=<token>

# GitLab Repository Files API
export BOOKSTORE_ENGINE=gitlab
export BOOKSTORE_GITLAB_URL=https://gitlab.example/api/v4/projects/<id>/repository/files
export BOOKSTORE_GITLAB_TOKEN=<token>

# 阿里云 Codeup Files API
export BOOKSTORE_ENGINE=codeup
export BOOKSTORE_CODEUP_URL=https://openapi-rdc.aliyuncs.com/oapi/v1/codeup/organizations/<org>/repositories/<repo>/files
export BOOKSTORE_CODEUP_TOKEN=<token>
```

三组凭证只需配置当前 `BOOKSTORE_ENGINE` 对应的一组。下载失败、内容为空或 YAML 校验失败时，迁移和应用都会立即停止。运行时配置文件已被 Git 忽略。

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

`start.sh` 会创建或复用 `.venv`、更新安装 TokenTide、下载配置、执行数据库迁移、安全停止旧进程并以后台进程重新启动。默认 Python 路径为 `/opt/python/3.12.13/bin/python3`，其他安装位置可通过 `PYTHON_BIN` 指定：

```bash
CONFIGURATION_TAIL=local \
PYTHON_BIN=/path/to/python3 \
./start.sh
```

运行时 PID 保存在 `backend/run/token-tide.pid`。应用、Uvicorn、安装和迁移日志分别写入 `backend/logs/app.log`、`uvicorn.log`、`install.log` 和 `alembic.log`；Python 日志按单文件 20 MiB、保留 10 份滚动。

APScheduler 当前运行在 Web 进程内。生产环境只能启动一个后端 Worker，否则每个 Worker 都会执行定时刷新。

### API

```text
GET  /
GET  /balances
GET  /balances/{provider}/history
POST /refresh
POST /refresh/{provider}
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

开发服务器默认把 `/api` 代理到 `http://127.0.0.1:8800`，转发时会移除 `/api` 前缀。独立部署时将 `VITE_API_BASE` 指向后端公开地址，反向代理使用的外部路径前缀不进入 Python Router。

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

## Python 服务规范

后续修改后端前，请阅读仓库根目录的 `python_server_convention.md`。服务器通过普通 wheel 安装运行；源码发生变化后需要重新执行 `pip install --upgrade`，不能依赖工作目录直接导入源码。
