# 简化 Token Usage 领域设计

## Summary

- 移除多设备和多日志流抽象，仅保留每个 Tool 一份独立 cursor。
- `TokenUsageEvent` 直接记录来源 Tool，并区分原始请求时间与采集器上报时间。

## Key Changes

- 删除 `TokenUsageCollector` 和 `TokenUsageStream`。
- 将 `TokenUsageCheckpoint` 简化为 `tool` 和 `cursor`，删除 `revision` 及其校验。
- 将 `TokenUsageEvent.stream` 替换为 `tool`。
- 保留 `occurred_at` 表示原始日志中的请求时间，新增必填的 `reported_at`
  表示采集器生成并上报事件的时间。
- 保留事件 ID、模型、Provider、Token 明细及非负校验。
- 本轮只修改领域类型与对应测试，不接入 CLI、API、数据库、迁移或上报协议。

## Test Plan

- 确认 Tool 枚举值保持稳定。
- 确认简化后的 Checkpoint 仍不可变，并可为不同 Tool 保存独立 cursor。
- 确认事件同时保存来源 Tool、原始请求时间和上报时间。
- 保留负 Token 数量拒绝测试，删除 revision 相关测试。
- 静态检查旧类型和字段引用，并执行 `git diff --check`。
- 遵守仓库约束，不由 Agent 执行 Python 或 pytest。

## Assumptions

- 每个 Tool 只有一个逻辑 Checkpoint；Tool 内多文件或多会话进度由 cursor 表达。
- `reported_at` 使用采集器时钟，不表示服务端接收或入库时间。
- 两个时间字段都由调用方显式传入，本轮不新增时区强制校验。
- `source_event_id` 继续在各 Tool 范围内标识源事件，去重约束留待后续实现。
