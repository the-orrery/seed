---
description: "seed 文档索引:模版仓的 architecture、生成仓文档契约与设计说明。"
keywords: [seed, 模版仓, Copier, 脚手架, architecture, generated-repo-contract]
kind: index
---

# seed docs

这里放 seed(uv-native Python 模版仓 + 脚手架 CLI)自己的文档。`src/seed/`(CLI 源码)、`template/`(Copier 模版工件)、`copier.yml`(模版变量)是代码/工件，不属于本域。

当前入口:

- [[overview]]:解释 seed 为什么是「模版 + 持续同步通道」、核心概念、生命周期和边界。
- [[architecture]]:模版仓是什么、模版结构 codemap、CLI 怎么工作、核心不变量(一次性不回灌 / 自包含 CI / 固定工具任务 / 选定栈)、`new` 流程、`status` 漂移审计、改 X 去哪。
- [[generated-repo-knowledge-contract]]:生成仓文档契约；每个 seed 生成仓默认带 `docs/INDEX.md` 和 `docs/architecture.md`，作为最小文档骨架。
- [[telemetry-design]]:模版自带本地用量遥测能力的设计决策。
- [[telemetry-explained]]:解释生成 CLI 里的 telemetry wrapper、调用账本和 `stats` 聚合如何运作。
