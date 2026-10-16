#!/usr/bin/env bash
# shellcheck disable=SC2034
# Noctoware Linux archiso profile.  Built by scripts/build-iso.sh, which
# generates the build-time pacman.conf (frozen DB snapshot + local repo).
iso_name="noctoware"
iso_label="NOCTO_$(date --date="@${SOURCE_DATE_EPOCH:-$(date +%s)}" +%Y%m)"
iso_publisher="Noctoware Linux <https://github.com/Zxre0/noctoware>"
iso_application="Noctoware Linux Live/Install medium"
iso_version="0.1-alpha-$(date --date="@${SOURCE_DATE_EPOCH:-$(date +%s)}" +%Y.%m.%d)"
install_dir="arch"
buildmodes=('iso')
bootmodes=('bios.syslinux' 'uefi.systemd-boot')
arch="x86_64"
pacman_conf="pacman.build.conf"
airootfs_image_type="squashfs"
airootfs_image_tool_options=('-comp' 'zstd' '-Xcompression-level' '19' '-b' '1M')
# Live session only: larger copy-on-write area (RAM-backed, used as needed).
kernel_params_x86_64="cow_spacesize=4G"
file_permissions=(
  ["/etc/shadow"]="0:0:400"
  ["/etc/gshadow"]="0:0:400"
  ["/root"]="0:0:750"
  ["/etc/sudoers.d"]="0:0:750"
  ["/etc/sudoers.d/90-noctoware-live"]="0:0:440"
  ["/usr/local/bin/noctoware-live-setup"]="0:0:755"
)
