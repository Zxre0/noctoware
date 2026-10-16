#!/usr/bin/env bash
# Split the ISO into parts below GitHub's 2 GiB release-asset limit.
#   scripts/split-iso.sh [ISO]   -> ISO.part-aa, -ab, ... + ISO.parts.sha256 + REASSEMBLE.txt
# Users reassemble with `cat ISO.part-* > ISO` and verify ISO.sha256 / ISO.sig.
source "$(dirname "$0")/lib/common.sh"
need split sha256sum
iso="${1:-$(ls -t "$NOCTO_OUT"/noctoware-*.iso 2>/dev/null | head -1)}"
[[ -f "$iso" ]] || die "no ISO" "$E_USAGE"
name="$(basename "$iso")"; dir="$(dirname "$iso")"
rm -f "$iso".part-*
split -b 1900M -d -a 2 "$iso" "$iso.part-"
(cd "$dir" && sha256sum "$name".part-* >"$name.parts.sha256")
[[ -f "$iso.sha256" ]] || (cd "$dir" && sha256sum "$name" >"$name.sha256")
cat >"$dir/REASSEMBLE.txt" <<TXT
Noctoware Linux ISO — download every ${name}.part-NN file plus ${name}.sha256
(and ${name}.sig), then:

  sha256sum -c ${name}.parts.sha256
  cat ${name}.part-* > ${name}
  sha256sum -c ${name}.sha256
  gpg --verify ${name}.sig ${name}      # with the Noctoware release key
TXT
# self-check: reassembly reproduces the ISO
cat "$iso".part-* | sha256sum | cut -d' ' -f1 | grep -qx "$(sha256sum "$iso" | cut -d' ' -f1)" || die "reassembly mismatch" "$E_BUILD"
ok "$(ls "$iso".part-* | wc -l) parts (max $(du -h "$iso".part-00 | cut -f1)), reassembly verified"
