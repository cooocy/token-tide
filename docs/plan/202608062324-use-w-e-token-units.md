# TOKEN 大数字改用 W / E

## Summary

- 网页 TOKEN 紧凑数字由 K/M/B 改为国内习惯：`W = 万`、`E = 亿`。
- 所有网页 TOKEN 读数复用同一格式化规则，GitHub Profile SVG 保持不变。

## Implementation Changes

- 调整共享 `formatCompactTokenCount`：小于 `10,000` 显示完整千分位数字，
  `10,000` 起使用 `W`，`100,000,000` 起使用 `E`。
- 最多保留 1 位小数，去掉无意义的 `.0`，临界值四舍五入后自动升档。
- 保留完整数字的辅助文本、`title` 和无障碍标签，不调整布局与样式。
- 不修改后端 API、数据类型及 GitHub Profile SVG。

## Test Plan

- 静态核对：`9,999 → 9,999`、`10,000 → 1W`、`12,500 → 1.3W`、
  `99,999,999 → 1E`、`120,000,000 → 1.2E`、`1,200,000,000 → 12E`。
- 检查非有限值仍显示 `—`，完整数字展示不受影响。
- 运行文本检索和 `git diff --check`；不运行前端构建、类型检查或 lint 命令。

## Interfaces and Assumptions

- `formatCompactTokenCount(value: number): string` 的签名不变，仅修改显示语义。
- W/E 与数字直接相连，不增加空格。
