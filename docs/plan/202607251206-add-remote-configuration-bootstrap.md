# TokenTide 远端配置引导实施计划

## 目标

补齐 `melina-lab` 同等的远端配置下载能力，使 `CONFIGURATION_TAIL=sh00` 在数据库迁移和 FastAPI 初始化前下载 `token-tide/application-sh00.yaml`，不再要求服务器预先存在本地配置文件。

## 实施步骤

1. 新增 Bookstore 配置存储层，支持 GitHub Raw、GitLab Repository Files API 和 Codeup Files API，并通过环境变量选择引擎。
2. 新增 `bootstrap_settings()`，严格按照“下载远端 YAML → 清理 Settings 缓存 → 加载强类型配置”的顺序执行。
3. 调整 Alembic，使迁移读取数据库 URL 前执行相同 bootstrap；配置 URL 写入 Alembic 时转义 `%`。
4. 调整 FastAPI 入口，使 Console Script 先配置日志、完成 bootstrap、配置 FastAPI，再启动 Uvicorn；模块导入本身不读取配置。
5. 按 Python 服务标准将应用、Uvicorn 和 Alembic 日志交给独立的滚动文件处理器，启动脚本不再与 Python 同时写相同日志。
6. 增加 Bookstore、bootstrap、Alembic 和入口顺序测试，覆盖远端路径替换、Base64 解码、缺失引导变量和下载失败。
7. 更新 README，记录 `BOOKSTORE_ENGINE` 及 GitHub、GitLab、Codeup 所需环境变量，并说明生产配置的远端路径。
8. 按 Python 服务标准新增 `python_server_convention.md`，并让 `AGENTS.md` 与 `CLAUDE.md` 引用同一规范。

## 外部契约

- 远端配置路径：`token-tide/application-:tail.yaml`
- 本地文件名：`application-{CONFIGURATION_TAIL}.yaml`
- 超时：8000 毫秒
- 引导变量：
  - `BOOKSTORE_ENGINE=github|gitlab|codeup`
  - `BOOKSTORE_GITHUB_URL` / `BOOKSTORE_GITHUB_TOKEN`
  - `BOOKSTORE_GITLAB_URL` / `BOOKSTORE_GITLAB_TOKEN`
  - `BOOKSTORE_CODEUP_URL` / `BOOKSTORE_CODEUP_TOKEN`

生产启动和 Alembic 都要求引导变量完整；下载、解析或写入失败时立即终止，不回退到可能过期的本地配置。

## 验证

- Python AST、Ruff 和后端测试。
- Mock 远端配置下载，不访问真实配置中心。
- Alembic bootstrap 调用顺序检查。
- Console Script/FastAPI 导入 smoke check。
- Bash 语法与 `git diff --check`。
- 不运行任何前端命令。
