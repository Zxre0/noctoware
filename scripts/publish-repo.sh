#!/usr/bin/env bash
# Publish the local [noctoware] repository to GitHub Releases.
#
#   scripts/publish-repo.sh            dry run: show what would change
#   scripts/publish-repo.sh --confirm  actually upload (needs `gh` auth)
#
# Safety rails:
#   * refuses unless the working tree is clean and on the release branch
#     (override the branch with NOCTO_RELEASE_BRANCH)
#   * refuses unless check-repo.sh passes (every file signed by the key in
#     keys/public, db consistent) and the key is not the local dev key
#     (override with NOCTO_ALLOW_DEV_KEY=1 for a private test repo only)
#   * uploads packages + signatures first and the databases LAST, so clients
#     never see a database that references files not yet uploaded
#   * keeps the previous generation of packages for clients with a cached db
#
# Hosting layout: one release (tag $NOCTO_REPO_TAG) whose assets form a flat
# pacman repo.  Server = https://github.com/<owner>/<repo>/releases/download/<tag>
# pacman follows GitHub's redirect to its asset CDN.  To migrate to other
# hosting, upload the same flat directory anywhere and change the mirrorlist.
source "$(dirname "$0")/lib/common.sh"
need gh git bsdtar

confirm=0
[[ "${1:-}" == --confirm ]] && confirm=1
branch="${NOCTO_RELEASE_BRANCH:-main}"
repo_slug="${NOCTO_GH_OWNER}/${NOCTO_GH_REPO}"
dir="$NOCTO_REPO_DIR"

cd "$NOCTO_ROOT"
[[ -z "$(git status --porcelain)" ]] || die "working tree is not clean; commit first" "$E_REFUSED"
[[ "$(git rev-parse --abbrev-ref HEAD)" == "$branch" ]] || die "not on $branch" "$E_REFUSED"
"$(dirname "$0")/check-repo.sh" "$dir" || die "integrity check failed" "$E_SIGN"
key="$(signing_key)"
if [[ -f "$NOCTO_KEYS_DIR/private/dev-key.fpr" && "$key" == "$(cat "$NOCTO_KEYS_DIR/private/dev-key.fpr")" && "${NOCTO_ALLOW_DEV_KEY:-0}" != 1 ]]; then
    die "refusing to publish packages signed with the local DEV key" "$E_REFUSED"
fi

# assets: GitHub can't store symlinks, so upload the real db/files archives
# under the names pacman requests.
stage="$(mktemp -d)"; trap 'rm -rf "$stage"' EXIT
for f in noctoware.db noctoware.files; do
    cp -L "$dir/$f.tar.gz" "$stage/$f"; cp -L "$dir/$f.tar.gz.sig" "$stage/$f.sig"
done
mapfile -t new_pkgs < <(bsdtar -xOf "$dir/noctoware.db.tar.gz" --include='*/desc' | awk '/^%FILENAME%$/{getline; print}')
for p in "${new_pkgs[@]}"; do
    [[ "$p" != *:* ]] || die "$p contains ':' which GitHub renames; drop the epoch" "$E_REFUSED"
done

if ! gh release view "$NOCTO_REPO_TAG" -R "$repo_slug" >/dev/null 2>&1; then
    log "release $NOCTO_REPO_TAG does not exist yet"
    remote=()
    prev=()
else
    mapfile -t remote < <(gh release view "$NOCTO_REPO_TAG" -R "$repo_slug" --json assets -q '.assets[].name')
    prev=()
    if gh release download "$NOCTO_REPO_TAG" -R "$repo_slug" -p noctoware.db -D "$stage/prev" >/dev/null 2>&1; then
        mapfile -t prev < <(bsdtar -xOf "$stage/prev/noctoware.db" --include='*/desc' | awk '/^%FILENAME%$/{getline; print}')
    fi
fi

declare -A have keep
for a in "${remote[@]}"; do have["$a"]=1; done
for p in "${new_pkgs[@]}" "${prev[@]}"; do keep["$p"]=1; keep["$p.sig"]=1; done
for f in noctoware.db noctoware.db.sig noctoware.files noctoware.files.sig; do keep["$f"]=1; done

upload=()
for p in "${new_pkgs[@]}"; do
    [[ -n "${have[$p]:-}" ]] || upload+=("$dir/$p" "$dir/$p.sig")
done
delete=()
for a in "${remote[@]}"; do [[ -n "${keep[$a]:-}" ]] || delete+=("$a"); done

log "target: https://github.com/$repo_slug/releases/tag/$NOCTO_REPO_TAG"
log "upload: $((${#upload[@]} / 2)) package(s) + databases; prune: ${#delete[@]} stale asset(s)"
for f in "${upload[@]}"; do echo "  + $(basename "$f")"; done
for f in "${delete[@]}"; do echo "  - $f"; done
if ((confirm == 0)); then
    warn "dry run only. Re-run with --confirm to publish."
    exit 0
fi

if ! gh release view "$NOCTO_REPO_TAG" -R "$repo_slug" >/dev/null 2>&1; then
    gh release create "$NOCTO_REPO_TAG" -R "$repo_slug" --title "[noctoware] x86_64 repository" \
        --notes "pacman repository for Noctoware Linux. Do not download manually; use pacman." --latest=false
fi
((${#upload[@]} == 0)) || gh release upload "$NOCTO_REPO_TAG" -R "$repo_slug" --clobber "${upload[@]}"
gh release upload "$NOCTO_REPO_TAG" -R "$repo_slug" --clobber \
    "$stage/noctoware.db" "$stage/noctoware.db.sig" "$stage/noctoware.files" "$stage/noctoware.files.sig"
for a in "${delete[@]}"; do gh release delete-asset "$NOCTO_REPO_TAG" "$a" -R "$repo_slug" -y; done
ok "published. Verify with: scripts/validate-update.sh --remote"
