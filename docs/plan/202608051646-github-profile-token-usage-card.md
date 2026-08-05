# GitHub Profile Token 用量仪表

## Summary

- 新增可嵌入 GitHub Profile README 的 `720×220` 动态 SVG，用于展示个人 AI
  coding 活动。
- 默认以近 7 天 Token 总量为主读数，辅以今日用量、区间请求数、每日趋势和工具占比。

## Public Interface

- 新增公开接口 `GET /token-usage/card.svg`，直接返回 `image/svg+xml`，不使用现有
  JSON 信封。
- 支持 `period=7d|30d`、`tool=all|claude|codex|opencode|pi`、
  `theme=dark|light` 和 IANA `timezone`；默认分别为 `7d`、`all`、`dark` 和
  `Asia/Shanghai`。
- 按所选时区从当地零点计算区间，复用 `TokenUsageService.summary()`，不新增数据表、
  migration 或聚合接口。

## Implementation

- 在 Token Usage 后端领域内增加独立 SVG renderer，负责紧凑数字、日期范围、柱高、
  工具占比、主题色和 XML 安全输出；Router 只负责参数适配与响应。
- 卡片左栏展示主读数、今日用量和请求数；中栏展示按工具堆叠的 `DAILY TIDE`；右栏
  展示 `TOOL MIX` 和当前筛选。
- 使用潮位基线上的堆叠用量柱作为视觉签名；不使用脚本、`foreignObject`、外部字体或
  外部资源。
- 深色沿用 TokenTide 深海色板；浅色使用海玻璃色板。文案固定为英文。
- 空数据返回完整的 `0 Tokens` 卡片；响应设置十分钟公开缓存、`nosniff` 和限制型
  CSP。
- 更新 README，提供 `<picture>` 深浅主题嵌入示例，并让卡片链接到完整用量页。

## Test Plan

- 覆盖默认参数、7/30 天边界、IANA 时区日界线、单工具筛选、空数据和非法参数。
- 验证主总量、今日值、请求数、趋势柱与工具占比均来自同一 summary 结果。
- 验证深浅主题关键色、固定尺寸、SVG 转义、Content-Type、安全头和缓存头。
- 更新后端路由集合断言及 README API 文档，执行 `git diff --check`。
- 不运行前端命令；本机 Python 测试由用户执行。

## Assumptions

- GitHub Profile README 通过 `<picture>` 引用两个主题 URL；卡片本身不判断宿主主题。
- `period` 只支持有可读趋势的 `7d` 和 `30d`；今日用量始终作为辅助指标显示。
- 本期不修改现有前端页面、数据库、运行配置或鉴权边界。
