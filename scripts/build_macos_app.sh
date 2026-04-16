#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_PYTHON="${ROOT_DIR}/.venv311/bin/python"
CACHE_DIR="${ROOT_DIR}/.build-cache"
ICNS_FILE="${ROOT_DIR}/assets/HandTrackerAI.icns"

if [[ ! -x "${VENV_PYTHON}" ]]; then
  echo "Python not found at ${VENV_PYTHON}"
  echo "Create the virtual environment first or adjust the script to your Python path."
  exit 1
fi

cd "${ROOT_DIR}"
mkdir -p "${CACHE_DIR}/pyinstaller" "${CACHE_DIR}/matplotlib" "${CACHE_DIR}/fontconfig"

export PYINSTALLER_CONFIG_DIR="${CACHE_DIR}/pyinstaller"
export MPLCONFIGDIR="${CACHE_DIR}/matplotlib"
export XDG_CACHE_HOME="${CACHE_DIR}"

"${VENV_PYTHON}" tools/generate_app_icon.py
if [[ ! -f "${ICNS_FILE}" ]]; then
  echo "Failed to generate ${ICNS_FILE}"
  exit 1
fi
"${VENV_PYTHON}" -m PyInstaller --noconfirm HandTrackerAI.spec

echo
echo "Build complete:"
echo "  ${ROOT_DIR}/dist/HandTrackerAI.app"
