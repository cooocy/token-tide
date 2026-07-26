# 自定义 Provider 展示顺序

## Summary

通过后端 YAML 的 `providers.order` 集中配置平台顺序。余额接口按该顺序返回，首页沿用现有数组渲染逻辑，无需增加前端排序配置。

## Implementation Changes

- 在配置模型中增加 Provider 名称类型及 `providers.order`。
- 未配置 `order` 时保持现有顺序：OpenRouter、DeepSeek、SiliconFlow、xAI、OpenCode。
- 支持部分配置：列表中的已启用平台优先排列；未列出的已启用平台按默认顺序追加；已禁用平台忽略。
- 未知平台名或重复项视为配置错误，启动时明确报错。
- Provider 工厂按解析后的顺序构造有序字典，使余额查询、批量刷新结果和首页展示共享同一顺序。
- 更新示例 YAML 和 README，说明配置格式与追加规则。
- 不修改余额 API 数据结构、数据库或前端排序逻辑。
- 保留当前尚未提交的 OpenCode Logo 相关改动，不将其改写或混入本功能。

## Test Plan

- 验证未配置 `order` 时保持当前默认顺序。
- 验证完整和部分自定义顺序。
- 验证未列出的已启用平台按默认顺序追加。
- 验证列表中的已禁用平台被忽略。
- 验证重复名称和未知名称导致配置校验失败。
- 验证余额查询和批量刷新结果遵循 Provider 工厂顺序。
- 实施后执行 `git diff --check`；Python 测试由用户执行，不运行前端构建、类型检查或 lint。

## Assumptions

- 自定义顺序同时影响余额接口及首页，而非仅做前端视觉排序。
- 新增 Provider 时，只需加入合法名称及默认顺序；旧配置无需修改。
- 本次不提供拖拽排序或管理页面，顺序只通过远端 YAML 管理。
