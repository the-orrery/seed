---
description: "seed 概览：解释 seed 作为 Python 仓一次性脚手架的设计心智、核心概念、new 生命周期，以及持续一致性如何由自包含 CI、固定工具任务和只读 status 审计维护。"
keywords: [seed, overview, Copier, 一次性脚手架, status, 漂移审计, Python模板]
kind: reference
links: [architecture, generated-repo-knowledge-contract]
---

# seed 概览

> 讲 seed 怎么运作、为什么这么设计。要跑起来看 [README](../README.md)；要改代码、看 codemap 与不变量清单看 [architecture](architecture.md)。

## 它解决什么

每个 Python 仓都要先搭一遍同样的地基：包管理、lint、类型检查、测试、CI、日志、配置。各仓各搭一遍，结果容易漂移：这个仓用一种 formatter，那个仓用另一种；这个仓 CI 跑三步，那个仓两步。

seed 把“搭地基”收成一件事：一个模板定义起点，一个 CLI 把模板渲染成新仓。它产出的不是某个业务工具，而是一组工具仓的一致起点。

## 一次性脚手架，不做回灌

seed 是渲染即脱离的脚手架：`seed new` 用一组答案渲染出一个一致的起点，从此这个仓自己长。业务代码、README、tests、docs 都归生成仓所有，模板不会再把后续变更强行合回老仓。

这样做的原因很简单：真实仓很快会修改模板种下的业务骨架，持续回灌会变成冲突机器。对会被业务改写的文件，给好起点就放手；对不会被业务改写的工程口径，用固定任务和审计维持一致。

## 持续一致性靠什么

seed 靠三件事维持一致性：

- **模板初值**：`pyproject.toml`、CI、pre-commit、README、docs、config、logging 和测试骨架一次性生成。
- **固定任务入口**：生成仓默认用 `uv run poe check` 串联 lint、format check、typecheck 和 test。
- **只读审计**：`seed status <root>` 扫描 seed-born 仓，检查 CI、工具任务、Python 版本、依赖、文档骨架等是否偏离当前公开栈口径。

`seed status` 只检测，不代修。漂了以后怎么改，是每个仓自己的提交。

## 关键概念

**渲染不是 init。** seed 不是拷贝一个固定目录，而是拿仓名、包名、形态、Python 版本、license 等答案渲染模板。同一个模板可以产出 CLI 或库。

**`.copier-answers.yml` 是血缘锚。** 它记录“这个仓由哪个模板源、带哪些答案生成”。现在它只用于让 `seed status` 认出 seed-born 仓，不驱动回灌。

**选定栈是一份清单。** uv、uv_build、ruff、pyrefly、pytest、Copier、poethepoet、pydantic-settings、structlog 和 src layout 是默认工程口径。换栈应改模板和审计逻辑，而不是让单个生成仓静默漂移。

**ruff/pyrefly 不进 dev-deps。** 这两个带原生二进制的工具通过 `uvx` 或 `uv run --with` 按需运行，避免每个仓的 `.venv` 都重复安装一份。

## 生命周期

1. **new**：回答几个问题，渲染出新仓，建好环境，留下首个 commit。
2. **自己长**：生成仓按自己的业务演进，模板不回灌。
3. **status 巡检**：想知道一批仓有没有工程口径漂移，跑 `seed status`；有 DRIFT 就非零退出，可挂在 CI 或本地 gate。

## 边界

- seed 不回灌模板。
- seed 不替生成仓修漂移。
- seed 不替生成仓做业务决定。
- seed 的文档只描述公开工程口径，不承载本地私有流程或组织配置。
