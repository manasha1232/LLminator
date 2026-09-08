#!/usr/bin/env bash
set -euo pipefail

LLMINATOR_RELEASE_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
LLMINATOR_VERSION="$(
  sed -n 's/^version = "\([^"]*\)"/\1/p' "${LLMINATOR_RELEASE_ROOT}/pyproject.toml" |
    head -n 1
)"
LLMINATOR_RELEASE_NAME="llminator-${LLMINATOR_VERSION}"
LLMINATOR_STAGE_ROOT="$(mktemp -d)"
LLMINATOR_STAGE_DIR="${LLMINATOR_STAGE_ROOT}/${LLMINATOR_RELEASE_NAME}"
LLMINATOR_DIST_DIR="${LLMINATOR_RELEASE_ROOT}/dist"
LLMINATOR_TEMP_ZIP="${LLMINATOR_STAGE_ROOT}/${LLMINATOR_RELEASE_NAME}.zip"

cleanup() {
  rm -rf -- "$LLMINATOR_STAGE_ROOT"
}
trap cleanup EXIT

if ! command -v zip >/dev/null 2>&1; then
  echo "error: zip is required to build the release" >&2
  exit 1
fi
if ! command -v sha256sum >/dev/null 2>&1; then
  echo "error: sha256sum is required to build the release" >&2
  exit 1
fi
if [[ -z "$LLMINATOR_VERSION" ]]; then
  echo "error: could not read project version" >&2
  exit 1
fi

mkdir -p "$LLMINATOR_STAGE_DIR" "$LLMINATOR_DIST_DIR"

cp -R \
  "${LLMINATOR_RELEASE_ROOT}/llminator" \
  "${LLMINATOR_RELEASE_ROOT}/scripts" \
  "${LLMINATOR_RELEASE_ROOT}/tests" \
  "${LLMINATOR_RELEASE_ROOT}/examples" \
  "$LLMINATOR_STAGE_DIR/"

cp \
  "${LLMINATOR_RELEASE_ROOT}/pyproject.toml" \
  "${LLMINATOR_RELEASE_ROOT}/README.md" \
  "${LLMINATOR_RELEASE_ROOT}/LLMINATOR_SUMMARY.md" \
  "${LLMINATOR_RELEASE_ROOT}/SHIPPING.md" \
  "${LLMINATOR_RELEASE_ROOT}/install.sh" \
  "${LLMINATOR_RELEASE_ROOT}/install_ui.sh" \
  "${LLMINATOR_RELEASE_ROOT}/.releaseignore" \
  "$LLMINATOR_STAGE_DIR/"

find "$LLMINATOR_STAGE_DIR" -type d -name __pycache__ -prune -exec rm -rf -- {} +
find "$LLMINATOR_STAGE_DIR" -type f \( -name '*.pyc' -o -name '*.log' \) -delete

(
  cd "$LLMINATOR_STAGE_ROOT"
  zip -q -r "$LLMINATOR_TEMP_ZIP" "$LLMINATOR_RELEASE_NAME"
)

mv -f -- "$LLMINATOR_TEMP_ZIP" "${LLMINATOR_DIST_DIR}/${LLMINATOR_RELEASE_NAME}.zip"
(
  cd "$LLMINATOR_DIST_DIR"
  sha256sum "${LLMINATOR_RELEASE_NAME}.zip" >"${LLMINATOR_RELEASE_NAME}.zip.sha256"
)

echo "Built:"
echo "  ${LLMINATOR_DIST_DIR}/${LLMINATOR_RELEASE_NAME}.zip"
echo "  ${LLMINATOR_DIST_DIR}/${LLMINATOR_RELEASE_NAME}.zip.sha256"

