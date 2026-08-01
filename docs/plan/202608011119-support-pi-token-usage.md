# 支持 Pi Token Usage

## Summary

- 将 Pi 作为第四个 Token Usage 工具，公开标识固定为 `pi`，界面名称固定为 `Pi`。
- 扩展现有 CLI、后端统计和前端筛选/图表；不新增数据库表或迁移，不改变现有鉴权边界。

## Public Interfaces

- 后端 `TokenUsageTool` 增加 `PI = "pi"`；现有 checkpoint、批量上报、summary、totals、overview 接口直接接受 `tool=pi`。
- 汇总响应中的 `tools` 和每日 `tools` 映射固定包含 Claude、Codex、OpenCode、Pi，空数据补零。
- 前端 `TokenUsageTool` 联合类型增加 `pi`，URL 使用 `?tool=pi`。
- CLI 支持官方 `PI_CODING_AGENT_DIR` 和 `PI_CODING_AGENT_SESSION_DIR`；默认读取 `~/.pi/agent/sessions/`。

## Implementation

- CLI 新增 `scan_pi` 并接入统一 `TOOLS/scanners` 流程，递归增量读取 Pi v1–v3 Session JSONL，沿用文件 identity、字节 offset、完整行、截断重扫和独立 checkpoint 机制。
- Session 目录解析顺序为 `PI_CODING_AGENT_SESSION_DIR`、`PI_CODING_AGENT_DIR/settings.json` 的 `sessionDir`、`PI_CODING_AGENT_DIR/sessions`；相对 `sessionDir` 按 Pi 配置目录解析。
- Token 映射固定为 `input -> input_tokens`、`output -> output_tokens`、`cacheWrite -> cache_creation_tokens`、`cacheRead -> cache_read_tokens`、`totalTokens -> total_tokens`，Pi 未提供独立 reasoning 时记零。
- 普通 assistant 使用日志内的 provider/model；compaction、branch summary 使用扫描时维护的当前模型状态；toolResult 按 `message.provider/model`、`message.details.provider/model` 的顺序读取，仍缺失时使用 `model=pi-internal`、空 provider。
- 零用量记录跳过；非法 usage 输出既有精简 JSONL 错误并推进完整行 cursor，不输出原始会话内容。
- `source_event_id` 基于 Pi Entry 的稳定内容元数据生成，不依赖 v1 缺失、迁移时随机生成的 Entry ID，也不包含目标 Session ID，使 v1→v3 迁移及 fork/clone 复制的历史记录保持幂等且不重复计费。
- 后端只扩展枚举和测试期望；现有 `String(16)`、唯一键、checkpoint、SQL 聚合和认证模型可直接容纳 `pi`，因此不做迁移。
- 前端增加 Pi 筛选项、工具元数据及 `#e47f96` 配色；工具顺序固定为 Claude、Codex、OpenCode、Pi，并同步更新工具占比、每日潮线、读数和图例，移动端筛选区允许换行。
- README 更新四工具说明、Pi 环境变量、目录优先级、统计口径及 `pi-internal` 含义。

## Test Plan

- CLI 覆盖默认/自定义目录、首次全量与 offset 增量、尾部不完整行、截断、assistant 字段映射、模型切换、摘要归属、toolResult 显式模型与 `pi-internal` fallback、零用量、非法 usage，以及 fork/clone 历史去重。
- 后端覆盖 `pi` 枚举、checkpoint/ingest 接受 Pi、四工具补零、Pi 单工具过滤，以及 overview/summary/totals 聚合。
- 静态检查所有三工具硬编码点均扩展为四工具，并执行 `git diff --check`。
- Agent 不运行 Python、pytest、Alembic、前端构建、类型检查或 lint；完成后提供建议命令，由用户执行并反馈结果。

## Assumptions

- 统计范围包含 assistant、compaction、branch summary 和带 usage 的 toolResult，以尽量对齐 Pi Footer。
- 无法证明真实模型身份的工具内部调用统一归入 `pi-internal`，不错误归给当前模型。
- 不采集费用，不新增逐事件页面，不调整模型聚合规则，也不改变 Claude、Codex、OpenCode 的现有数据。
- 使用自定义 `--session-dir` 且未写入设置的 Pi Session，需要通过 `PI_CODING_AGENT_SESSION_DIR` 告知 collector。
