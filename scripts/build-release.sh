#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUTPUT_DIR="${1:-${ROOT}/dist/release}"
BUILD_DIR="${SEED_BUILD_DIR:-${ROOT}/build/pyinstaller}"
export PYINSTALLER_CONFIG_DIR="${PYINSTALLER_CONFIG_DIR:-${BUILD_DIR}/cache}"
case "$(uname -s)" in Darwin) platform=darwin ;; Linux) platform=linux ;; *) exit 2 ;; esac
case "$(uname -m)" in arm64|aarch64) arch=arm64 ;; x86_64|amd64) arch=x86_64 ;; *) exit 2 ;; esac
mkdir -p "${OUTPUT_DIR}" "${BUILD_DIR}/dist" "${BUILD_DIR}/work" "${BUILD_DIR}/spec" "${PYINSTALLER_CONFIG_DIR}"
uv run --group freeze pyinstaller --noconfirm --onedir --clean \
  --paths "${ROOT}/src" --collect-all seed --collect-all jinja2_ansible_filters \
  --name seed --distpath "${BUILD_DIR}/dist" \
  --workpath "${BUILD_DIR}/work/seed" --specpath "${BUILD_DIR}/spec" \
  "${ROOT}/scripts/seed_entry.py"
tar -C "${BUILD_DIR}/dist" -czf "${OUTPUT_DIR}/seed-${platform}-${arch}.tar.gz" seed
if [[ "${SKIP_SMOKE:-0}" != "1" ]]; then
  smoke_root="$(mktemp -d)"
  CI=1 XDG_DATA_HOME="${smoke_root}/data" XDG_CACHE_HOME="${smoke_root}/cache" \
    GIT_AUTHOR_NAME=seed-smoke GIT_AUTHOR_EMAIL=seed-smoke@example.invalid \
    GIT_COMMITTER_NAME=seed-smoke GIT_COMMITTER_EMAIL=seed-smoke@example.invalid \
    "${BUILD_DIR}/dist/seed/seed" new smoke-cli --dest "${smoke_root}" --no-sync >/dev/null
  test -f "${smoke_root}/smoke-cli/pyproject.toml"
  git -C "${smoke_root}/smoke-cli" rev-parse --verify HEAD >/dev/null
  rm -rf "${smoke_root}"
fi
