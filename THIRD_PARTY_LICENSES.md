# Third-party licenses and redistribution audit

Noctoware's own code is MIT (`LICENSE`); its artwork is CC-BY-SA-4.0
(`branding/LICENSE.artwork`). Everything else keeps its upstream license.
Packages taken unmodified from Arch Linux or CachyOS repositories are
redistributed on the ISO exactly as those projects distribute them; their
license texts are installed under `/usr/share/licenses/<package>/`, and source
is available from the Arch Linux / CachyOS package sources (links below).

Audit date: 2026-10-15. Re-run the audit when upstream versions change
(`scripts/check-dependencies.sh` and the weekly `upstream-watch` workflow flag
drift).

## Components Noctoware packages or bundles itself

| Component | Upstream | License (SPDX) | How Noctoware uses it | Redistribution |
|---|---|---|---|---|
| HyDE | github.com/HyDE-Project/HyDE @ fa2fd57 (v26.8.1) | GPL-3.0-only | `noctoware-hyde` ships the unmodified upstream tree (only `pyproject.toml`/`uv.lock` re-locked without `xdg-prefs`) | ✅ GPL: license + CREDITS shipped; source = pinned upstream commit + `packages/noctoware-hyde/PKGBUILD` |
| HyDE Python deps (deez-dots, pyprland, loguru, requests, websockets, pulsectl, uv, …) | PyPI / GitHub, versions from HyDE's `uv.lock` | MIT / Apache-2.0 / LGPL-2.1+ (pulsectl: MIT) | bundled venv in `noctoware-hyde` | ✅ permissive; metadata (incl. licenses) in each `*.dist-info` |
| Wallbash GTK / icon themes | HyDE `Source/arcs` | GPL-3.0 (HyDE) | extracted per user | ✅ |
| hyprquery | github.com/HyDE-Project/hyprquery @ 002af78 | LGPL-3.0-only | built from source in `[noctoware]` | ✅ unmodified, license shipped |
| Bibata cursor theme 2.0.7 | github.com/ful1e5/Bibata_Cursor | GPL-3.0-only | repackaged release in `[noctoware]` | ✅ unmodified, license shipped |
| Calamares (CachyOS build) | github.com/CachyOS/cachyos-calamares | GPL-3.0-or-later | used unmodified from `[cachyos]` on the live ISO only; Noctoware config is separate (`noctoware-calamares-config`) | ✅ |

## Components fetched or installed from official repositories

| Component | Source repo | License | Notes |
|---|---|---|---|
| linux-cachyos, linux-cachyos-lts | `[cachyos]` | GPL-2.0-only | official signed CachyOS builds, not rebuilt |
| linux-cachyos-(lts-)nvidia-open | `[cachyos]` | MIT AND GPL-2.0-only | offline cache on ISO; installed only on NVIDIA hardware |
| nvidia-utils, lib32-nvidia-utils, nvidia-settings | `[cachyos]` / `[extra]` | NVIDIA license (custom) | NVIDIA permits redistribution of the unmodified driver; shipped exactly as Arch/CachyOS do, only in the offline cache |
| Hyprland, aquamarine, hypr* | `[extra]` | BSD-3-Clause | |
| SDDM | `[extra]` | GPL-2.0-only | Noctoware theme is original (MIT code, CC-BY-SA art) |
| KDE Plasma 6 + apps | `[extra]` | GPL-2.0+/LGPL-2.0+ | optional (`noctoware-plasma`) |
| Steam (bootstrap) | `[multilib]` | Steam Subscriber Agreement | the Arch `steam` package is a launcher that downloads the Steam runtime under Valve's terms on first start; preinstalled the same way CachyOS and Garuda do |
| OpenAI Codex CLI | `[extra]` `openai-codex` | Apache-2.0 | preinstalled; NOTICE/license from the Arch package |
| Firefox | `[extra]` | MPL-2.0 | |
| kitty | `[extra]` | GPL-3.0-only | |
| waybar / rofi / dunst / fastfetch / uwsm / mangohud | `[extra]` | MIT / MIT / BSD / MIT / MIT / MIT | |
| gamescope / gamemode | `[extra]` | BSD-2/3-Clause (+ ReShade shader license) / BSD-3-Clause | |
| Papirus icon theme | `[extra]` | GPL-3.0 | |
| Fonts: JetBrains Mono NF, Cascadia Code NF, Mononoki NF, Noto, Noto CJK, Noto Emoji, Cantarell | `[extra]` | OFL-1.1 (RFN variants as listed by Arch) | Nerd Font patched versions packaged by Arch |
| snapper, snap-pac | `[extra]` | GPL-2.0-only / GPL-3.0 | |
| archiso (build tool, not shipped) | `[extra]` | GPL-3.0-or-later | `iso/` profile derives from archiso's `releng` |

## Components NOT redistributed

| Component | Why | What Noctoware does instead |
|---|---|---|
| **Claude Code** (Anthropic) | `LICENSE.md`: "© Anthropic PBC. All rights reserved. Use is subject to Anthropic's Commercial Terms of Service." No redistribution grant. | `noctoware-claude-setup` runs Anthropic's **official installer** (`curl -fsSL https://claude.ai/install.sh \| bash`, per code.claude.com/docs/en/setup) per user, **only after explicit consent**; a `claude` shim offers this on first use. No binaries, keys or credentials are bundled. |
| **Revo Shell** (github.com/vzbc/revo-shell @ 62e13cd) | the repository has **no license file**; default copyright applies, so redistribution is not permitted | kept out of the ISO and out of `[noctoware]`. `noctoware-revo` (Noctoware's own MIT scripts) fetches it from upstream at the user's explicit request. Individual Revo interfaces may carry their own upstream licenses; users fetch them directly. |
| HyDE community themes (hyde-themes) | mixed per-theme licensing | not bundled; users can import them with HyDE's own theme tools |
| `xdg-prefs` (HyDE optional Python dep) | pulls ~650 MB PySide6/WebEngine; unused by HyDE scripts | dropped from the bundled venv (not a licensing issue) |

## Source availability

* Noctoware sources, PKGBUILDs and build scripts: this repository.
* Arch Linux package sources: https://gitlab.archlinux.org/archlinux/packaging/packages
* CachyOS package sources: https://github.com/CachyOS/CachyOS-PKGBUILDS and https://github.com/CachyOS/linux-cachyos
* Pinned upstream commits are recorded in each PKGBUILD (`_commit=`).
