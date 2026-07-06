"""seed-born 仓的漂移审计。

纯只读: 直接读文件 + 比对 seed 当前公开栈口径, 不做 copier re-render。
权威值是模板约定的快照: 自包含 CI、ruff/typecheck/build 任务和基础文档口径。
仓偏离即 DRIFT, 供 `seed status` CI gate 用。

每个维度一个 `_check_*(repo, pyproject) -> (ok, detail)` 纯函数; `audit_repo` 只编排。
"""

from __future__ import annotations

import re
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

import yaml

# ── 权威值 (与 src/seed/_template/template/ 同步) ────────────────────────
# 改栈口径在此处改, status 据此判仓是否落后。

CI_REQUIRED_SNIPPETS: tuple[str, ...] = (
    "actions/checkout",
    "astral-sh/setup-uv",
    "uv sync --locked",
    "uv run poe check",
)
INHERIT_ALL_MARKER = "secret" + "s: inherit"

# 这两个原生工具用 uvx / uv run --with 拉取, 不进每仓 dev-deps。
TOOL_FORBIDDEN_DEV_DEPS: frozenset[str] = frozenset({"ruff", "pyrefly"})
RUFF_VERSION = "0.15.16"
PYREFLY_VERSION = "1.0.0"

BUILD_BACKEND = "uv_build"

DEP_NAME_RE = re.compile(r"^[A-Za-z0-9._-]+")
PY_VER_RE = re.compile(r"(\d+\.\d+)")


@dataclass
class RepoAudit:
    """一个 seed-born 仓的审计结果: 每个维度一条 (name, ok, detail)。"""

    name: str
    checks: list[tuple[str, bool, str]] = field(default_factory=list)

    def add(self, dim: str, result: tuple[bool, str]) -> None:
        ok, detail = result
        self.checks.append((dim, ok, detail))

    @property
    def drift(self) -> bool:
        return any(not ok for _, ok, _ in self.checks)


def _load_toml(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError):
        return {}


def _load_yaml(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError):
        return {}


def _dep_names(deps: list) -> set[str]:
    """从 dependency 规格列表抽包名 (去版本约束 / extras)。"""
    names = set()
    for spec in deps:
        if not isinstance(spec, str):
            continue
        m = DEP_NAME_RE.match(spec.strip())
        if m:
            names.add(m.group(0).lower().replace("_", "-"))
    return names


def _python_floor(requires_python: str) -> str | None:
    """从 requires-python (如 '>=3.12') 抽下限 '3.12'。"""
    m = PY_VER_RE.search(requires_python or "")
    return m.group(1) if m else None


def _ruff_target_dotted(target: str) -> str:
    """ruff target-version 'py312' -> '3.12'; 非 pyNNN 原样返回。"""
    norm = target[2:] if target.startswith("py") else target
    return f"{norm[0]}.{norm[1:]}" if norm.isdigit() else norm


# ── 维度检查 (各自纯函数, repo + 已解析 pyproject 入参) ──────────────────


def _check_ci(repo: Path, _pyproject: dict) -> tuple[bool, str]:
    ci = repo / ".github" / "workflows" / "ci.yml"
    if not ci.exists():
        return False, "ci.yml 缺失"
    text = ci.read_text(encoding="utf-8")
    if INHERIT_ALL_MARKER in text:
        return False, "ci.yml 不应继承调用方全部敏感值"
    if ".github/.github/workflows/" in text:
        return False, "ci.yml 不应依赖组织级私有 reusable workflow"
    missing = [snippet for snippet in CI_REQUIRED_SNIPPETS if snippet not in text]
    if missing:
        return False, "ci.yml 缺少公开自包含步骤: " + ", ".join(missing)
    return True, "公开自包含 CI"


def _check_tool_tasks(_repo: Path, pyproject: dict) -> tuple[bool, str]:
    tasks = pyproject.get("tool", {}).get("poe", {}).get("tasks", {})
    expected = {
        "lint": f"uvx ruff@{RUFF_VERSION} check .",
        "fmt": f"uvx ruff@{RUFF_VERSION} format .",
        "fmt-check": f"uvx ruff@{RUFF_VERSION} format --check .",
        "typecheck": f"uv run --with pyrefly=={PYREFLY_VERSION} pyrefly check",
    }
    wrong = [
        f"{name}={tasks.get(name)!r}"
        for name, command in expected.items()
        if tasks.get(name) != command
    ]
    if wrong:
        return False, "poe task 未对齐公开工具口径: " + "; ".join(wrong)
    return True, f"ruff {RUFF_VERSION} + pyrefly {PYREFLY_VERSION}"


def _check_python_version(repo: Path, pyproject: dict) -> tuple[bool, str]:
    ruff = pyproject.get("tool", {}).get("ruff", {})
    pyver_path = repo / ".python-version"
    pyver = (
        pyver_path.read_text(encoding="utf-8").strip() if pyver_path.exists() else None
    )
    floor = _python_floor(pyproject.get("project", {}).get("requires-python", ""))
    target = _ruff_target_dotted(ruff.get("target-version", ""))
    if pyver is None or floor is None or not target:
        return (
            False,
            f".python-version={pyver} requires-python floor={floor} ruff target={target or '?'}",
        )
    if len({pyver, floor, target}) != 1:
        return (
            False,
            f"不一致: .python-version={pyver} floor={floor} ruff-target={target}",
        )
    return True, f"全 = {pyver}"


def _check_tool_deps(_repo: Path, pyproject: dict) -> tuple[bool, str]:
    dev_deps = _dep_names(pyproject.get("dependency-groups", {}).get("dev", []))
    leaked = TOOL_FORBIDDEN_DEV_DEPS & dev_deps
    if leaked:
        return False, f"{sorted(leaked)} 漏进 dev-deps (应由任务命令按需拉取)"
    return True, "ruff/pyrefly 未入 dev-deps"


def _check_precommit(repo: Path, _pyproject: dict) -> tuple[bool, str]:
    ok = (repo / ".pre-commit-config.yaml").exists()
    return ok, "有" if ok else "缺 .pre-commit-config.yaml"


def _check_build(_repo: Path, pyproject: dict) -> tuple[bool, str]:
    backend = pyproject.get("build-system", {}).get("build-backend", "")
    if backend != BUILD_BACKEND:
        return False, f"build-backend={backend or '?'} (需 {BUILD_BACKEND})"
    if not pyproject.get("tool", {}).get("poe", {}).get("tasks"):
        return False, "缺 [tool.poe.tasks]"
    return True, f"{BUILD_BACKEND} + poe"


def _check_dependabot(repo: Path, _pyproject: dict) -> tuple[bool, str]:
    ok = (repo / ".github" / "dependabot.yml").exists()
    return ok, "有" if ok else "缺 .github/dependabot.yml"


def _check_lineage(repo: Path, _pyproject: dict) -> tuple[bool, str]:
    answers = _load_yaml(repo / ".copier-answers.yml")
    if not answers:
        return False, "缺 .copier-answers.yml"
    return True, f"_commit={answers.get('_commit')}"


def _check_docs(repo: Path, _pyproject: dict) -> tuple[bool, str]:
    docs = repo / "docs"
    missing = [n for n in ("INDEX.md", "architecture.md") if not (docs / n).exists()]
    if missing:
        return False, "缺 docs/" + ", docs/".join(missing)
    return True, "INDEX + architecture"


# 维度顺序 = status 报告顺序。
_CHECKS: list[tuple[str, object]] = [
    ("ci", _check_ci),
    ("tool-tasks", _check_tool_tasks),
    ("python-version", _check_python_version),
    ("tool-deps", _check_tool_deps),
    ("pre-commit", _check_precommit),
    ("build", _check_build),
    ("dependabot", _check_dependabot),
    ("lineage", _check_lineage),
    ("docs", _check_docs),
]


def audit_repo(repo: Path) -> RepoAudit:
    """对一个 seed-born 仓跑全部维度的只读审计。"""
    pyproject = _load_toml(repo / "pyproject.toml")
    result = RepoAudit(name=repo.name)
    for dim, check in _CHECKS:
        result.add(dim, check(repo, pyproject))
    return result


def find_seed_repos(root: Path) -> list[Path]:
    """root 下含 .copier-answers.yml 的直接子目录 (= seed-born 仓)。"""
    return sorted(
        d for d in root.iterdir() if d.is_dir() and (d / ".copier-answers.yml").exists()
    )
