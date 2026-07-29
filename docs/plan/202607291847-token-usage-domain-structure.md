# Token Usage 独立域框架重构

## Summary

- 将现有余额功能迁入 `token_tide.balance`，新增独立的
  `token_tide.token_usage` 域。
- 将根目录 `token_usage.py` 移至 `cli/token_usage_collector.py`，保持现有扫描、
  统计、价格和参数行为。
- 本轮不实现 API、上报协议、数据库表、迁移或游标持久化。

## Key Changes

- `balance` 接收现有余额专属模型、Schema、Provider、服务、依赖、路由和调度
  逻辑；根配置负责组合应用配置，余额配置类型进入 `balance.config`。
- SQLAlchemy `Base` 作为跨域基础设施放入根层 `database.py`；迁移环境显式导入
  `balance.models` 注册元数据，为以后注册 `token_usage` 模型预留一致入口。
- 根层 `schemas.py` 仅保留 `ApplicationInfo` 等应用级类型；`main.py` 改为从
  `token_tide.balance` 完成服务装配、路由注册和余额调度。
- 仓库内全部切换到 `token_tide.balance.*`，不保留旧路径兼容转发模块。
- `token_usage.domain` 定义无持久化依赖的核心类型：
  `TokenUsageTool`、`TokenUsageCollector`、`TokenUsageStream`、
  `TokenUsageCheckpoint`、`TokenUsageEvent`。
- 新增根层 `cli/`，将脚本改名为 `token_usage_collector.py`；更新脚本说明、
  运行示例和 README 路径，不加入后端 wheel 或 Console Script。

## Test Plan

- 更新现有后端测试的 import，确保余额路由、服务、Provider、调度器及 Alembic
  元数据行为不变。
- 增加轻量领域类型测试，确认枚举值、冻结属性及 Token 字段非负约束。
- 静态检查所有旧模块引用均已清除，并执行 `git diff --check`。
- 遵守项目约束，不由 Agent 运行 Python、pytest 或前端命令。
- 验收标准：现有 HTTP 路径与响应不变，余额功能只发生包路径迁移，采集脚本
  原参数和输出保持不变，`token_usage` 不依赖 `balance`。

## Assumptions

- `balance` 与 `token_usage` 是完全独立的业务域，只共享应用基础设施。
- 服务端游标仍是未来 `token_usage` 域的一部分，但本轮仅保留领域概念，不实现
  存储或同步。
- 不新增数据库迁移、不修改现有表、不增加 API 和认证配置。
