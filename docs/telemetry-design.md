---
description: "seed 模版本地用量遥测设计决策:为生成的 CLI 仓内置 stdlib-only SQLite invocation ledger,并解释为何否决现成遥测库、OpenTelemetry 和 jsonl。"
keywords: [seed, telemetry, SQLite, invocation-ledger, design-doc, decision, OpenTelemetry, jsonl, stats]
kind: decision
links: [telemetry-explained, architecture]
---

# Design Doc — seed 模版的本地用量遥测能力

> 体裁:decision(design doc)。受众:维护 seed 的人、用它生成 CLI 的人、未来的你。
> 状态:已实现并随 v0.4.0 发布。配套:`telemetry-explained.md`(讲怎么运作)。

## TL;DR

seed 生成的每个 CLI 仓(`kind != lib`)自带一个 stdlib-only 的本地用量账本:每次调用记一行进 SQLite,`<cli> stats` 出 per-verb 调用次数 / p50·p95 耗时 / error-rate。**选定手搓 stdlib `sqlite3`,否决了所有现成遥测库、OpenTelemetry、以及 jsonl** —— 因为这套约束(纯本地零网络 + 多进程并发写 + 轻量 + 可嵌入 Copier 模版)下,市面无现成组件契合,而 SQLite(WAL)在并发安全和聚合查询上同时压过 jsonl,且零第三方依赖。

## 问题 → Context

小型 Python CLI 工具越来越多,但没有一致的方式回答「这个工具被怎么用」——哪个子命令高频、哪个慢、哪个反复报错。没有这层观测,工具改进靠拍脑袋。

目标:让 seed 生成的每个 CLI **白嫖**到用量观测,无需各仓自己搭。约束:

| 约束 | 含义 |
|---|---|
| 纯本地、零网络出口 | 个人/小团队工具,隐私 + 不依赖任何后端/服务 |
| 多进程并发写 | 多个 agent 进程可能同时调同一 CLI,落盘必须 append-safe |
| 轻量 | 打进每个小 CLI,不能臃肿、不能拖慢每次调用 |
| 可嵌入 Copier 模版 | 作为生成的小模块或薄依赖,不是要常驻运行的服务 |
| 要聚合 | 不只是原始日志,要 per-verb count / p50 / p95 / error-rate |

## 选项

认真考虑过五条路,从「买现成」到「全手搓」:

- **A. 现成遥测/分析库** — PostHog / Segment / Mixpanel / Rudderstack / `@vscode/extension-telemetry` / Dart `unified_analytics`。
- **B. OpenTelemetry** — 配纯本地 file/console exporter。
- **C. 通用日志库 + 自写聚合** — structlog / loguru / eliot 当 sink,聚合自己写。
- **D. 手搓 jsonl** — 每次 append 一行 JSON,`stats` 时全量扫聚合。
- **E. 手搓 stdlib SQLite**(选中)— WAL + busy_timeout,SQL 聚合 + 纯 Python percentile。

## 权衡(逐项横比)

下表在五个硬约束维度上横比五个选项(✅ 满足 / ⚠️ 勉强 / ❌ 不满足),选中项加粗:

| 维度 | A 遥测库 | B OpenTelemetry | C 日志库+自聚合 | D 手搓 jsonl | **E 手搓 SQLite** |
|---|---|---|---|---|---|
| 零网络 | ❌ 全部强制上报后端 | ⚠️ 可纯本地但非主路径 | ✅ | ✅ | ✅ |
| 聚合(p50/p95) | n/a(在后端) | ❌ histogram 本地算不出精确分位 | ❌ 库不带,得全自写 | ⚠️ 全量扫,量大线性劣化 | ✅ SQL 聚合 + 纯 Python 分位 |
| 多进程并发写安全 | n/a(后端负责) | ❌ 不解决,短命进程是反模式 | ❌ 库不保证 | ⚠️ 要 `os.write` 单 syscall 规避缓冲撕裂 | ✅ WAL + busy_timeout |
| 依赖重量 | 重(SDK + 网络栈) | 重(api+sdk+semconv,碰 OTLP 拖 grpcio) | 中(一个日志库) | 零(stdlib) | 零(stdlib `sqlite3`) |
| 嵌入 Copier 模版 | ❌ 需 API key/后端 | ❌ 一套 provider/exporter 仪式 | ⚠️ 多一个 runtime 依赖 | ✅ 一个文件 | ✅ 一个文件 |

判据细节见 Alternatives Considered;完整调研含 O_APPEND 原子性真相与 Atuin 先例分析。

## 决策

**选 E:手搓 stdlib SQLite 账本。** 具体形状:

- 存储 = 用户数据目录下的 `<pkg>/telemetry.db`(`$<PKG>_TELEMETRY_DB` 可改),WAL + `busy_timeout=5000` + `BEGIN IMMEDIATE`。
- 字段 = `verb / args / exit_code / duration_ms / out_bytes / stdout·stderr 样本 / cwd / version / is_tty / is_ci / meta`(字段集参考 gh/dotnet/ng 工业趋同集,但放开记 args/cwd/stderr —— 纯本地无隐私顾虑,这些是诊断金矿)。
- 包装器 = `run_instrumented(app)` 作为 console-script 入口,`standalone_mode=True` 让 click 自有退出语义,wrapper 只捕 stdout/stderr + exit code + 记一行。
- 聚合 = `stats` 命令,SQL 算 count/error,duration 列拉回纯 Python `sorted` 取 p50/p95。
- **适用 CLI kind**(`kind != lib`)。

## Consequences

**收益**:每个生成的 CLI 零配置获得用量观测,零第三方依赖、零网络、多进程安全;`stats` 直接驱动工具迭代。

**代价 / 后续约束**:
- 账本无限增长(一调用一行),需要时手删 `telemetry.db` 重置或 `DELETE FROM calls WHERE id < …`;未内建轮转。
- `verb` 取「首个非 `-` token」是启发式,flag 的**值**在子命令前会误判(如 `--config x sync` 取到 `x`)。
- schema 用 `CREATE IF NOT EXISTS` + `PRAGMA user_version=1` 作迁移锚;将来加列要走 ALTER,否则老 db 静默丢写。
- 消费仓若大改 telemetry,后续 `seed update` 会与本地改动三方合并产生冲突(可接受,copier 标记呈现)。
- `stats` 输出为英文格式(消费仓原有的本地化格式被统一掉)。

## Non-Goals

- **不是产品分析**(不追踪用户行为做增长)。
- **不做网络上报 / 远端可视化**(若将来要,写一次性 jsonl→OTLP 离线转换器,不进采集热路径)。
- **不覆盖 `lib` kind**(库无调用入口,invocation-ledger 模型不适用)。
- **不做审计级保证**(best-effort:高并发竞争下可能静默丢采样;它是观测不是账目)。

## Alternatives Considered

- **OpenTelemetry — 判 C(尺寸严重不匹配)**:分布式追踪的机器塞本地 CLI。metrics 信号本地存不下原始观测值,算不出精确 p95;官方无 file exporter;不解决多进程 append;短命进程 + BatchProcessor/atexit flush/SDK import 是纯税。连 Google Gemini CLI 本地模式都退化成「写一个 log 文件」绕开它。只借它的 semantic-convention 字段命名,不引依赖。
- **现成遥测库 — 全部强制网络上报**:没有一个提供「只本地、不出网」模式,违反零网络铁律。字段设计可抄,代码不可用。
- **jsonl(D)— 被 SQLite 压过**:O_APPEND 原子性其实与 PIPE_BUF 无关(常见误区);真正的坑是 Python `BufferedWriter`(默认 8192)把大记录拆成多 syscall 导致跨进程撕裂,要 `os.write` 单写规避。既然要碰存储层,SQLite 一并把并发、聚合性能、轮转管理解决更划算。先例 = Atuin(shell 历史,明确从纯文本换成 SQLite)。
- **DuckDB 做聚合 — 否**:`quantile_cont` 确实一句出 p95,但 +14.7MB wheel 换一个纯 Python 5 行就够的分位,投入产出不成正比。
- **telemetry 作为特殊工具形态差异化 — 否**:曾考虑只给少数 CLI,但最终定为所有 CLI 的 baseline。
