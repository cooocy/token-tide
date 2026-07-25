# 金额精度与 Provider 代理优化实施计划

## 目标

1. 所有余额金额按十进制四舍五入为 2 位小数，并在 API 中固定返回 2 位。
2. 通过 Alembic 清洗已有余额快照，再将数据库金额列从 `NUMERIC(20, 8)` 收窄为 `NUMERIC(20, 2)`。
3. 允许每个 Provider 独立配置可选的 HTTP 代理，例如 xAI 使用 `proxy-url: http://127.0.0.1:3128`，由服务端通过代理请求对应平台。

## 实施步骤

1. 在金额持久化边界使用 `Decimal.quantize(..., ROUND_HALF_UP)`，确保新快照写入前已按业务规则保留 2 位。
2. 将金额模型列调整为 `NUMERIC(20, 2)`；新增 Alembic 迁移，先对三个金额列执行 `ROUND(..., 2)` 清洗历史数据，再修改列精度。
3. API 金额序列化固定使用两位小数，保证余额列表和历史接口的字符串格式一致。
4. 为 Provider 强类型配置增加可选 `proxy-url`，仅接受 HTTP/HTTPS URL；构造 Provider 的 `httpx.AsyncClient` 时传入该 Provider 的代理。
5. 更新 `application-example.yaml` 和 README，说明代理按 Provider 独立生效且不配置时直连。
6. 增加配置、代理传递、金额舍入、持久化和接口格式测试。

## 数据迁移策略

- 升级：先用数据库 `ROUND(column, 2)` 清洗 `available_amount`、`prepaid_amount`、`granted_amount`，再改为 `NUMERIC(20, 2)`。
- 降级：只恢复为 `NUMERIC(20, 8)`，已清洗掉的额外小数位不可恢复。
- 新写入：应用层在数据库提交前显式使用 `ROUND_HALF_UP`，不依赖不同数据库的隐式转换行为。

## 配置契约

每个 Provider 都可以增加：

```yaml
proxy-url: http://127.0.0.1:3128
```

该配置仅用于对应 Provider 的余额 API 请求；省略或配置为 `null` 时保持直连。API Key、代理地址和完整请求信息均不写日志。

## 验证

- 运行后端测试，覆盖正数与负数的五入边界、数据库持久化、固定两位输出、代理启用和无代理直连。
- 生成并检查 MySQL Alembic 离线 SQL，确认先清洗再修改列类型。
- 运行 Ruff（若当前环境可用）和 `git diff --check`。
- 不运行任何前端构建、类型检查、Lint、开发或预览命令。
