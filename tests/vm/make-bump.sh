#!/usr/bin/env bash
# make-bump.sh REPO_COPY — add noctoware-welcome with pkgrel+1 (signed, indexed)
# to a copy of [noctoware], so VM tests can exercise a real package upgrade.
source "$(dirname "$0")/../../scripts/lib/common.sh"
dst="$(realpath "$1")"; [[ -f "$dst/noctoware.db.tar.gz" ]] || die "not a repo copy: $dst" "$E_USAGE"
tmp="$NOCTO_ROOT/packages/.bump-noctoware-welcome"   # inside the tree so $startdir/../.. resolves
rm -rf "$tmp"; cp -r "$NOCTO_ROOT/packages/noctoware-welcome" "$tmp"
trap 'rm -rf "$tmp"' EXIT
rel="$(sed -n 's/^pkgrel=//p' "$tmp/PKGBUILD")"
sed -i "s/^pkgrel=.*/pkgrel=$((rel + 1))/" "$tmp/PKGBUILD"
key="$(signing_key)"
(cd "$tmp" && PKGDEST="$dst" BUILDDIR="$NOCTO_WORK/build" makepkg -f --nodeps --noconfirm >/dev/null 2>&1) || die "bump build failed" "$E_BUILD"
f="$(cd "$tmp" && PKGDEST="$dst" makepkg --packagelist)"
GNUPGHOME="$NOCTO_GNUPGHOME" gpg --batch --yes --detach-sign -u "$key" "$f"
# GitHub-style flat repo: real files, no symlinks
GNUPGHOME="$NOCTO_GNUPGHOME" repo-add -q --sign --key "$key" --remove "$dst/noctoware.db.tar.gz" "$f"
for n in db files; do
    rm -f "$dst/noctoware.$n" "$dst/noctoware.$n.sig"
    cp "$dst/noctoware.$n.tar.gz" "$dst/noctoware.$n"; cp "$dst/noctoware.$n.tar.gz.sig" "$dst/noctoware.$n.sig"
done
ok "bumped: $(basename "$f")"
