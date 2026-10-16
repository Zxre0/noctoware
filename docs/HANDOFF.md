# Handoff — Noctoware Linux 0.1 Alpha

State of the project when autonomous development stopped, and what is left
for the maintainer. Details: docs/PROGRESS.md (definition of done),
docs/KNOWN_ISSUES.md, docs/RELEASE.md (publishing steps).

## Done and verified
* Packages: 18 Noctoware packages build reproducibly from `packages/` and are
  signed into a local `[noctoware]` repository (`scripts/build-packages.sh`).
* ISO: `out/noctoware-0.1-alpha-*.iso` boots in UEFI and BIOS mode; Calamares
  installs Hyprland + HyDE (default) or Hyprland + KDE Plasma, Btrfs with
  snapshots or ext4, fully offline.
* Test results on the final ISO: **178/178 checks, 0 failures** across 15 QEMU
  scenarios: live UEFI/BIOS, installs, Plasma + mocked hybrid NVIDIA offline,
  KDE later, opt-in Claude Code / Revo Shell, rollback, multi-monitor, Secure Boot
  (docs/RELEASE-TEST-2026-10-16.md).
* CI (GitHub Actions, private repo): builds every package with an ephemeral
  key, runs the fast suite, checks dependencies against live Arch + CachyOS,
  simulates `pacman -Syu`, and tests the publish pipeline with a simulated GitHub Releases.

## Needs you (not done because it publishes something or needs hardware)
1. **Release signing key**: create it and switch `noctoware-keyring` to it
   (docs/RELEASE.md §1). Packages are currently signed with a local DEV key,
   and `publish-repo.sh` refuses to publish them.
2. **Make `Zxre0/noctoware` public and publish `[noctoware]`**: set up the
   `release` environment and its secrets, then run the **release-repo**
   workflow (§2–3). Until this is done, `sudo pacman -Syu` fails on installed
   systems at the `[noctoware]` sync.
3. **Publish the ISO**: `scripts/split-iso.sh` makes it fit GitHub's 2 GiB
   asset limit, or host it elsewhere (§4).
4. **Real hardware**: follow docs/HARDWARE_TESTING.md and collect
   `noctoware-hwreport` output from NVIDIA, AMD, Intel and hybrid machines.
   Only QEMU has been tested so far.
5. **Remove the build sudo rule** that was added for autonomous ISO builds:
   `sudo rm /etc/sudoers.d/90-noctoware-build`.

## Everyday commands
```
scripts/build-packages.sh            # build + sign packages into repository/x86_64
tests/run-tests.sh                   # fast suite (~1 min)
sudo scripts/build-iso.sh            # ISO into out/
tests/vm/run-all.sh                  # full QEMU release suite (~25 min)
```
