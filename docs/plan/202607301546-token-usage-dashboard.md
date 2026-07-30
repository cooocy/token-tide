# Token 使用量查看页

## Summary

- 新增 `/usage` 数据查看页，默认展示最近 7 天，可切换“今天 / 7 天 / 30 天”。
- 默认汇总 Claude、Codex、OpenCode，也可切换单个工具。
- 延续 TokenTide 深海仪表风格，以按工具分层的“用量潮线”作为页面视觉核心。

## Public Interfaces

- 新增公开只读接口 `GET /token-usage/summary`。
- 参数为可选 `tool`、必填 `start-time`、`end-time` 和
  `timezone-offset-minutes`。
- 查询区间采用 `[start-time, end-time)`；时间必须带时区、开始早于结束、跨度不超过
  31 天。
- 返回区间总 Token、事件数、各 Token 类型计数、工具汇总、按本地日期聚合的趋势，
  以及按总 Token 降序排列的模型汇总。
- 现有 checkpoint 与批量上报接口继续要求 Bearer Token。

## Implementation

- 为跨工具时间查询新增 `occurred_at` 单列索引及 Alembic migration。
- 新增 Usage API 类型、请求封装和 `/usage` 路由；URL 保存时间与工具筛选状态。
- 页面包含总量 Hero、Token 类型明细、按工具分层的每日潮线和模型用量排行。
- 余额看板增加“使用量”入口，并覆盖加载、失败、空数据和移动端布局。

## Test Plan

- 覆盖工具过滤、时间边界、本地日界线、空数据、工具/模型聚合、非法范围和鉴权边界。
- 更新路由集合、migration 与 README API 文档测试。
- 仅执行静态引用检查与 `git diff --check`；Python、Alembic 和前端命令由用户执行。

## Assumptions

- 本期不展示逐条事件、费用、Provider 维度或自定义日期。
- 查询页公开读取，部署层负责需要的站点级访问保护。
- `total_tokens` 独立求和，各 Token 类型仅作明细，不假设相加等于总量。
