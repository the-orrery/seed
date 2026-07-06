---
description: "seed 生成仓文档契约：每个生成仓默认带最小文档骨架，维护 INDEX 与 architecture，spec/contract 按真实约束增量补。"
keywords: [seed, generated-repo, docs, architecture, contract, template]
kind: spec
links: [architecture]
code: [template/docs/INDEX.md.jinja, template/docs/architecture.md.jinja]
---

# generated repo knowledge contract

## 状态

- 状态：draft
- 生效范围：seed 模板生成的 `cli`、`lib` 仓。
- 关联实现：`template/docs/INDEX.md.jinja`、`template/docs/architecture.md.jinja`

## 术语

| 术语 | 定义 |
|---|---|
| generated repo | 通过 `seed new` 一次性生成、此后自行演进的仓（无回灌；漂移由 `seed status` 只读审计检测）。 |
| docs domain | 有 `INDEX.md` 的耐用 Markdown 目录，作为仓的文档入口。 |
| architecture | `docs/architecture.md`，面向新 contributor 的开发地图，属于 reference 体裁。 |
| repo-specific contract | 具体仓稳定约束的 spec/contract，例如输出协议、source-of-truth、数据 schema。 |

## 条款

| 条款 | 强制等级 | 约束 | 校验点 |
|---|---|---|---|
| C1 | MUST | 每个 generated repo 默认必须包含 `docs/INDEX.md`。 | 模板渲染测试。 |
| C2 | MUST | 每个 generated repo 默认必须包含 `docs/architecture.md`，作为新 contributor 开发地图。 | 模板渲染测试、人工 review。 |
| C3 | MUST | 模板生成的 architecture 只能写模板已知事实，不得伪造具体业务模块、接口或领域语义。 | 模板 review。 |
| C4 | SHOULD | 仓库业务化后，应按真实模块和不变量维护 `docs/architecture.md`，不要长期保留纯模板骨架。 | PR review。 |
| C5 | SHOULD | 稳定约束出现时，应新增 `*-contract.md` 或 `*-spec.md`，`kind: spec`；不要把 MUST/SHOULD 条款塞进 architecture。 | PR review。 |
| C6 | MUST NOT | raw log、cache、运行态数据库、secret、lockfile、源码和测试不得直接伪装成文档。 | PR review。 |
| C8 | MUST | seed 模板新增文档骨架后，render matrix 必须仍能通过生成仓 lint/type/test。 | `uv run poe check`、模板渲染 smoke。 |

## 执行点

- 模板层：`template/docs/INDEX.md.jinja` 和 `template/docs/architecture.md.jinja` 是生成仓最小文档包。
- 工程层：`template-ci` 的 render matrix 会验证生成仓仍能通过 Python 工程检查。
