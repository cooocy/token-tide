# Token 用量页面卡片与间距统一

## Summary

统一“今日 / 总计 / 用量分析”的首卡标题、明细布局和卡片视觉节奏；分析页新增工具占比卡，并将四张内容卡在所有屏幕宽度下单列排列。

## Implementation Changes

- 三个视图的首卡统一为 `TOKEN BREAKDOWN / Token 分布`。
- 从共享 `UsageTokenReading` 中删除 `detailsLabel` 和“今日明细 / 累计明细 / 区间明细”，让右侧五项 Token 明细直接上移。
- 分析页有数据时复用 `UsageDistributionChart` 展示当前筛选结果的 `TOOL SHARE / 按工具`，顺序固定为“Token 分布 → 按工具 → 每日用量 → 模型用量”。
- 分析页四卡继续使用统一外框和 1px 分隔，删除桌面双列规则，所有断点均保持单列；空区间继续显示“Token 分布 + 空状态提示”。
- 二级视图导航使用上方 `18px`、下方 `8px` 的内间距，三个视图内容顶部统一为 `10px`；分析筛选卡到内容、空状态和加载骨架统一为 `14px`。

## Interfaces

- 不修改后端接口、URL 参数、数据类型或筛选行为。
- 仅删除内部组件 `UsageTokenReading` 不再使用的 `detailsLabel` prop。
- 分析工具卡直接使用 `/token-usage/summary` 已返回的 `tools` 数据。

## Test Plan

- 静态检查三个视图均显示 `TOKEN BREAKDOWN / Token 分布`，旧明细文案和 `PERIOD BREAKDOWN / 区间分布` 无残留。
- 检查分析页工具卡使用当前筛选结果，四卡顺序和单列 CSS 在桌面及移动端一致。
- 检查有数据、空数据、加载和错误状态的间距。
- 仅运行文本检索和 `git diff --check`；不运行前端 build、dev、preview、Vite、TypeScript 或 lint 命令。

## Assumptions

- “四卡单列”适用于桌面和移动端。
- 今日与总计仍保留现有桌面三列布局；统一范围为标题层级、边框、圆角、分隔和间距。
- 本次不调整配色、字体、图表实现或筛选交互。
