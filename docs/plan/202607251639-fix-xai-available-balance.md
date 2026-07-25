# 修复 xAI 可用余额计算

## 背景

xAI 控制台显示预充值 `$5.00`、已使用 `$1.35`、剩余 `$3.65`，TokenTide 的历史快照却持续将可用余额和充值余额都记录为 `$5.00`。

当前 Provider 读取 `/v1/billing/teams/{team_id}/prepaid/balance` 的 `total.val`，并把该值同时作为可用余额与充值余额，没有扣除已使用的预付额度。

## 实施方案

1. 将 xAI 余额数据源切换为 `/v1/billing/teams/{team_id}/postpaid/invoice/preview`。
2. 从 `coreInvoice.prepaidCredits.val` 读取预充值额度，从 `coreInvoice.prepaidCreditsUsed.val` 读取已使用额度；两者均按美分转换为美元。
3. 按 xAI 的记账方向计算：
   - 充值余额：`-prepaidCredits / 100`
   - 可用余额：`(-prepaidCredits - prepaidCreditsUsed) / 100`
4. 对缺失或类型错误的 `coreInvoice`、`prepaidCredits`、`prepaidCreditsUsed` 保持统一的 `invalid_response` 错误处理。
5. 更新 Provider 单元测试，覆盖 `$5.00 - $1.35 = $3.65`、请求路径与响应结构校验。

## 验证

- 运行 xAI Provider 定向测试。
- 运行后端测试集。
- 运行 `git diff --check`。
- 不运行任何前端构建、类型检查、Lint 或启动命令。
