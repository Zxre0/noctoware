#!/usr/bin/env bash
# Sign the newest ISO (detached signature + SHA-256) with the Noctoware key.
#   scripts/sign-iso.sh [ISO]      verify with: gpg --verify ISO.sig ISO
source "$(dirname "$0")/lib/common.sh"
need gpg sha256sum
iso="${1:-$(ls -t "$NOCTO_OUT"/noctoware-*.iso 2>/dev/null | head -1)}"
[[ -f "$iso" ]] || die "no ISO found" "$E_USAGE"
key="$(signing_key)" || die "no signing key" "$E_SIGN"
(cd "$(dirname "$iso")" && sha256sum "$(basename "$iso")" >"$(basename "$iso").sha256")
nocto_gpg --yes --detach-sign -u "$key" -o "$iso.sig" "$iso" || die "signing failed" "$E_SIGN"
nocto_gpg --verify "$iso.sig" "$iso" 2>/dev/null || die "signature does not verify" "$E_SIGN"
ok "signed $(basename "$iso") with $key"
