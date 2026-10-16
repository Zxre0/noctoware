#!/usr/bin/env bash
# Generate a LOCAL DEVELOPMENT signing key for [noctoware] packages.
#
# The private key lives in keys/private/ (git-ignored).  The public key is
# exported to keys/public/ so noctoware-keyring can ship it.
#
# Release builds must NOT use this key: CI imports the real release key from
# the NOCTO_SIGNING_KEY_ASC secret instead (see .github/workflows/release.yml).
#
# Usage: scripts/gen-dev-key.sh [--force]
source "$(dirname "$0")/lib/common.sh"
need gpg

force=0
[[ "${1:-}" == "--force" ]] && force=1

fpr_file="${NOCTO_KEYS_DIR}/private/dev-key.fpr"
if [[ -s "$fpr_file" && $force -eq 0 ]]; then
    ok "dev key already exists: $(cat "$fpr_file")"
else
    install -d -m700 "${NOCTO_GNUPGHOME}"
    log "generating Ed25519 dev signing key (no passphrase, local use only)"
    nocto_gpg --pinentry-mode loopback --passphrase '' --quick-generate-key \
        "Noctoware Dev Build Key (LOCAL ONLY) <dev@noctoware.invalid>" ed25519 sign 2y
    nocto_gpg --list-secret-keys --with-colons | awk -F: '/^fpr:/{print $10; exit}' >"$fpr_file"
    ok "created $(cat "$fpr_file")"
fi
"$(dirname "$0")/export-keyring.sh"
