# 删除充值余额

## 背景

各平台对充值余额的定义并不一致：DeepSeek 和 SiliconFlow 返回余额组成，OpenRouter 无法拆分充值来源，xAI 的预充值额度还需要结合已使用额度才能得到当前可用余额。跨平台展示 `prepaid_amount` 容易产生误解，因此仅保留可直接消费的可用余额以及平台明确返回的赠送余额。

## 实施方案

1. 新增 Alembic 迁移，从 `balance_snapshot` 删除 `prepaid_amount`；降级时恢复为可空的 `NUMERIC(20, 2)` 列。
2. 从 SQLAlchemy Model、Provider 统一读数、余额持久化和 API Schema 中删除 `prepaid_amount`。
3. 各 Provider 不再生成充值余额：
   - OpenRouter 仅返回可用余额。
   - DeepSeek 不再解析 `topped_up_balance`。
   - SiliconFlow 不再解析 `chargeBalance`。
   - xAI 继续在内部读取 `prepaidCredits` 和 `prepaidCreditsUsed`，只用于计算可用余额。
4. 从前端 API 类型和平台历史表格中删除充值余额。
5. 更新 Provider、Service 和迁移测试，确认接口与持久化模型不再包含该字段，并验证迁移会删除和恢复数据库列。

## 兼容性

- API 响应不再返回 `prepaid_amount`，属于有意的字段删除。
- 升级迁移会永久删除已有的充值余额历史数据；降级只恢复空列，无法还原已删除的数据。
- 旧迁移和历史方案文档保留当时的结构记录，不进行回写。

## 验证

- 运行后端测试集。
- 对变更的 Python 文件执行语法检查。
- 运行 `git diff --check`。
- 不运行任何前端构建、类型检查、Lint 或启动命令。
