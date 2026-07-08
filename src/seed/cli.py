from __future__ import annotations

import os
import subprocess
from pathlib import Path

import typer
from orrery_heartbeat import check_update

from seed.audit import audit_repo, find_seed_repos

app = typer.Typer(
    no_args_is_help=True,
    add_completion=False,
    help="一次性 Python 仓脚手架 (Copier 渲染 + uv 建环境) + 只读漂移审计。",
)


@app.callback(invoke_without_command=True)
def _callback(ctx: typer.Context) -> None:
    check_update("seed", "the-orrery/seed")
    if ctx.invoked_subcommand is None:
        raise typer.Exit


KINDS = {"cli", "lib"}


def _template_source() -> str:
    """模版源: 优先 PY_PROJECT_TEMPLATE env (git URL/路径), 否则用包内捆绑模版。

    捆绑路径 (src/seed/_template/) 在 source-tree editable 安装和
    uv tool install 两种场景下均正确, 不再依赖 parents[N] 向上猜测仓根。
    """
    env = os.environ.get("PY_PROJECT_TEMPLATE")
    if env:
        return env
    return str(Path(__file__).parent / "_template")


@app.command()
def new(
    name: str = typer.Argument(..., help="新仓名 (kebab-case)"),
    kind: str = typer.Option("cli", help="cli | lib"),
    dest: Path = typer.Option(None, help="目标父目录, 默认当前目录 (生成 ./<name>)"),
    template: str = typer.Option(None, help="模版源 (路径或 git URL), 默认本仓"),
    publish: bool = typer.Option(False, help="发布到公网 PyPI"),
    license: str = typer.Option("MIT", help="许可证: MIT | Proprietary"),
    no_sync: bool = typer.Option(False, help="跳过 uv sync"),
) -> None:
    """从模版生成新仓 → uv sync → git init+commit (一次性, 不回灌)。"""
    from copier import run_copy

    if kind not in KINDS:
        allowed = ", ".join(sorted(KINDS))
        raise typer.BadParameter(f"kind must be one of: {allowed}")

    src = template or _template_source()
    target = ((dest or Path.cwd()) / name).resolve()
    run_copy(
        src,
        str(target),
        data={
            "project_name": name,
            "kind": kind,
            "publish": publish,
            "license": license,
        },
        defaults=True,
        unsafe=True,
    )
    if not no_sync:
        subprocess.run(["uv", "sync"], cwd=target, check=True)
    subprocess.run(["git", "init", "-q"], cwd=target, check=True)
    subprocess.run(["git", "add", "-A"], cwd=target, check=True)
    subprocess.run(
        ["git", "commit", "-qm", "chore: scaffold from seed"],
        cwd=target,
        check=True,
    )
    typer.echo(f"✓ {name} 已生成于 {target}")


@app.command()
def status(
    root: Path = typer.Argument(None, help="扫描的工作区根, 默认当前目录"),
) -> None:
    """只读审计: root 下每个 seed-born 仓相对 seed 当前公开栈的漂移。

    无回灌。报 PASS/DRIFT, 有 DRIFT 即非零退出 (CI gate)。
    """
    base = (root or Path.cwd()).resolve()
    repos = find_seed_repos(base)
    if not repos:
        typer.echo(f"未发现 seed-born 仓 (无 .copier-answers.yml) 于 {base}")
        return

    drifted = 0
    for repo in repos:
        result = audit_repo(repo)
        if result.drift:
            drifted += 1
            typer.echo(f"DRIFT  {result.name}")
            for dim, ok, detail in result.checks:
                mark = "ok " if ok else "✗  "
                typer.echo(f"       {mark}{dim:14} {detail}")
        else:
            lineage = next((d for n, _, d in result.checks if n == "lineage"), "")
            typer.echo(f"PASS   {result.name:30} {lineage}")

    total = len(repos)
    typer.echo(f"\n{total - drifted}/{total} PASS, {drifted} DRIFT")
    if drifted:
        raise typer.Exit(1)


if __name__ == "__main__":
    app()
