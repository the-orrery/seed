# seed

## Install

Install the verified `seed-<os>-<arch>` asset from
[GitHub Releases](https://github.com/the-orrery/seed/releases). The executable
bundles Copier and the repository template, so it does not need Python, `uv`,
or a local seed checkout. Generated projects may still run `uv sync` unless
`--no-sync` is used. Targets are macOS arm64 and Linux x86_64 (Ubuntu 22.04
baseline). Use `./scripts/build-release.sh` for a local build and full scaffold
smoke test.

通用 Python 仓脚手架:Copier 模版 + 编排 CLI。`seed new <name>` 从模版生成新仓并建好 uv 环境；后续一致性靠公开自包含 CI、固定工具任务与 `seed status` 审计，不做模版回灌。

## stack（生成仓默认）

uv（包/环境，硬锁）· uv_build（build backend）· ruff（lint+format）· pyrefly（类型）· typer（CLI）· pydantic-settings（配置）· structlog（日志）· pytest（测试）· poethepoet（task）· pre-commit（hook）· Copier（模版引擎）· src layout。

生成仓默认带最小文档骨架：`docs/INDEX.md`（文档入口）和 `docs/architecture.md`（新 contributor 开发地图）。

## 用量遥测（`cli` 自带）

非 `lib` 仓生成 `telemetry.py`：每次调用本地记一行进 SQLite 账本（verb/args/exit/耗时/输出量/stderr 样本/cwd），`<cli> stats` 出 per-verb 次数 / p50·p95 耗时 / error-rate，**驱动工具自身改进**。`run()` 入口把命令跑在 telemetry wrapper 下（`cli.py` 的 console-script = `…cli:run`）。

- **纯本地、零网络、零三方依赖**（stdlib `sqlite3`，WAL+busy_timeout 多进程并发安全，percentile 纯 Python）。结构化日志走 structlog（诊断），用量账本走 telemetry（账本）——两层正交。
- 账本默认在 `$XDG_DATA_HOME/<pkg>/telemetry.db`；`$<PKG>_TELEMETRY_DB` 改路径。
- 关闭：`DO_NOT_TRACK=1` 或 `$<PKG>_TELEMETRY_OFF=1`。
- best-effort：遥测任何失败都不影响主命令的输出与 exit code。账本无限增长，删文件即重置。

## 上手（开发本仓 / 任意生成仓）

开发 checkout 中：

    uv sync                 # .venv 只装纯 Python 依赖
    uv run poe check        # ruff check + format-check + typecheck + test
    uv run poe fmt          # 格式化

## CLI 用法

    uv run seed new <name> --kind cli|lib [--publish]    # 生成 ./<name>
    uv run seed status [root]                            # 只读漂移审计

- `--kind`：`cli`(CLI 工具) / `lib`(可 import 的库)。
- 模版源默认 = 本仓（单仓 dogfood）。跨机/正式用设 `PY_PROJECT_TEMPLATE=<git URL 或路径>` 指远端 tag。
- 生成仓里 `.copier-answers.yml` 记录模版来源；它是 `seed status` 的血缘锚，不再驱动回灌。

## 出单文件 binary（release 时）

    ./scripts/build-release.sh          # PyInstaller + 真实 scaffold smoke

脱 Python 的单二进制，给没装 Python 的机器/容器用。

## 结构

| 路径 | 是什么 |
|---|---|
| `src/seed/` | CLI 源码（薄编排层：Copier 渲染、status 审计、uv 建环境） |
| `src/seed/_template/template/` | Copier 模版内容（`copier.yml` 的 `_subdirectory`），渲染进新仓 |
| `src/seed/_template/copier.yml` | 模版变量（project_name / kind / python_min / publish…）+ 条件 |
| `.github/workflows/template-ci.yml` | self-check + 渲染矩阵(cli/lib) |

CLI 自身也用本模版的 stack（dogfood）。

## 已知坑

- **ruff/pyrefly 不在 dev-deps**：ruff 由 `uvx` 按需运行，pyrefly 由 `uv run --with` 按需运行，生成仓 `.venv` 保持纯 Python。
- **`new` 从模版的 git HEAD 渲染**（不是工作树）——本地改了 `template/` 要先 commit 才生效；正式用 pin 到 tag。
- **`freeze` 每次 build 产新 hash 二进制 → 每次触发一次安全扫描（需手动 approve）**，代码不变也一样（PyInstaller 嵌新 UUID）。故只在 release 做、产物留存，不进 dev loop。
- license 未发布/私有仓用 SPDX `LicenseRef-Proprietary`（裸 `Proprietary` 会被 uv_build 拒）。
