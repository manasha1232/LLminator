#!/usr/bin/env bash
# ════════════════════════════════════════════════════════════════════════════════
#  install_ui.sh — LLMinator ONNX Web UI integration script
#
#  Integrates the llminator-ui ONNX browser interface into an EXISTING
#  llminator installation WITHOUT needing to re-run the full install.sh.
#
#  Usage:
#    ./install_ui.sh                          # auto-detect llminator
#    ./install_ui.sh --prefix ~/.local/share/llminator
#    ./install_ui.sh --bin-dir ~/.local/bin
#    ./install_ui.sh --port 8080              # bake a custom default port
#    ./install_ui.sh --uninstall              # remove the UI only
#    ./install_ui.sh --help
#
#  What this script does:
#    1. Locates the llminator virtual environment on the target machine.
#    2. Installs Flask into that venv (pip or uv, whichever is available).
#    3. Re-installs (or upgrades) the llminator package itself so that the
#       llminator.ui sub-package and its static assets are present.
#    4. Creates a `llminator-ui` symlink in the same bin directory that
#       already holds the `llminator` command.
#    5. Prints a one-liner to start the server.
#
# ════════════════════════════════════════════════════════════════════════════════
set -euo pipefail

# ── Defaults ──────────────────────────────────────────────────────────────────
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
UI_INSTALL_ROOT="${LLMINATOR_INSTALL_ROOT:-${HOME}/.local/share/llminator}"
UI_BIN_DIR="${LLMINATOR_BIN_DIR:-${HOME}/.local/bin}"
UI_PORT=7474
UI_UNINSTALL=false
UI_SOURCE_DIR="$SCRIPT_DIR"   # top-level project dir (contains pyproject.toml)

# ── Colour helpers ────────────────────────────────────────────────────────────
_bold()  { printf '\033[1m%s\033[0m\n' "$*"; }
_green() { printf '\033[0;32m%s\033[0m\n' "$*"; }
_cyan()  { printf '\033[0;36m%s\033[0m\n' "$*"; }
_warn()  { printf '\033[0;33mwarn: %s\033[0m\n' "$*" >&2; }
_err()   { printf '\033[0;31merror: %s\033[0m\n' "$*" >&2; }
_step()  { printf '\n\033[1;34m==> %s\033[0m\n' "$*"; }

usage() {
  cat <<'EOF'

  install_ui.sh — LLMinator ONNX Web UI integration

  Usage:
    ./install_ui.sh                          Auto-detect existing installation
    ./install_ui.sh --prefix  PATH           Path to the llminator install root
                                              (default: ~/.local/share/llminator)
    ./install_ui.sh --bin-dir PATH           Directory that holds the llminator
                                              symlink (default: ~/.local/bin)
    ./install_ui.sh --port    N              Default port baked into the launcher
                                              wrapper (default: 7474)
    ./install_ui.sh --uninstall              Remove the llminator-ui command only
    ./install_ui.sh --help                   Show this message

  Examples:
    ./install_ui.sh
    ./install_ui.sh --prefix /opt/llminator --bin-dir /usr/local/bin
    ./install_ui.sh --port 8080
    ./install_ui.sh --uninstall

EOF
}

# ── Argument parsing ──────────────────────────────────────────────────────────
while (($#)); do
  case "$1" in
    --prefix)
      shift
      [[ $# -eq 0 ]] && { _err "--prefix requires a path"; exit 2; }
      UI_INSTALL_ROOT="$1"
      ;;
    --bin-dir)
      shift
      [[ $# -eq 0 ]] && { _err "--bin-dir requires a path"; exit 2; }
      UI_BIN_DIR="$1"
      ;;
    --port)
      shift
      [[ $# -eq 0 ]] && { _err "--port requires a number"; exit 2; }
      UI_PORT="$1"
      ;;
    --uninstall)
      UI_UNINSTALL=true
      ;;
    --help|-h)
      usage
      exit 0
      ;;
    *)
      _err "unknown option: $1"
      usage >&2
      exit 2
      ;;
  esac
  shift
done

UI_MAIN_VENV="${UI_INSTALL_ROOT}/venv"
UI_VENV_PYTHON="${UI_MAIN_VENV}/bin/python"
UI_VENV_PIP="${UI_MAIN_VENV}/bin/pip"
UI_LINK="${UI_BIN_DIR}/llminator-ui"

# ── Uninstall path ────────────────────────────────────────────────────────────
if [[ "$UI_UNINSTALL" == "true" ]]; then
  _step "Removing llminator-ui"
  if [[ -L "$UI_LINK" ]]; then
    rm -f -- "$UI_LINK"
    _green "Removed symlink: $UI_LINK"
  else
    _warn "No symlink found at $UI_LINK — nothing to remove."
  fi
  # Remove Flask from the venv (best-effort; don't fail if already absent)
  if [[ -x "$UI_VENV_PYTHON" ]]; then
    "$UI_VENV_PYTHON" -m pip uninstall -y flask werkzeug click itsdangerous jinja2 2>/dev/null || true
    _green "Flask removed from venv."
  fi
  echo
  _bold "llminator-ui uninstalled."
  exit 0
fi

# ── Sanity checks ─────────────────────────────────────────────────────────────
_step "Checking prerequisites"

# 1. venv must already exist
if [[ ! -d "$UI_MAIN_VENV" ]]; then
  _err "Could not find the llminator venv at: $UI_MAIN_VENV"
  _err "Run install.sh first, or pass --prefix to point at the correct location."
  exit 1
fi
_green "venv found: $UI_MAIN_VENV"

# 2. llminator binary must be installed inside that venv
LLMINATOR_IN_VENV="${UI_MAIN_VENV}/bin/llminator"
if [[ ! -x "$LLMINATOR_IN_VENV" ]]; then
  _err "llminator is not installed in the venv: $LLMINATOR_IN_VENV"
  _err "Run install.sh first to install llminator."
  exit 1
fi
_green "llminator binary: $LLMINATOR_IN_VENV"

# 3. Source tree must contain pyproject.toml (so we can pip install .[ui])
if [[ ! -f "${UI_SOURCE_DIR}/pyproject.toml" ]]; then
  _err "pyproject.toml not found in: $UI_SOURCE_DIR"
  _err "Run this script from the llminator source directory."
  exit 1
fi
_green "Source dir: $UI_SOURCE_DIR"

# 4. Port must be a valid integer in [1024, 65535]
if ! [[ "$UI_PORT" =~ ^[0-9]+$ ]] || (( UI_PORT < 1024 || UI_PORT > 65535 )); then
  _err "--port must be an integer between 1024 and 65535, got: $UI_PORT"
  exit 2
fi
_green "UI port: $UI_PORT"

# ── Install Flask + llminator[ui] into the existing venv ─────────────────────
_step "Installing Flask into the llminator venv"

install_pkg() {
  # Prefer uv for speed; fall back to pip
  if command -v uv >/dev/null 2>&1; then
    uv pip install --python "${UI_VENV_PYTHON}" "$@"
  else
    "${UI_VENV_PYTHON}" -m pip install --quiet --upgrade "$@"
  fi
}

install_pkg "${UI_SOURCE_DIR}[ui]"
_green "Flask installed."

# ── Ensure llminator.ui static assets are present in the venv ─────────────────
_step "Verifying UI assets"

UI_PKG_DIR="$("$UI_VENV_PYTHON" - <<'PYEOF'
import importlib.util, pathlib, sys
spec = importlib.util.find_spec("llminator.ui.server")
if spec is None:
    print("NOT_FOUND")
else:
    print(pathlib.Path(spec.origin).parent / "static")
PYEOF
)"

if [[ "$UI_PKG_DIR" == "NOT_FOUND" ]]; then
  _warn "llminator.ui.server not found in the venv — trying editable re-install."
  install_pkg -e "${UI_SOURCE_DIR}[ui]"
  UI_PKG_DIR="$("$UI_VENV_PYTHON" - <<'PYEOF'
import importlib.util, pathlib
spec = importlib.util.find_spec("llminator.ui.server")
print(pathlib.Path(spec.origin).parent / "static")
PYEOF
)"
fi

# If static assets are not inside site-packages (editable install), copy them.
UI_STATIC_SRC="${UI_SOURCE_DIR}/llminator/ui/static"
UI_STATIC_DST="${UI_PKG_DIR}"   # e.g. <venv>/lib/python3.11/site-packages/llminator/ui/static

if [[ ! -f "${UI_STATIC_DST}/index.html" ]]; then
  _warn "Static assets not found in venv; copying from source tree."
  mkdir -p "$UI_STATIC_DST"
  cp -R "${UI_STATIC_SRC}/." "${UI_STATIC_DST}/"
  _green "Static assets copied to: $UI_STATIC_DST"
else
  _green "Static assets present: $UI_STATIC_DST"
fi

# ── Create llminator-ui symlink ───────────────────────────────────────────────
_step "Installing llminator-ui command"

mkdir -p "$UI_BIN_DIR"
LLMINATOR_UI_BIN="${UI_MAIN_VENV}/bin/llminator-ui"

# If the console script was created by pip, use it directly.
# Otherwise create a thin wrapper that calls the module.
if [[ ! -x "$LLMINATOR_UI_BIN" ]]; then
  _warn "llminator-ui console script not found; creating wrapper."
  cat > "$LLMINATOR_UI_BIN" <<WRAPPER
#!/usr/bin/env bash
exec "${UI_VENV_PYTHON}" -m llminator.ui.server "\$@"
WRAPPER
  chmod +x "$LLMINATOR_UI_BIN"
fi

if [[ -e "$UI_LINK" && ! -L "$UI_LINK" ]]; then
  _err "A non-symlink file already exists at $UI_LINK — refusing to overwrite."
  _err "Remove it manually and re-run this script."
  exit 1
fi
ln -sfn "$LLMINATOR_UI_BIN" "$UI_LINK"
_green "Symlink created: $UI_LINK -> $LLMINATOR_UI_BIN"

# ── Verify the PATH contains the bin dir ─────────────────────────────────────
PATH_HINT=""
if [[ ":${PATH}:" != *":${UI_BIN_DIR}:"* ]]; then
  PATH_HINT="(add ${UI_BIN_DIR} to PATH first)"
fi

# ── Done ──────────────────────────────────────────────────────────────────────
echo
_bold "════════════════════════════════════════"
_bold " LLMinator ONNX Web UI — installed ✓"
_bold "════════════════════════════════════════"
echo
_cyan "  Start the UI:"
echo  "    llminator-ui ${PATH_HINT}"
echo
_cyan "  Custom port:"
echo  "    llminator-ui --port ${UI_PORT}"
echo
_cyan "  Network-accessible (LAN):"
echo  "    llminator-ui --host 0.0.0.0 --port ${UI_PORT}"
echo
_cyan "  Then open:"
echo  "    http://127.0.0.1:${UI_PORT}"
echo
_cyan "  Uninstall UI only:"
echo  "    ./install_ui.sh --uninstall"
echo
