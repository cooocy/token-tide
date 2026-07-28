# 统一校正 TokenTide Logo 视觉重心

## Summary

将 Logo 图形整体上移 `12/256`，抵消下方双层波浪的视觉重量，并重新生成网站、favicon、Apple Touch Icon 与 PWA 的全部派生资产。

## Implementation Changes

- 在 `favicon.svg` 中将完整图形上移 12 个 SVG 单位；不修改路径造型、渐变、颜色或网页 Logo 尺寸。
- 同步调整 `pwa-maskable.svg` 的纵向变换，使安全留白内的 Logo 获得相同视觉偏移，并继续满足 maskable 裁切安全区。
- 由校正后的 SVG 重新导出透明背景的 192px/512px PWA 图标、256px favicon，以及深色背景的 180px Apple Touch Icon 和 512px maskable PWA 图标。
- 保留全部现有文件名、manifest 配置、HTML 引用和页面结构；不修改公共 API、路由或业务逻辑。

## Test Plan

- 静态确认两个 SVG 的图形重心一致，普通图标上下留白约为 `12:16`，呈现轻微视觉上移。
- 使用 `file`、`sips` 检查 ICO/PNG 的格式、尺寸、透明通道和背景属性。
- 逐一目视检查网页 Logo、普通 PWA、maskable PWA 与 Apple Touch Icon，确认没有裁切且纵向观感一致。
- 执行 `git diff --check`；不运行 `pnpm build`、`vite`、类型检查或其他前端命令。

## Assumptions

- 采用已确认的“视觉居中”方案：上移 `12/256`，而非严格几何居中的 `10/256`。
- Logo 造型、配色、大小、安全留白比例及现有资源 URL 均保持不变。
