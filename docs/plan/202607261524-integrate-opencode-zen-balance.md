# 集成 OpenCode Zen 余额查询

## 背景

OpenCode Zen 当前没有支持 API Key 鉴权的公开余额 OpenAPI。已验证其 Web Dashboard
内部 billing RPC 可以使用登录 Cookie 与 Workspace ID 查询当前 Zen 美元余额。该接口
返回的原始余额单位需要除以 `100000000` 才是 USD。

本次将该能力作为实验性 Provider 接入 TokenTide，并明确记录其私有接口属性与失效边界。

## 实施步骤

1. 扩展后端类型化配置：
   - 为 OpenCode 定义独立配置，不把登录 Cookie 伪装成 API Key。
   - 配置 `enabled`、`auth-cookie`、`workspace-id`、`base-url`、`proxy-url`。
   - 启用时校验 Cookie 名称和值，以及 `wrk_...` 格式的 Workspace ID。
2. 实现 OpenCode Provider：
   - 只向配置的 OpenCode 主机发送 Cookie。
   - 调用当前 billing server function，并携带 Dashboard 所需请求头与参数。
   - 同时兼容 JSON 与服务端 JavaScript 序列化响应。
   - 校验响应包含客户上下文与余额，将原始金额按 `1e8` 换算为 USD。
   - 将网络、鉴权和响应格式错误归一化为不包含敏感信息的 `ProviderError`。
3. 注册 Provider 并更新展示：
   - 将 OpenCode 加入 Provider 工厂。
   - 前端名称显示为 `OpenCode`，无图片资源时使用 `OC` 文字标记。
   - 不修改数据库；现有 provider 字符串与 USD 快照结构可直接承载。
4. 补充测试：
   - 覆盖启用配置的 Cookie/Workspace 校验。
   - 覆盖代理隔离、请求参数和敏感鉴权头。
   - 覆盖序列化响应解析、金额换算及无效响应。
5. 同步示例与文档：
   - 在 `application-example.yaml` 增加无真实凭证的 OpenCode 配置。
   - 在 README 说明内部接口、Cookie 名义有效期、提前失效场景及安全风险。
   - 修正安全边界，明确仅 OpenCode 实验性 Provider 使用登录 Cookie。
6. 静态核对：
   - 检查完整 diff、敏感值和 `git diff --check`。
   - 按本机约束不执行 Python、pytest、前端构建、类型检查或 lint，由用户完成运行验证。

## 验收标准

- 启用 OpenCode 后，定时刷新可持久化两位小数的 USD 可用余额。
- Cookie、完整响应和客户标识不进入日志、数据库或前端接口。
- Cookie 失效、HTTP 失败或 RPC 格式变化时生成安全、可诊断的失败记录。
- 未启用 OpenCode 时不改变现有 Provider 行为。
