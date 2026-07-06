---
description: "seed 模板仓架构总览：项目定位、模板结构、CLI 主路径、status 审计维度、核心不变量和改动入口。"
keywords: [seed, 模板仓, Copier, architecture, codemap, uv, ruff, pyrefly, status]
kind: reference
---

# seed 架构

> 给新 contributor 的一页地图：这个仓是什么、模板长什么样、CLI 怎么把模板变成新仓、改某类东西该从哪里入手。

## 1. 鸟瞰

seed 是通用 Python 仓的一次性脚手架：一个 Copier 模板加一个薄 CLI。`seed new <name>` 从模板渲染出一个新仓、建好 uv 环境、`git init` 留首个 commit。渲染后，生成仓脱离模板自己演进。

选定栈：uv、uv_build、ruff、pyrefly、pytest、poethepoet、typer、pydantic-settings、structlog、Copier、src layout。CLI 自己也用同一套栈做 dogfood。

## 2. 两层拓扑

| 层 | 路径 | 是什么 | 谁消费 |
|---|---|---|---|
| 模板层 | `src/seed/_template/template/` | Copier 渲染内容，等于生成仓的初始内容 | `copier` |
| 模板配置 | `src/seed/_template/copier.yml` | 模板变量、默认值、choices 和 `_subdirectory` | `copier` |
| 编排层 | `src/seed/` | `new` 负责渲染和建仓；`status` 负责只读漂移审计 | `seed` console script |

## 3. 模板结构

| 模板路径 | 渲染成 | 干什么 |
|---|---|---|
| `.copier-answers.yml.jinja` | `.copier-answers.yml` | 血缘锚：记录模板源、模板 ref 和回答 |
| `pyproject.toml.jinja` | `pyproject.toml` | 项目元数据、依赖组、poe tasks、ruff、pytest、coverage 配置 |
| `.github/workflows/ci.yml.jinja` | `.github/workflows/ci.yml` | 公开自包含 CI：checkout、setup-uv、`uv sync --locked`、`uv run poe check` |
| `.pre-commit-config.yaml.jinja` | `.pre-commit-config.yaml` | 本地 pre-commit：ruff check/format 和 uv-lock |
| `README.md.jinja` | `README.md` | 生成仓入口和开发命令 |
| `docs/INDEX.md.jinja` | `docs/INDEX.md` | 文档入口 |
| `docs/architecture.md.jinja` | `docs/architecture.md` | 生成仓开发地图骨架 |
| `src/{{package_name}}/config.py.jinja` | `src/<pkg>/config.py` | pydantic-settings 配置入口 |
| `src/{{package_name}}/logging_setup.py.jinja` | `src/<pkg>/logging_setup.py` | structlog 配置 |
| `src/{{package_name}}/{% if kind != 'lib' %}cli.py{% endif %}.jinja` | `src/<pkg>/cli.py` | Typer app 和 console-script 入口；仅 CLI |
| `src/{{package_name}}/{% if kind != 'lib' %}telemetry.py{% endif %}.jinja` | `src/<pkg>/telemetry.py` | 本地 SQLite 调用账本；仅 CLI |
| `tests/*.jinja` | `tests/` | config、CLI 和 telemetry 测试 |
| `Dockerfile` 条件模板 | `Dockerfile` | 非 lib 仓可选容器入口 |

核心变量在 `copier.yml`：`project_name`、`package_name`、`description`、`author`、`kind`、`cli_command`、`python_min`、`publish`、`license`。

## 4. CLI codemap

| 符号 | 职责 |
|---|---|
| `seed.cli:app` | Typer 根入口 |
| `_template_source()` | 解析模板源：`PY_PROJECT_TEMPLATE` 优先，否则用包内捆绑模板 |
| `new(...)` | 调 Copier 渲染一次，按需 `uv sync`，再 `git init/add/commit` |
| `status(root)` | 扫描 root 下的 seed-born 仓，输出 PASS/DRIFT |
| `audit_repo(repo)` | 对一个仓跑全部审计维度 |
| `find_seed_repos(root)` | 发现直接子目录中的 `.copier-answers.yml` |

## 5. status 审计维度

| 维度 | 判什么 |
|---|---|
| `ci` | `ci.yml` 是公开自包含 CI，且不继承 secrets、不依赖组织级 reusable workflow |
| `tool-tasks` | poe tasks 使用固定的 ruff 和 pyrefly 公开命令 |
| `python-version` | `.python-version`、`requires-python` 下限、ruff target-version 三者一致 |
| `tool-deps` | `ruff` / `pyrefly` 未进入 dev-deps |
| `pre-commit` | 有 `.pre-commit-config.yaml` |
| `build` | `build-backend == uv_build` 且有 `[tool.poe.tasks]` |
| `dependabot` | 有 `.github/dependabot.yml` |
| `lineage` | 有 `.copier-answers.yml` |
| `docs` | 有 `docs/INDEX.md` 和 `docs/architecture.md` |

## 6. 核心不变量

1. **一次性脚手架，不回灌**：`seed new` 只给一致起点，不把模板后续变更推回老仓。
2. **质量门统一入口**：生成仓默认以 `uv run poe check` 为本地和 CI 的一致检查入口。
3. **CI 自包含**：生成仓 CI 不继承 secret，不依赖私有组织 workflow。
4. **工具不进 dev-deps**：ruff/pyrefly 按需拉取，生成仓虚拟环境保持轻量。
5. **血缘可查**：`.copier-answers.yml` 只作识别和审计，不作自动更新锚点。
6. **文档域最小可用**：生成仓默认有 `docs/INDEX.md` 和 `docs/architecture.md`，但业务化后应按真实模块维护。

## 7. 关键流程

### `seed new mytool --kind cli`

1. `_template_source()` 找模板源。
2. Copier 根据回答渲染 `src/seed/_template/template/`。
3. 默认执行 `uv sync`。
4. 初始化 git 仓，提交 `chore: scaffold from seed`。
5. 生成仓可直接运行 `uv run poe check`。

### `seed status [root]`

1. 找 root 直接子目录下含 `.copier-answers.yml` 的仓。
2. 对每个仓跑 9 个审计维度。
3. 输出 `PASS` 或 `DRIFT`。
4. 有 DRIFT 时 exit 1。

## 8. 改 X 去哪

| 想改什么 | 改哪里 |
|---|---|
| 改生成仓初始文件 | `src/seed/_template/template/` 下对应 `*.jinja` |
| 加/改模板变量 | `src/seed/_template/copier.yml` 和使用它的模板文件 |
| 改 seed CLI 命令 | `src/seed/cli.py` 和 `tests/test_cli.py` |
| 改漂移审计 | `src/seed/audit.py` 和测试 |
| 改生成仓检查命令 | 模板 `pyproject.toml.jinja`，并同步 `audit.py` |
| 改本仓 CI | `.github/workflows/ci.yml` 或 `.github/workflows/template-ci.yml` |
| 改生成仓默认文档 | 模板 `docs/*.jinja` |

## 9. 非目标

- 不回灌模板。
- 不重造 Copier 的渲染能力。
- 不替生成仓修漂移。
- 不存本地私有流程或组织配置。
