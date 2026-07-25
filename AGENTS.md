## Commit Conventions

### Commit Types
1. fix — Bug fixes, issue resolution
2. feat — New features, enhancements
3. chore — Maintenance, dependencies
4. docs — Documentation updates
5. refactor — Code restructuring
6. perf — Performance improvements
7. test — Test additions/fixes
8. style — Code formatting

### Commit Message Format

```
<type>: <scope>: <description>

Examples:
- feat: order: optimize order list query and billing page UX
- fix: bsm: use capitalized action values for API consistency
- feat: i18n: update billing table column header for clarity
- fix: usage: handle empty data export and reset page on period change
```

## Agent Planning Rule

For every non-trivial coding task, if the agent creates a plan or enters plan mode, the finalized plan MUST be written to the repository before implementation.

### Plan Location

Write plans to:

`docs/plan/`

Create the directory if it does not exist.

### Timing

The plan must be persisted after the plan is finalized and before the first code change.

This is a required execution gate.

### Filename

Use:

`YYYYMMDDHHMM-<task-slug>.md`

Example:

`202607021430-add-token-auth.md`

## 前端项目代码规范（通用）

0. 协作流程（最重要）

- **不要自己执行前端的打包、运行命令**：`pnpm build` / `pnpm dev` / `pnpm preview` / `vite` / `tsc` / `lint` 等一律不跑。
- 改完代码直接告诉我变更点，编译、类型检查、构建、启动由我执行。
- 如果确实需要启动项目来验证，先告诉我，由我决定是否启。
- 可以做的：读代码、改代码。

## Python 服务规范

修改 Python 服务代码、配置、迁移、测试、日志或部署脚本前，必须阅读并遵循 [python_server_convention.md](python_server_convention.md)。
