"""Static consistency checks for the Calamares configuration."""
import re
import sys
from pathlib import Path

import yaml

C = Path(__file__).resolve().parents[2] / "calamares"
errors = []
settings = yaml.safe_load((C / "settings.conf").read_text())
instances = {f"{i['module']}@{i['id']}": i for i in settings["instances"]}
for i in settings["instances"]:
    if not (C / "modules" / i["config"]).is_file():
        errors.append(f"instance {i['id']}: missing modules/{i['config']}")
steps = [m for phase in settings["sequence"] for mods in phase.values() for m in mods]
for m in steps:
    if "@" in m and m not in instances:
        errors.append(f"sequence uses undefined instance {m}")
    if "@" not in m and m in ("noctoware_bootcfg",) and not (C / "modules-local" / m / "module.desc").is_file():
        errors.append(f"local module {m} missing")
# exec ordering invariants
ex = [m for phase in settings["sequence"] for k, mods in phase.items() if k == "exec" for m in mods]
def before(a, b):
    if ex.index(a) >= ex.index(b):
        errors.append(f"{a} must run before {b}")
before("unpackfs", "shellprocess@live_cleanup")
before("shellprocess@live_cleanup", "shellprocess@gpu")       # keyring + archiso hooks gone first
before("shellprocess@gpu", "shellprocess@kernel")             # final initramfs includes GPU modules
before("shellprocess@desktop_install", "shellprocess@kernel")
before("shellprocess@kernel", "noctoware_bootcfg")
before("noctoware_bootcfg", "bootloader")                     # sets noctoware_bootloader
before("removeuser", "users")
# shellprocess scripts exist
for conf in (C / "modules").glob("shellprocess_*.conf"):
    for entry in yaml.safe_load(conf.read_text())["script"]:
        cmd = entry["command"] if isinstance(entry, dict) else entry
        path = cmd.split()[0]
        if path.startswith("/usr/share/noctoware/calamares/scripts/"):
            if not (C / "scripts" / Path(path).name).is_file():
                errors.append(f"{conf.name}: script {path} not in calamares/scripts")
# desktop chooser ids <-> install-desktop
ids = [i["id"] for i in yaml.safe_load((C / "modules/packagechooser_desktop.conf").read_text())["items"]]
script = (C / "scripts/install-desktop").read_text()
for i in ids:
    if not re.search(rf"^\s*{re.escape(i)}[|)]", script, re.M) and f"{i}|" not in script:
        errors.append(f"install-desktop does not handle chooser id {i}")
if "${gs[packagechooser_desktop]}" not in (C / "modules/shellprocess_desktop.conf").read_text():
    errors.append("desktop_install does not read packagechooser_desktop")
# bootloader handshake
boot = yaml.safe_load((C / "modules/bootloader.conf").read_text())
if f'GS_KEY = "{boot["efiBootLoaderVar"]}"' not in (C / "modules-local/noctoware_bootcfg/main.py").read_text():
    errors.append("bootloader.conf efiBootLoaderVar does not match noctoware_bootcfg GS_KEY")
# btrfs layout needed for snapshots/rollback
subs = {s["subvolume"] for s in yaml.safe_load((C / "modules/mount.conf").read_text())["btrfsSubvolumes"]}
for need in ("/@", "/@home", "/@snapshots", "/@log", "/@cache"):
    if need not in subs:
        errors.append(f"mount.conf lacks subvolume {need}")
part = yaml.safe_load((C / "modules/partition.conf").read_text())
if part["efiSystemPartition"] != "/boot":
    errors.append("ESP must be /boot for systemd-boot static entries")
if set(part["availableFileSystemTypes"]) != {"btrfs", "ext4"} or part["defaultFileSystemType"] != "btrfs":
    errors.append("filesystems must be btrfs (default) and ext4")
# no live identifiers copied
mid = yaml.safe_load((C / "modules/machineid.conf").read_text())
if not mid.get("systemd") or mid.get("entropy-copy"):
    errors.append("machine-id must be regenerated and entropy not copied")
for e in errors:
    print("ERROR:", e)
print(f"{len(steps)} steps checked, {len(errors)} errors")
sys.exit(1 if errors else 0)
