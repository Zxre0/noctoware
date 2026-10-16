#!/usr/bin/env bash
# Fast, root-free test suite (CI runs this on every push / pull request).
#   tests/run-tests.sh
source "$(dirname "$0")/../scripts/lib/common.sh"
cd "$NOCTO_ROOT"
fail=0
t() { local name="$1"; shift; if "$@" >"$NOCTO_WORK/test-$name.log" 2>&1; then ok "$name"; else warn "FAIL: $name (see work/test-$name.log)"; tail -15 "$NOCTO_WORK/test-$name.log" >&2; fail=1; fi; }
mkdir -p "$NOCTO_WORK"

shell_files=(scripts/*.sh scripts/lib/common.sh calamares/scripts/* desktop/hyde/bin/* desktop/session/noctoware-session
             desktop/session/kdeglobals-swap desktop/system/bin/* desktop/ai/noctoware-claude-setup desktop/ai/claude-shim
             desktop/revo/* desktop/installer/noctoware-installer iso/airootfs/usr/local/bin/*)
t bash-syntax bash -c 'for f in "$@"; do bash -n "$f" || exit 1; done' _ "${shell_files[@]}"
if command -v shellcheck >/dev/null; then t shellcheck shellcheck -S error "${shell_files[@]}"; fi
t python-compile python3 -m py_compile desktop/gpu/noctoware-gpu desktop/welcome/noctoware-welcome \
    calamares/modules-local/noctoware_bootcfg/main.py tests/vm/vmctl.py tests/vm/test_live.py
t unit-tests python3 -I -m unittest discover -s tests/unit
t yaml-configs python3 -I -c '
import sys, yaml, glob
for f in ["calamares/settings.conf", *glob.glob("calamares/modules/*.conf"), "calamares/branding/noctoware/branding.desc"]:
    yaml.safe_load(open(f))
'
t calamares-sequence python3 -I tests/static/check_calamares.py
t gpu-offline-coverage bash -c 'grep -q "noctoware-gpu\" packages" scripts/build-iso.sh && python3 -I desktop/gpu/noctoware-gpu packages | grep -q .'
t pkgbuild-srcinfo bash -c 'for d in packages/*/; do (cd "$d" && makepkg --printsrcinfo >/dev/null) || exit 1; done'
t os-release bash -c 'bsdtar -xOf repository/x86_64/noctoware-release-*.pkg.tar.zst etc/os-release | grep -qx "PRETTY_NAME=\"Noctoware Linux\""'
t shell-switch bash tests/integration/test-shell-switch.sh
t kdeglobals-swap bash tests/integration/test-kdeglobals-swap.sh
if ls repository/x86_64/noctoware-hyde-*.pkg.tar.zst >/dev/null 2>&1; then
    t hyde-deploy bash tests/integration/test-hyde-deploy.sh
fi
if [[ -f repository/x86_64/noctoware.db.tar.gz ]]; then t repo-integrity scripts/check-repo.sh; fi
((fail == 0)) && ok "all tests passed" || die "some tests failed" "$E_TEST"
