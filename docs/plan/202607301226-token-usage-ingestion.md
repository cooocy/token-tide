# Token Usage 增量采集与批量上报

## Summary

- 将 `cli/token_usage_collector.py` 收敛为单次运行的增量上报器。
- 服务端新增 Bearer Token 认证、Token Usage 持久化、cursor 回查和原子批量上报。
- 首次运行读取全部历史，后续完全使用服务端保存的每 Tool cursor。

## Public Interfaces

- 配置新增必填的 `token-usage.auth-token`。
- CLI 从 `TOKEN_TIDE_BASE_URL` 和 `TOKEN_TIDE_TOKEN_USAGE_TOKEN` 读取连接信息。
- `GET /token-usage/{tool}/checkpoint` 返回该 Tool 的 cursor。
- `POST /token-usage/{tool}/events/batch` 原子 upsert 最多 500 个事件并更新
  `next_cursor`，允许空事件批次。
- 相同源事件内容变化时更新为最新内容；相同内容重试保持幂等。

## Collector

- Claude/Codex JSONL 使用逐文件字节 offset；只推进完整行，文件截断或替换时重扫。
- Codex cursor 额外保留 model、累计 Token 基线和事件序号。
- OpenCode SQLite 使用 `time_updated` 包含式水位增量读取；无数据库时回退到
  `storage/message` JSON 文件。
- 非法完整数据以结构化 JSONL 输出 stdout 并推进 cursor；运行状态和错误写
  stderr。
- 每个 Tool 独立同步；任一失败时最终非零退出，未成功请求不推进 cursor。

## Server and Storage

- 新增 `token_usage_event` 和 `token_usage_checkpoint` 表、约束、索引及 Alembic
  migration。
- `(tool, source_event_id)` 唯一；事件 upsert 与 checkpoint 更新使用同一事务。
- Token Usage 独立于 balance，只共享应用配置、数据库和响应基础设施。

## Test Plan

- 覆盖认证、配置、空 cursor、批量新增/更新/重试、批内重复、上限和事务行为。
- 覆盖三类来源首次全量、增量、JSONL 尾行/截断、Codex 累计 fallback、
  OpenCode 更新水位及非法数据输出。
- 更新 README 和示例 YAML；执行静态引用检查和 `git diff --check`。
- 遵守项目约束，不由 Agent 执行 Python、pytest 或 Alembic。

## Assumptions

- 只有一个采集设备，同一时刻只运行一个 collector。
- OpenCode 新增或修改消息时会更新 `time_updated`。
- 不实现用量查询/统计 API、费用计算、前端或常驻调度进程。
