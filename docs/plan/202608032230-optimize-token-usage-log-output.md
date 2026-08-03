# 优化 Token Usage Collector 日志输出

## 目标

为 `cli/token_usage_collector.py` 的 CLI 日志输出增加 Nerd Font 视觉层次感，同时简化参数（去掉 `--verbose`）。

## 变更范围

- `cli/token_usage_collector.py`
- `cli/test_token_usage_collector.py`

## 图标选型

用户选择：Nerd Font 优先（非 emoji）

| 场景 | 字符 | 名称 | 码点 (NF v3) |
|------|------|------|-------------|
| 整体开始 | `󰓦` | nf-md-sync | U+F04E6 |
| 整体成功 | `󰗠` | nf-md-check_circle | U+F05E0 |
| 整体有失败 | `󰅙` | nf-md-close_circle | U+F0159 |
| 行内成功 | `󰄬` | nf-md-check | U+F012C |
| 行内失败 | `󰅖` | nf-md-close | U+F0156 |
| 工具开始 | `▶` | — | U+25B6 |
| 工具成功 | `◀` | — | U+25C0 |
| 工具失败 | `✖` | — | U+2716 |

## 子步骤日志

用户选择：全部移除。每个工具只展示 `▶` 开始和 `◀`/`✖` 结束两行，不再有逐批次进度。

## 输出格式

### 整体开始横幅

```
╭─────────────────────────────────────────╮
│  󰓦  TokenTide Sync Started              │
│  Tools: claude, codex, opencode, pi       │
╰─────────────────────────────────────────╯
```

### 每个工具（成功有变化）

```
▶  claude
◀  claude  events=10  batches=3  created=5  updated=3  unchanged=2  ⏱ 1.20s
```

### 每个工具（无变化）

```
▶  claude
◀  claude  no changes  ⏱ 0.05s
```

### 每个工具（失败）

```
▶  claude
✖  claude  sync failed: <error message>
```

### 整体结束横幅（全部成功）

```
╭──────────────────────────────────────────────────╮
│  󰗠  TokenTide Sync Completed                      │
│  󰄬 Succeeded: 4  󰅖 Failed: 0                        │
│  Events: 52  Batches: 3                              │
│  Created: 50  Updated: 2  Unchanged: 0                 │
│  ⏱ Duration: 3.50s                                     │
╰──────────────────────────────────────────────────╯
```

有失败时：图标换 `󰅙`，追加 `Failed: claude, pi` 行。

## 实现细节

### 新增 `print_banner()`

```python
def print_banner(lines: list[str], *, file: Any = sys.stderr) -> None:
    width = max(len(line) for line in lines) + 4
    top = "╭" + "─" * (width - 2) + "╮"
    bottom = "╰" + "─" * (width - 2) + "╯"
    print(top, file=file)
    for line in lines:
        print(f"│  {line}{' ' * (width - len(line) - 4)}│", file=file)
    print(bottom, file=file)
```

### 删除内容

| 删除项 | 位置 |
|--------|------|
| `log_message()` 函数 | L67-L69 |
| `verbose_log()` 函数 | L73-L75 |
| `sync_tool()` 的 `verbose: bool` 参数 | 函数签名 |
| 6 处 `verbose_log(verbose, ...)` 调用 | `sync_tool()` 函数体 |
| `sync_tool()` 内的 2 处 `log_message()` 调用 | start / no-changes / completion |
| `main()` 内的 `log_message()` start/end 调用 | 各 1 处 |
| `parser.add_argument("-v", "--verbose", ...)` | `main()` |
| `args.verbose` 传参 | `main()` 调用 `sync_tool()` 处 |
| `args.verbose` 传参 | 测试文件中 2 处 |

### 测试更新

- `test_default_logging_shows_result_without_verbose_stages`：去掉 `verbose=False`，断言 `▶`/`◀` 行
- `test_only_final_batch_advances_cursor`：去掉 `verbose=True`，断言 `▶`/`◀` 行和汇总字段

## 假设

- 终端使用 Nerd Font 字体
- stderr 仅供人类阅读，无机器解析依赖
- 去掉 verbose 后，运行时无进度输出可以接受
