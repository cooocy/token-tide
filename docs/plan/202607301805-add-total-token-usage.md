# 增加 Token 全部历史总计

## Summary

- 在时间筛选中增加“总计”，顺序为“今天 / 7 天 / 30 天 / 总计”，默认仍为 7 天。
- “总计”统计数据库内全部历史事件，继续受“全部 / Claude / Codex / OpenCode”工具筛选影响。
- 总计模式展示累计 Token、请求次数和 Token 分布，不生成全部历史的每日图表及模型排行。

## API Changes

- 新增公开只读接口 `GET /token-usage/totals`，接受可选 `tool` 参数。
- 响应复用 `TokenUsageTotals`：`event_count`、`total_tokens`、输入、输出、缓存写入、缓存读取和推理 Token。
- 使用 SQL `COUNT`、`SUM`、`COALESCE` 完成数据库内聚合，只返回一行；不读取完整事件到 Python。
- 不修改现有 `/token-usage/summary` 的 31 天限制，不增加缓存、汇总表或数据库迁移。

## Implementation Changes

- 前端增加 `period=total` URL 状态；选中后调用 totals 接口，工具切换时重新查询对应工具的全部历史总计。
- 总计模式复用当前大数字 Hero 和“Token 分布”结构，显示精确 Token 数与请求数。
- 总计为零时仍展示值为 `0` 的分布，并提供“还没有累计用量”空状态。
- 区间模式维持现有总量、每日用量和模型排行；切换模式时清除旧数据，避免短暂显示上一口径结果。
- README 同步新增接口、查询参数、全部历史统计口径及性能说明。

## Test Plan

- 后端覆盖全部工具总计、单工具筛选、空表、各 Token 字段独立求和，以及 `total_tokens` 不等于明细字段之和的情况。
- API 路由测试确认 totals 接口公开读取、`tool` 枚举校验和统一响应封装。
- 前端静态检查默认 7 天、`period=total`、工具切换、加载、失败、空数据和从总计切回区间。
- 检查 320px 移动端四个时间按钮、总量长数字和 Token 分布布局。
- 执行 `git diff --check`；Python 测试和前端构建、类型检查、lint 由用户运行。

## Assumptions

- “总计”指采集入库的全部历史数据，不代表各平台账单系统中的官方累计值。
- 总计模式只需要累计数与 Token 类型分布，不包含跨全部历史的每日趋势和模型排行。
- 1 万条事件直接 SQL 聚合足够轻量；只有达到百万级并出现实际慢查询后，才考虑增量汇总表。
