#!/usr/bin/env bash
set -euo pipefail

LLMINATOR_SOURCE_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
LLMINATOR_INSTALL_ROOT="${LLMINATOR_INSTALL_ROOT:-${HOME}/.local/share/llminator}"
LLMINATOR_BIN_DIR="${LLMINATOR_BIN_DIR:-${HOME}/.local/bin}"
LLMINATOR_PROFILE="core"
LLMINATOR_UI="false"
LLMINATOR_PYTHON="${LLMINATOR_PYTHON:-}"

usage() {
  sed -n '/^# Usage:/,/^$/p' "$0" | sed 's/^# \?//'
}

# Usage:
#   ./install.sh                 Install the core CLI
#   ./install.sh --ml            Add ART, PyTorch, ONNX, and ONNX Runtime
#   ./install.sh --garak         Add isolated garak deep scanning
#   ./install.sh --full          Install ML and garak support
#   ./install.sh --ui            Add the ONNX Web UI (Flask browser interface)
#   ./install.sh --ml --ui       Combine ML support with the web UI
#   ./install.sh --prefix PATH   Choose a different installation directory
#   ./install.sh --python PATH   Use a specific Python 3.11/3.12 interpreter
#

while (($#)); do
  case "$1" in
    --core)  LLMINATOR_PROFILE="core" ;;
    --ml)    LLMINATOR_PROFILE="ml" ;;
    --garak) LLMINATOR_PROFILE="garak" ;;
    --full)  LLMINATOR_PROFILE="full" ;;
    --ui)    LLMINATOR_UI="true" ;;
    --prefix)
      shift
      if (($# == 0)); then
        echo "error: --prefix requires a path" >&2
        exit 2
      fi
      LLMINATOR_INSTALL_ROOT="$1"
      ;;
    --python)
      shift
      if (($# == 0)); then
        echo "error: --python requires an interpreter path" >&2
        exit 2
      fi
      LLMINATOR_PYTHON="$1"
      ;;
    --help|-h)
      usage
      exit 0
      ;;
    *)
      echo "error: unknown option: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
  shift
done

choose_python() {
  local candidate
  for candidate in python3.11 python3.12 python3; do
    if command -v "$candidate" >/dev/null 2>&1; then
      if "$candidate" -c 'import sys; raise SystemExit(not ((3, 11) <= sys.version_info[:2] <= (3, 12)))'; then
        command -v "$candidate"
        return
      fi
    fi
  done
  echo "error: Python 3.11 or 3.12 is required" >&2
  exit 1
}

if [[ -z "$LLMINATOR_PYTHON" ]]; then
  LLMINATOR_PYTHON="$(choose_python)"
fi
if [[ ! -x "$LLMINATOR_PYTHON" ]]; then
  echo "error: Python interpreter is not executable: $LLMINATOR_PYTHON" >&2
  exit 1
fi
if ! "$LLMINATOR_PYTHON" -c 'import sys; raise SystemExit(not ((3, 11) <= sys.version_info[:2] <= (3, 12)))'; then
  echo "error: --python must point to Python 3.11 or 3.12" >&2
  exit 1
fi
LLMINATOR_MAIN_VENV="${LLMINATOR_INSTALL_ROOT}/venv"
LLMINATOR_GARAK_VENV="${LLMINATOR_INSTALL_ROOT}/garak-venv"

mkdir -p "$LLMINATOR_INSTALL_ROOT" "$LLMINATOR_BIN_DIR"

create_venv() {
  local destination="$1"
  if command -v uv >/dev/null 2>&1; then
    uv venv --python "$LLMINATOR_PYTHON" "$destination"
  else
    "$LLMINATOR_PYTHON" -m venv "$destination"
  fi
}

install_package() {
  local environment="$1"
  shift
  if command -v uv >/dev/null 2>&1; then
    uv pip install --python "${environment}/bin/python" "$@"
  else
    "${environment}/bin/python" -m pip install --upgrade pip
    "${environment}/bin/python" -m pip install "$@"
  fi
}

echo "==> Installing LLMinator (${LLMINATOR_PROFILE})"
create_venv "$LLMINATOR_MAIN_VENV"

case "$LLMINATOR_PROFILE" in
  core|garak)
    install_package "$LLMINATOR_MAIN_VENV" "$LLMINATOR_SOURCE_DIR"
    ;;
  ml|full)
    install_package "$LLMINATOR_MAIN_VENV" "${LLMINATOR_SOURCE_DIR}[ml]"
    ;;
esac

if [[ "$LLMINATOR_UI" == "true" ]]; then
  echo "==> Installing ONNX Web UI (flask)"
  install_package "$LLMINATOR_MAIN_VENV" "${LLMINATOR_SOURCE_DIR}[ui]"
fi

if [[ "$LLMINATOR_PROFILE" == "garak" || "$LLMINATOR_PROFILE" == "full" ]]; then
  echo "==> Installing garak in a separate environment"
  create_venv "$LLMINATOR_GARAK_VENV"
  install_package "$LLMINATOR_GARAK_VENV" "garak>=0.15,<0.16"
fi

LLMINATOR_LINK="${LLMINATOR_BIN_DIR}/llminator"
if [[ -e "$LLMINATOR_LINK" && ! -L "$LLMINATOR_LINK" ]]; then
  echo "error: refusing to replace existing file: $LLMINATOR_LINK" >&2
  exit 1
fi
ln -sfn "${LLMINATOR_MAIN_VENV}/bin/llminator" "$LLMINATOR_LINK"

echo
echo "LLMinator installed successfully."
echo "Command: ${LLMINATOR_LINK}"
if [[ ":${PATH}:" != *":${LLMINATOR_BIN_DIR}:"* ]]; then
  echo "Add this directory to PATH:"
  echo "  export PATH=\"${LLMINATOR_BIN_DIR}:\$PATH\""
fi
echo
echo "Try:"
echo "  llminator --help"
echo "  llminator scan --llm qwen3.5:9b"
if [[ "$LLMINATOR_PROFILE" == "ml" || "$LLMINATOR_PROFILE" == "full" ]]; then
  echo "  llminator scan --onnx ./model.onnx"
fi
if [[ "$LLMINATOR_PROFILE" == "garak" || "$LLMINATOR_PROFILE" == "full" ]]; then
  echo "  llminator scan --llm qwen3.5:9b --deep"
fi
if [[ "$LLMINATOR_UI" == "true" ]]; then
  LLMINATOR_UI_LINK="${LLMINATOR_BIN_DIR}/llminator-ui"
  ln -sfn "${LLMINATOR_MAIN_VENV}/bin/llminator-ui" "$LLMINATOR_UI_LINK"
  echo "  llminator-ui                     # open http://127.0.0.1:7474"
  echo "  llminator-ui --port 8080         # custom port"
fi
