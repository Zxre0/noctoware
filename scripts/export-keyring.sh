#!/usr/bin/env bash
# Export the public half of the active signing key into keys/public/ in the
# format pacman-key --populate expects (noctoware.gpg, -trusted, -revoked).
source "$(dirname "$0")/lib/common.sh"
need gpg

fpr="$(signing_key)" || die "no signing key configured (run scripts/gen-dev-key.sh or set NOCTO_SIGNING_KEY)" "$E_SIGN"
pub="${NOCTO_KEYS_DIR}/public"
install -d "$pub"
nocto_gpg --export "$fpr" >"$pub/noctoware.gpg"
[[ -s "$pub/noctoware.gpg" ]] || die "export of $fpr produced an empty keyring" "$E_SIGN"
# Ownertrust format "<fpr>:4:" == full trust for the master key.
printf '%s:4:\n' "$fpr" >"$pub/noctoware-trusted"
touch "$pub/noctoware-revoked"
nocto_gpg --armor --export "$fpr" >"$pub/noctoware.asc"
ok "exported public key $fpr to keys/public/"
