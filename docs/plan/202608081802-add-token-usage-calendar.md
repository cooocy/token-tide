# Token 用量贡献日历

## Summary

- 新增第 4 个一级视图 `CALENDAR / 日历`，URL 使用 `view=calendar`。
- 展示以本周周一为基准、向前覆盖 53 周的整体 Token 用量，不提供工具筛选。
- 使用 TokenTide 现有深海青视觉体系：空白 `#102B33`，四档活跃色 `#17505A / #1D7475 / #27A69B / #32D6C5`，不引入新字体。

## Implementation Changes

- 新增公开接口 `GET /token-usage/calendar`：
  - 参数为包含首尾的 `start-date`、`end-date` 和浏览器提供的 IANA `timezone`。
  - 最长允许 371 天，返回零值补齐的每日日期、请求数和 Token 数。
  - 使用数据库侧日期聚合，不放宽或复用现有 31 天 `summary` 查询；正确处理 DST。
  - 复用现有时间索引，不增加表、迁移、缓存或汇总任务。
- 前端增加独立贡献日历组件：
  - 浏览器计算当前周周一往前 52 周至今天的请求范围，共固定 53 列；本周未来日期显示为空白占位格。
  - 月份标记置于顶部，左侧显示“一 / 三 / 五”，底部提供“少—多”颜色图例。
  - 强度使用区间内对数归一化，零用量为 0 档，非零为 1–4 档。
  - 顶部详情区显示日期、精确及紧凑 Token、请求数；默认选中今天。
  - 悬停临时预览，点击、触摸或键盘确认后固定选中。
- 页面状态与响应式：
  - 日历视图独立懒加载并缓存，不影响现有三个视图。
  - 桌面完整展示 53 周；手机横向滚动并默认定位到最近日期，星期标签固定在左侧。
  - 复用现有卡片圆角、加载骨架、错误重试和空状态，支持键盘、屏幕阅读器和 reduced-motion。

## Public Interfaces

```text
GET /token-usage/calendar
  ?start-date=YYYY-MM-DD
  &end-date=YYYY-MM-DD
  &timezone=Asia/Shanghai
```

```ts
interface TokenUsageCalendarDay {
  date: string;
  event_count: number;
  total_tokens: number;
}

interface TokenUsageCalendar {
  start_date: string;
  end_date: string;
  timezone: string;
  days: TokenUsageCalendarDay[];
}
```

现有 `/summary`、`/overview`、SVG 卡片和数据库结构保持不变。

## Test Plan

- 后端覆盖跨月、跨年、零值补齐、本地午夜、DST、无效时区、倒置日期和超过 371 天。
- 前端验收深链接、加载、失败重试、空状态、53 列布局、未来日期、对数分档、鼠标与键盘交互。
- 验收 320px 手机横向滚动定位和桌面完整布局。
- 按项目约束不执行 Python 或前端构建、类型检查、测试命令；仅做静态检查和 `git diff --check`。

## Assumptions

- 日历只展示所有工具合计，不增加工具维度或日期详情页。
- 时间范围随当天滚动，不提供年份切换。
- 日界线采用浏览器 IANA 时区；无法取得时回退 `Asia/Shanghai`。
- 不修改现有短期“每日用量”图表；除非用户另行要求，否则不提交或推送代码。
