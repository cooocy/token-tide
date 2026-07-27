# 将 TokenTide 前端改造为 PWA

## Summary

为现有 React + Vite 前端增加可安装、可离线启动的 PWA 能力。仅缓存应用外壳，余额和历史 API 始终请求实时数据；不新增安装按钮；新版本自动更新。

## Implementation Changes

- 在前端开发依赖中加入兼容 Vite 6 的 `vite-plugin-pwa@^1.3.0`，并在 Vite 配置中启用 `generateSW`、过期缓存清理和 `autoUpdate`。
- 配置 manifest：名称 `TokenTide`、语言 `zh-CN`、`standalone` 显示模式、现有深色主题、根路径 `start_url`/`scope`，以及 192px、512px 和 maskable 图标。
- 从现有 `favicon.svg` 生成普通 PWA 图标、带安全留白的 maskable 图标和 180px Apple Touch Icon；保留现有 favicon。
- 在 HTML 中补充 Apple Touch Icon、iOS standalone 和状态栏元信息。
- 预缓存 HTML、JS、CSS、字体和本地图像，使首页及历史路由在断网后仍可打开应用外壳；不配置任何 API runtime cache，不缓存 `/api`、生产 `/token-tide/` 或第三方请求。
- 更新 README，说明安装条件、离线语义、自动更新行为和 HTTPS/localhost 要求。
- 不修改页面布局、前端业务数据结构、路由结构或后端 API。

## Public Interfaces

- 新增 Web App Manifest、Service Worker 和标准 PWA 图标资源。
- 浏览器获得原生安装入口；页面内不增加安装按钮或 iOS 教程。
- 离线时沿用现有 API 错误界面，不展示缓存余额或历史数据。

## Test Plan

- 静态检查 manifest 字段、图标路径、Service Worker 缓存范围及 API 排除规则。
- 由用户执行 `pnpm install` 和 `pnpm build`，确认生成 manifest、Service Worker 和图标引用；本机不代跑前端命令。
- 在 HTTPS 或 localhost 环境验证 Chrome/Edge 可安装，安装后以 standalone 模式启动。
- 在线访问首页和历史页后断网，确认两个路由仍能加载应用外壳，同时余额请求明确失败且不存在旧金额响应。
- 发布一次静态资源变更，确认 Service Worker 自动取得并接管新版本。
- 使用浏览器 Application/Lighthouse 检查 manifest、图标、安装资格、离线启动和 Service Worker 控制状态。

## Assumptions

- 前端继续部署在域名根路径；生产 API 仍为 `https://wormhole.dcyy.cc/token-tide/`。
- PWA 不承担余额数据的离线可用性，避免把过期金额误认为当前余额。
- 依赖安装、构建、运行、类型检查和浏览器验证均由用户执行。
