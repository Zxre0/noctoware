# Building Noctoware

Everything builds on an Arch Linux or CachyOS host (x86_64). Only
`build-iso.sh` needs root.

```
scripts/prepare.sh                 # build tools, QEMU modules, dev signing key
scripts/build-packages.sh          # build + sign all packages → repository/x86_64
scripts/check-dependencies.sh      # resolve everything against the live repos
tests/run-tests.sh                 # fast tests (no root)
sudo scripts/build-iso.sh          # → out/noctoware-0.1-alpha-YYYY.MM.DD-x86_64.iso
scripts/test-iso.sh all            # QEMU: live boot, install, installed system
```

## Layout
| path | contents |
|---|---|
| `noctoware.conf` | names, version, repository URL, signing key (env-overridable) |
| `packages/` | one PKGBUILD per package; `BUILD_ORDER` lists the local build order |
| `desktop/` | sources the packages install: HyDE theme + deploy, session wrappers, GPU tool, Welcome app, Plasma branding, AI tools, Revo switcher, SDDM theme |
| `calamares/` | installer settings, module configs, custom module, scripts, branding |
| `branding/` | SVG originals of the logo/wallpapers, Fastfetch logo |
| `iso/` | archiso profile (derived from archiso `releng`) |
| `repository/x86_64/` | generated, signed `[noctoware]` repo (git-ignored) |
| `scripts/` | build, sign, check, publish, test entry points |
| `tests/` | unit, static, integration and QEMU tests |

PKGBUILDs read their local sources from the project tree through
`$startdir/../..`, so they must be built from inside this repository.

## Exit codes (all scripts)
`0` ok · `1` generic · `2` usage · `3` missing dependency · `4` build failure ·
`5` test failure · `6` signing/integrity failure · `7` refused (unsafe).

## Signing
* `scripts/gen-dev-key.sh` creates a **local dev key** (private half in
  `keys/private/`, git-ignored) and exports the public key to `keys/public/`,
  which `noctoware-keyring` ships.
* Release builds use the real key: the `release-repo` workflow imports it
  from the `NOCTO_SIGNING_KEY_ASC` environment secret. **Before the first
  public release, replace `keys/public/*` with the release key** (run
  `NOCTO_SIGNING_KEY=<fpr> scripts/export-keyring.sh` with the release key in
  `keys/private/gnupg`) — `publish-repo.sh` refuses to publish dev-signed
  packages.
* Every package and both databases get detached signatures;
  `scripts/check-repo.sh` verifies them against `keys/public` in an isolated
  keyring. `SigLevel = Required` is used everywhere; nothing disables checks.

## Repository order (installed system)
`[noctoware]` → `[cachyos]` → `[core]` → `[extra]` → `[multilib]`.
`[cachyos]` must precede Arch because `linux-cachyos-nvidia-open` pins
CachyOS' `nvidia-utils` build; with Arch first, `pacman -Syu` would break
NVIDIA systems. The ISO uses the generic x86-64 `[cachyos]` repo (not the
v3/v4/znver4 ones) so it runs on every x86_64 CPU.

## Reproducible ISO inputs
`build-iso.sh` downloads every repository database **once** into
`work/iso/frozen/` and lists it as the first `Server` (real mirrors and the
Arch Linux Archive are fallbacks for package files). The live image and the
offline cache (KDE Plasma + NVIDIA packages under `/opt/noctoware/offline`)
are therefore resolved from identical databases, and that snapshot ships on
the ISO so the installer can install from the cache with full signature
verification. A private pacman keyring (`work/iso/gnupg`) is used; the host
keyring is never modified.

## Updating pinned upstreams
* HyDE: bump `_commit`/`pkgver` in `packages/noctoware-hyde/PKGBUILD`, rebuild,
  run `tests/integration/test-hyde-deploy.sh` and `scripts/check-dependencies.sh`
  (it fails if HyDE's dots need packages we don't depend on).
* plasma-meta changes: `check-dependencies.sh` fails until
  `noctoware-plasma`'s `_plasma` list matches it (minus plasma-login-manager).
* Python minor bump in Arch: rebuild `noctoware-hyde` (pkgrel+1).
