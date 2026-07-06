from __future__ import annotations

import textwrap
from pathlib import Path

import pytest
from typer.testing import CliRunner

from seed.audit import audit_repo
from seed.cli import app

runner = CliRunner()


def test_help() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0


def test_dropped_commands_gone() -> None:
    # update / doctor 回灌已废; ruff helper 也不再绑定私有上游配置。
    for verb in ("update", "doctor", "ruff"):
        result = runner.invoke(app, [verb, "--help"])
        assert result.exit_code != 0


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(content), encoding="utf-8")


def _make_clean_repo(parent: Path, name: str) -> Path:
    """一个所有维度都 PASS 的 seed-born 仓。"""
    repo = parent / name
    _write(
        repo / "pyproject.toml",
        f"""
        [build-system]
        requires = ["uv_build>=0.11"]
        build-backend = "uv_build"

        [project]
        name = "{name}"
        requires-python = ">=3.12"

        [dependency-groups]
        dev = ["pytest>=8.0", "poethepoet"]

        [tool.poe.tasks]
        lint = "uvx ruff@0.15.16 check ."
        fmt = "uvx ruff@0.15.16 format ."
        fmt-check = "uvx ruff@0.15.16 format --check ."
        typecheck = "uv run --with pyrefly==1.0.0 pyrefly check"
        test = "pytest"

        [tool.ruff]
        target-version = "py312"
        """,
    )
    _write(repo / ".python-version", "3.12\n")
    _write(
        repo / ".github" / "workflows" / "ci.yml",
        """
        name: CI
        on: [push, pull_request]
        jobs:
          ci:
            runs-on: ubuntu-latest
            steps:
              - uses: actions/checkout@v5
              - uses: astral-sh/setup-uv@v8.2.0
              - run: uv sync --locked
              - run: uv run poe check
        """,
    )
    _write(repo / ".pre-commit-config.yaml", "repos: []\n")
    _write(repo / ".github" / "dependabot.yml", "version: 2\n")
    _write(repo / ".copier-answers.yml", "_commit: v0.1.0\n_src_path: seed\n")
    _write(repo / "docs" / "INDEX.md", "# index\n")
    _write(repo / "docs" / "architecture.md", "# arch\n")
    return repo


def _make_drifted_repo(parent: Path, name: str) -> Path:
    """多维度故意漂移: 旧 CI 版本, dev-deps 漏 ruff, 无 dependabot/docs。"""
    repo = parent / name
    _write(
        repo / "pyproject.toml",
        f"""
        [build-system]
        requires = ["hatchling"]
        build-backend = "hatchling.build"

        [project]
        name = "{name}"
        requires-python = ">=3.13"

        [dependency-groups]
        dev = ["pytest", "ruff>=0.15", "poethepoet"]

        [tool.poe.tasks]
        lint = "ruff check ."
        fmt = "ruff format ."
        fmt-check = "ruff format --check ."
        typecheck = "pyrefly check"
        test = "pytest"

        [tool.ruff]
        target-version = "py312"
        """,
    )
    _write(repo / ".python-version", "3.12\n")
    _write(
        repo / ".github" / "workflows" / "ci.yml",
        """
        name: CI
        jobs:
          ci:
            runs-on: ubuntu-latest
            steps:
              - run: pytest
        """,
    )
    _write(repo / ".copier-answers.yml", "_commit: v0.0.1\n")
    return repo


def test_audit_clean_repo_passes(tmp_path: Path) -> None:
    repo = _make_clean_repo(tmp_path, "clean-tool")
    result = audit_repo(repo)
    failed = [(d, detail) for d, ok, detail in result.checks if not ok]
    assert not result.drift, f"unexpected drift: {failed}"
    assert len(result.checks) == 9


def test_audit_drifted_repo_flags_each_dimension(tmp_path: Path) -> None:
    repo = _make_drifted_repo(tmp_path, "drifted-tool")
    result = audit_repo(repo)
    assert result.drift
    failed = {dim for dim, ok, _ in result.checks if not ok}
    # CI 不完整, 工具任务不一致, python 不一致, dev-deps 漏 ruff, 无 pre-commit, hatchling build, 无 dependabot, 无 docs
    for dim in (
        "ci",
        "tool-tasks",
        "python-version",
        "tool-deps",
        "pre-commit",
        "build",
        "dependabot",
        "docs",
    ):
        assert dim in failed, f"expected {dim} to be flagged, failed={failed}"
    # lineage 仍 PASS (.copier-answers.yml 在)
    lineage_ok = next(ok for dim, ok, _ in result.checks if dim == "lineage")
    assert lineage_ok


def test_status_pass_exit_zero(tmp_path: Path) -> None:
    _make_clean_repo(tmp_path, "clean-tool")
    result = runner.invoke(app, ["status", str(tmp_path)])
    assert result.exit_code == 0
    assert "PASS   clean-tool" in result.stdout
    assert "0 DRIFT" in result.stdout
    # 没有任何仓被标 DRIFT (只有 summary 那行带 "DRIFT" 字样)
    assert not any(line.startswith("DRIFT") for line in result.stdout.splitlines())


def test_status_drift_exit_nonzero(tmp_path: Path) -> None:
    _make_clean_repo(tmp_path, "clean-tool")
    _make_drifted_repo(tmp_path, "drifted-tool")
    result = runner.invoke(app, ["status", str(tmp_path)])
    assert result.exit_code == 1
    assert "DRIFT" in result.stdout
    assert "drifted-tool" in result.stdout
    assert "1 DRIFT" in result.stdout


def test_status_no_repos(tmp_path: Path) -> None:
    result = runner.invoke(app, ["status", str(tmp_path)])
    assert result.exit_code == 0
    assert "未发现" in result.stdout


def test_new_rejects_unknown_kind(tmp_path: Path) -> None:
    result = runner.invoke(
        app,
        ["new", "unknown-kind", "--kind", "worker", "--dest", str(tmp_path)],
    )
    assert result.exit_code != 0
    assert "kind must be one of" in result.output


# ---------------------------------------------------------------------------
# _template_source() bug regression: must not return a dir without copier.yml
# ---------------------------------------------------------------------------


def test_template_source_bundled_copier_yml_exists() -> None:
    """Bundled _template inside the package must contain copier.yml.

    Verifies the package-data layout that makes `uv tool install` work:
    Path(__file__).parent / '_template' / 'copier.yml' must exist whether
    the package is used as an editable source install or a wheel install.
    """
    import seed.cli as cli_module

    bundled = Path(cli_module.__file__).parent / "_template"  # type: ignore[arg-type]
    assert bundled.is_dir(), f"bundled template dir missing: {bundled}"
    assert (bundled / "copier.yml").exists(), (
        f"copier.yml not found in bundled template: {bundled}"
    )
    assert (bundled / "template").is_dir(), (
        f"template/ subdirectory missing in bundled template: {bundled}"
    )


def test_template_source_returns_dir_with_copier_yml(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """_template_source() must always return a path that contains copier.yml.

    Regression for the site-packages bug: parents[2] from an installed
    cli.py points to python3.x/, not the template root, causing copier to
    scaffold only a site-packages directory instead of the real template.
    """
    monkeypatch.delenv("PY_PROJECT_TEMPLATE", raising=False)
    from seed.cli import _template_source

    src = _template_source()
    assert Path(src, "copier.yml").exists(), (
        f"_template_source() returned {src!r} which has no copier.yml — "
        "this is the site-packages regression"
    )
