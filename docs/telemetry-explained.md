---
description: "seed 生成 CLI 的本地 telemetry 运作解释:run_instrumented wrapper 如何记录调用账本、stats 如何聚合,以及 telemetry 与 structlog 的边界。"
keywords: [seed, telemetry, run_instrumented, invocation-ledger, stats, structlog, SQLite, CLI]
kind: reference
links: [telemetry-design, architecture]
---

# 概念阐释 — seed 生成的 CLI 里,用量遥测怎么运作

> 体裁:explanation(理解导向)。受众:用 seed 生成了 CLI、想搞懂自带的那套 telemetry 怎么转的人。
> 本篇只讲**怎么运作 + 为什么这么设计**。要**为什么选 SQLite 而非别的**看 `telemetry-design.md`;要**怎么用某个命令**看生成仓 `docs/cli-features.md` 一类的 runbook。

## 这篇讲什么 / 不讲什么

讲清:一次 CLI 调用是怎么变成账本里一行的、`stats` 怎么把这些行变成 per-verb 统计、以及为什么是这个形状。不讲选型论证(在 design doc),不讲逐命令操作(在 runbook)。

## 两个容易混的层:诊断日志 vs 用量账本

模版给非-lib 仓装了**两层正交的观测**,别混:

- **structlog(诊断日志)** —— 程序运行中从代码各处发出的事件(debug/info/warn),用来排查「这次跑为什么这样」。一次运行可能很多条。
- **telemetry(用量账本)** —— 每次**调用**记**一行**(verb、耗时、exit、输出量、stderr 样本…),用来回答「这个工具被怎么用、哪里慢、哪里反复错」。一次运行恰好一行。

它们不是一个替另一个:structlog 是 event 级的诊断,telemetry 是 invocation 级的账本。本篇只讲后者。

## 核心抽象

- **invocation ledger(调用账本)** —— 一张 SQLite 表 `calls`,一行 = 一次 CLI 调用。它不是程序日志,是「谁、何时、跑了哪个 verb、多久、成没成」的结构化流水。
- **wrapper(`run_instrumented`)** —— 套在命令分发外面的一层,负责观测每次调用而命令本身无感知。
- **best-effort** —— 遥测的任何失败都被吞掉,绝不改变主命令的输出或 exit code。账本是配角,命令是主角。

## 主线:一次调用怎么变成账本里一行

跟着一条调用走一遍(这是整套的命门,记住这条线就懂了八成):

1. console-script 入口是 `cli:run`(不是裸 `app`)。`run()` 调 `run_instrumented(app, sys.argv[1:])`。
2. wrapper 先把 `sys.stdout/sys.stderr` 换成两个 **Tee** —— Tee 透传写到真流,同时数总字节、留头部样本。于是命令照常输出,wrapper 顺便看见了输出规模。
3. wrapper 以 `standalone_mode=True` 跑 click 命令。这一步把「退出语义」整个交给 click:成功 `SystemExit(0)`、用法错 `SystemExit(2)`、abort `SystemExit(1)`,错误信息 click 自己印到 stderr。wrapper 只 `except SystemExit` 取 code,外加 `except Exception` 兜住命令体里的意外异常(印一行 `error:`、exit 1、绝不甩 traceback)。
4. 命令跑完,wrapper 组一个 record(verb、args、exit_code、duration_ms、out_bytes、stdout/stderr 样本、cwd、version、is_tty、is_ci、meta),调 `record()`。
5. `record()` 开一个 WAL 模式的 SQLite 连接(`busy_timeout=5000` + `BEGIN IMMEDIATE`),`INSERT` 一行,关连接。全程包在 try 里——写不进去就静默放弃(best-effort)。
6. 之后 `<cli> stats` 反过来:`SELECT` 出轻量列做 per-verb 聚合(count、error-rate 走 SQL),把 duration 列拉回内存用纯 Python `sorted` 取 p50/p95,再单独小查询拉最近几条出错行做「recent errors」。

`verb` 怎么定的:取 argv 里**首个不以 `-` 开头**的 token(于是 `tool --verbose sync` 也能认出 `sync`)。这是启发式,不是从 click 解析结果回填——所以 flag 的**值**夹在子命令前会被误当 verb,是已知的边界。

## 为什么是这个形状(why,不只 what)

- **为什么 wrapper 用 `standalone_mode=True`** —— 让 click 拥有退出语义,wrapper 就只剩「捕 SystemExit + 兜意外」两件事,不必去 catch 各种 click 异常类型。这躲开了一个真坑:typer 自带 vendored click(`typer._click`),它抛的异常和你 `import click` 的不是同一个类,手动 catch 会全部漏掉、把正常调用误记成 error。交给 click 自己处理就没这问题。
- **为什么 best-effort 是硬约束** —— 观测绝不能伤害被观测对象。Tee 的记账、`record` 的落盘、`stats` 的读,任一出错都返回/吞掉而非抛,确保主命令的 exit code 和输出一字不变。
- **为什么 SQLite 而非追加 jsonl** —— 多个短命进程并发写,WAL + busy_timeout 让它们排队而非互相撕裂或丢写;聚合走 SQL 不必全量扫文件。(更细的论证见 design doc。)
- **为什么账本默认在用户数据目录而非项目里** —— 用量是「这个工具被这个人怎么用」,跨项目是同一回事;放在用户数据目录既不污染任何代码/数据仓,又让同一工具的所有调用汇到一处。

## 对比相邻设计(划边界)

- **telemetry vs structlog** —— 见开头那张:一个是 invocation 账本(为聚合而生),一个是 event 诊断日志(为排查而生)。同一个 CLI 两层都有,各管各。
- **SQLite 账本 vs 一堆原始日志行** —— 账本是 schema 化、为聚合查询而设的;它不是给人逐行读的(那是 structlog 的事),是给 `stats` 聚合、给你看趋势的。

## 一点判断(承认视角)

这套的代价是账本无限增长且 `verb` 启发式不完美 —— 这是有意的取舍:为了 stdlib-only + 零配置 + best-effort,放弃了轮转机制和从 click ctx 精确回填 verb。对「个人/小团队工具的用量趋势」这个用途,这个取舍偏向了简单和零依赖,我认为是对的;若哪天要把它当审计级账目用,就得重估。
