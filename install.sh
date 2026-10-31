#!/usr/bin/env bash
# install.sh - Install or update sportstui symlinks in ~/.local/bin
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BIN_DIR="${HOME}/.local/bin"
TARGET="${SCRIPT_DIR}/sportstui"

mkdir -p "${BIN_DIR}"
chmod +x "${TARGET}"

echo "==> Setting up sportstui in ${BIN_DIR}..."

# 1. Back up standalone cfbtui binary if it is a real file (not a symlink)
if [ -f "${BIN_DIR}/cfbtui" ] && [ ! -L "${BIN_DIR}/cfbtui" ]; then
    echo "    Backing up legacy standalone cfbtui binary to ${BIN_DIR}/cfbtui.elf.bak"
    mv -f "${BIN_DIR}/cfbtui" "${BIN_DIR}/cfbtui.elf.bak"
fi

# 2. Main multi-league executable
ln -sf "${TARGET}" "${BIN_DIR}/sportstui"
echo "    Linked: ${BIN_DIR}/sportstui -> ${TARGET}"

# 3. Individual league launchers
ALIASES=("cfbtui" "cbbtui" "ncaabtui" "nbatui" "nhltui" "mlbtui" "nfltui")

for cmd in "${ALIASES[@]}"; do
    ln -sf "sportstui" "${BIN_DIR}/${cmd}"
    echo "    Linked: ${BIN_DIR}/${cmd} -> sportstui"
done

echo
echo "==> Installation complete!"
echo "    Available commands:"
echo "      sportstui : Combined 6-league scoreboard (1-6 to switch)"
echo "      cfbtui    : College Football"
echo "      cbbtui    : College Basketball (Men's) [also ncaabtui]"
echo "      nbatui    : NBA"
echo "      nhltui    : NHL"
echo "      mlbtui    : MLB"
echo "      nfltui    : NFL"
echo
"${BIN_DIR}/sportstui" --version
