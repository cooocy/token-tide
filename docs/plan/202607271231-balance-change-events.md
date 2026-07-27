# 增加余额变动事件并改造历史阶梯图

## 目标

- 新增 `balance_change_event` 表。`balance_snapshot` 继续保存每次采样，当前余额继续读取最新 snapshot；历史接口只查询变动事件。
- 不回填旧的逐次变动，但迁移时为每个平台、币种的最新 snapshot 建立一条 `INITIAL` 基线事件。
- 保留 `GET /balances/{provider}/history` 路径，将响应改为显式 `events` 结构。

## 后端与数据变更

1. 事件表保存唯一关联的 snapshot、平台、币种、变动前后余额、有符号差额、`INITIAL | SUPPLY | CONSUMPTION` 和发生时间。
2. Alembic 迁移创建事件表、约束和查询索引，并用每个平台币种的最新 snapshot 建立 INITIAL；降级只删除事件表。
3. 成功刷新在同一事务内写 snapshot 和事件：首次采样写 INITIAL，金额增加或减少写 SUPPLY 或 CONSUMPTION，金额不变不写事件。
4. `STARTUP`、`SCHEDULED` 和兼容保留的 `MANUAL` 共用事件逻辑；失败刷新不产生 snapshot 或事件。
5. 历史查询改为只读事件表；保留币种、起止时间和 limit 参数，选取最新 N 条后按发生时间正序返回。

## API 与前端

- history 响应包含 `provider`、`currency`、`events`；事件包含 `id`、`currency`、`previous_amount`、`current_amount`、`change_amount`、`change_type`、`occurred_at`。
- 历史页同时读取 `/balances`：币种、当前余额和采样时间来自最新 snapshot；事件列表、区间汇总和图表来自 history。
- INITIAL 只作为基线，不计入补给、消耗或净变化；历史不再展示 UNCHANGED。
- 将 SVG 折线改为阶梯路径，在事件位置从变动前余额垂直跳到变动后余额，并保持移动端触摸选点能力。
- 更新空状态与 README，明确 snapshot 和 event 的职责。

## 验证

- 增加迁移测试，覆盖建表、最新 INITIAL 基线、同时间 ID 决胜和降级。
- 增加服务测试，覆盖首次采样、增加、减少、不变、币种隔离、失败刷新和历史事件查询。
- 增加 schema UTC 序列化与路由契约检查。
- 遵循本机约束，不运行 Python 或前端构建、测试、类型检查命令；仅执行 `git diff --check`。

## 已确认约束

- 余额变动仅指两位小数归一化后的 `available_amount` 变化，availability 状态变化不产生事件。
- INITIAL 的前值和差额为 `null`。
- history URL 保持不变，但响应字段正式切换为事件语义。
- 不提交、不推送，除非后续明确要求。
