# shellcheck shell=bash
# Shared helpers for Noctoware build scripts.  Source, don't execute.
#
# Exit codes used across all scripts (documented in docs/BUILD.md):
#   0  success
#   1  generic failure
#   2  usage error
#   3  missing dependency / tool
#   4  build failure (package, repo, ISO)
#   5  test failure
#   6  signing / integrity failure
#   7  refused: unsafe operation (e.g. publishing from a dirty tree)

set -Eeuo pipefail

readonly E_GENERIC=1 E_USAGE=2 E_DEPS=3 E_BUILD=4 E_TEST=5 E_SIGN=6 E_REFUSED=7

NOCTO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
export NOCTO_ROOT

# shellcheck source=../../noctoware.conf
source "${NOCTO_ROOT}/noctoware.conf"
[[ -f "${NOCTO_ROOT}/noctoware.local.conf" ]] && source "${NOCTO_ROOT}/noctoware.local.conf"

NOCTO_OUT="${NOCTO_OUT:-${NOCTO_ROOT}/out}"
NOCTO_WORK="${NOCTO_WORK:-${NOCTO_ROOT}/work}"
NOCTO_REPO_DIR="${NOCTO_REPO_DIR:-${NOCTO_ROOT}/repository/x86_64}"
NOCTO_KEYS_DIR="${NOCTO_KEYS_DIR:-${NOCTO_ROOT}/keys}"
NOCTO_GNUPGHOME="${NOCTO_GNUPGHOME:-${NOCTO_KEYS_DIR}/private/gnupg}"
export NOCTO_OUT NOCTO_WORK NOCTO_REPO_DIR NOCTO_KEYS_DIR NOCTO_GNUPGHOME

if [[ -t 2 ]]; then
    _c_red=$'\e[31m' _c_grn=$'\e[32m' _c_yel=$'\e[33m' _c_pur=$'\e[35m' _c_off=$'\e[0m'
else
    _c_red='' _c_grn='' _c_yel='' _c_pur='' _c_off=''
fi

log()  { printf '%s==>%s %s\n' "$_c_pur" "$_c_off" "$*" >&2; }
ok()   { printf '%s  ✓%s %s\n' "$_c_grn" "$_c_off" "$*" >&2; }
warn() { printf '%s  !%s %s\n' "$_c_yel" "$_c_off" "$*" >&2; }
die()  { local code="${2:-$E_GENERIC}"; printf '%sERROR:%s %s\n' "$_c_red" "$_c_off" "$1" >&2; exit "$code"; }

_nocto_err_trap() {
    local rc=$? line=${BASH_LINENO[0]} src=${BASH_SOURCE[1]:-?}
    printf '%sERROR:%s command failed (exit %d) at %s:%s: %s\n' \
        "$_c_red" "$_c_off" "$rc" "${src##*/}" "$line" "${BASH_COMMAND}" >&2
}
trap _nocto_err_trap ERR

need() {
    local missing=()
    for c in "$@"; do command -v "$c" >/dev/null 2>&1 || missing+=("$c"); done
    ((${#missing[@]} == 0)) || die "missing required tools: ${missing[*]}" "$E_DEPS"
}

# Run a command as root: directly if already root, else via sudo (non-interactive
# when NOCTO_SUDO_NONINTERACTIVE=1 so CI fails fast instead of hanging).
as_root() {
    if ((EUID == 0)); then "$@"
    elif [[ "${NOCTO_SUDO_NONINTERACTIVE:-0}" == 1 ]]; then sudo -n "$@"
    else sudo "$@"
    fi
}

# Echo the fingerprint of the key used to sign packages and databases.
signing_key() {
    if [[ -n "${NOCTO_SIGNING_KEY}" ]]; then
        printf '%s\n' "${NOCTO_SIGNING_KEY}"
    elif [[ -f "${NOCTO_KEYS_DIR}/private/dev-key.fpr" ]]; then
        cat "${NOCTO_KEYS_DIR}/private/dev-key.fpr"
    else
        return 1
    fi
}

# gpg wrapper bound to the Noctoware signing keyring.
nocto_gpg() { GNUPGHOME="${NOCTO_GNUPGHOME}" gpg --batch "$@"; }

# Ordered list of package directories (dependency order for local builds).
package_dirs() {
    local order="${NOCTO_ROOT}/packages/BUILD_ORDER"
    grep -vE '^\s*(#|$)' "$order" | while read -r p; do
        [[ -f "${NOCTO_ROOT}/packages/${p}/PKGBUILD" ]] || die "BUILD_ORDER lists ${p} but packages/${p}/PKGBUILD is missing"
        printf '%s\n' "$p"
    done
}
