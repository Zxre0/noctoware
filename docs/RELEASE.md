# Publishing Noctoware (maintainer guide)

Everything up to here is automated and tested; these steps need a maintainer
decision because they make things public or create long-lived secrets.

## 1. Create the release signing key (once, offline machine preferred)
```
gpg --quick-generate-key "Noctoware Linux Package Signing <release@YOUR-DOMAIN>" ed25519 sign 3y
FPR=<fingerprint printed above>
gpg --armor --export-secret-keys "$FPR" > noctoware-release-secret.asc   # keep offline + backed up
```
Put the public half into the repository (this replaces the local dev key that
`noctoware-keyring` currently ships):
```
mkdir -p keys/private && GNUPGHOME=keys/private/gnupg gpg --import noctoware-release-secret.asc
NOCTO_SIGNING_KEY=$FPR scripts/export-keyring.sh
git add keys/public && git commit -m "Switch noctoware-keyring to the release key"
```
Bump `pkgver` in `packages/noctoware-keyring/PKGBUILD`.

## 2. GitHub settings
* The repository must be **public**: pacman downloads release assets without
  credentials. (Alternative: host the flat repo directory elsewhere and change
  `NOCTO_REPO_URL`; see docs/REPOSITORY.md.)
* Settings → Environments → create `release`, add required reviewers.
* In that environment add secrets `NOCTO_SIGNING_KEY_ASC` (the armored secret
  key) and, if the key has one, `NOCTO_SIGNING_KEY_PASSPHRASE`.

## 3. Publish the package repository
Actions → **release-repo** → Run workflow with `dry_run: true`; review the
plan; run again with `dry_run: false`. The workflow builds with the release
key, runs every check, simulates `pacman -Syu`, uploads packages before the
databases, and validates the published repository.

After the first publish, `sudo pacman -Syu` works on installed systems
(until then the unreachable `[noctoware]` database makes pacman's sync fail —
docs/KNOWN_ISSUES.md).

## 4. Build and publish the ISO
```
scripts/build-packages.sh              # with NOCTO_SIGNING_KEY set to the release key
sudo scripts/build-iso.sh
NOCTO_SIGNING_KEY=$FPR scripts/sign-iso.sh
tests/vm/run-all.sh                    # full QEMU release suite (~25 min)
scripts/split-iso.sh                   # parts < 2 GiB + checksums + REASSEMBLE.txt
gh release create v0.1-alpha out/noctoware-*.iso.part-* out/noctoware-*.iso.{sig,sha256,parts.sha256} \
   out/REASSEMBLE.txt --prerelease --notes-file docs/PROGRESS.md
```
GitHub limits release assets to 2 GiB and the ISO is ~4.7 GiB (with the
offline KDE + driver cache), so it is published as numbered parts that users
join with `cat` (REASSEMBLE.txt). For a single-file download, host the ISO on
object storage (S3/R2/B2) or a torrent instead and link it from the notes.

## 5. Before calling it "hardware-ready"
Run the live ISO and an install on real NVIDIA (RTX 20–50), AMD and Intel
machines, a hybrid laptop, and with Secure Boot disabled; record results in
docs/TESTING.md. VM results are not hardware validation.
