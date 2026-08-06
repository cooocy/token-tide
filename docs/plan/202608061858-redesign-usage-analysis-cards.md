# 用量分析视图：卡片拼图化与间距对齐

## 背景
【Token 用量】中「用量分析」视图的「区间分布 / 每日用量 / 模型用量」三张卡片为独立卡片样式，彼此有可见间隔；与「今日 / 总计」视图的拼图式（1px 发丝线分隔、外层统一圆角边框）不一致。同时「条件选择」卡片距上方切换 bar 偏近，与下方不等距。

## 目标
1. 条件选择卡片不动。
2. 区间分布 / 每日用量 / 模型用量 三卡去掉中间间隔，改成与今日/总计一致的拼图样式。
3. 条件选择卡片与上方 bar 拉远，与下方等距。

## 改动清单

### A. `frontend/src/pages/TokenUsagePage.tsx`
- `{displayedSummary && (...)}` 改为按 `event_count === 0` 分两个分支：
  - 有数据：区间分布、每日用量、模型用量同处 `.usage-analysis-grid`。
  - 空状态：保持原样（区间分布 + 空提示），避免空数据硬凑拼图。

### B. `frontend/src/styles/global.css`
1. `.usage-analysis`（第 2004 行）：`padding-top: 14px` → `28px`，上方拉远。
2. `.usage-analysis-grid`（第 1228 行）：改为拼图（gap:1px + 外层 border/radius/overflow:hidden + background:--line）。
3. 新增：grid 内 `.usage-tide-panel` / `.usage-model-panel` / `.usage-period-reading` 的 border/radius/margin 清零。
4. `.usage-analysis .usage-period-reading`（第 2029 行）：保留空状态 margin（28px 上下）；新增 `.usage-analysis-grid > .usage-period-reading` 覆盖为 0。
5. 980px+ 响应式（第 1547 行）：区间分布通栏占第一行；删 align-items: start。
6. `.usage-analysis > .usage-skeleton`（第 2035 行）：margin-top 对齐 28px。

## 间距终态
```
[ view bar ]
   ↑ 28px (.usage-analysis padding-top)
[ 条件选择 ]
   ↑ 28px (.usage-analysis-grid margin-top)
[ 拼图：区间分布 ┐ 每日用量 ┐ 模型用量 ]  1px 发丝线分隔
```

## 不做
- 条件选择卡片样式不动。
- 不执行 build/dev 命令。
