# Token Usage Collector 进度与精简错误日志

## Summary

- CLI 默认在 stderr 输出简洁进度和最终结果，`-v` 输出详细阶段及批次信息。
- 非法数据继续输出 stdout JSONL，但删除完整原始数据。

## Logging Changes

- 默认输出整体开始、每 Tool 开始/结果、最终成功失败数量和耗时。
- `-v` 额外输出 cursor 回查、扫描结果、批次序号和服务端处理计数。
- Tool 失败不阻止其他 Tool，最终汇总失败并返回状态码 1。

## Invalid Data Output

- 仅输出 `tool`、`occurred_at`、`source`、`position` 和 `error`。
- 请求时间按来源尽力提取，无法解析时为 `null`。
- 不输出原始 JSON、Prompt 或响应正文。
- 非法完整记录继续推进 cursor，未完成尾行不推进。

## Test Plan

- 覆盖默认日志、verbose 批次日志、多批计数、无变化和失败汇总。
- 覆盖非法记录字段、时间提取和无 `raw` 内容。
- 更新 README 和脚本顶部参数说明，执行 `git diff --check`。
- 按项目约束不由 Agent 运行 Python 测试。
