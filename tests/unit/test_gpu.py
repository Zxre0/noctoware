"""Unit tests for desktop/gpu/noctoware-gpu using mock PCI IDs and fake sysfs trees.

Run: python3 -m unittest discover -s tests/unit -v
Device IDs are real PCI IDs (pci.ids) for the named products.
"""
import importlib.machinery
import importlib.util
import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
_loader = importlib.machinery.SourceFileLoader("noctoware_gpu", str(ROOT / "desktop/gpu/noctoware-gpu"))
_spec = importlib.util.spec_from_loader("noctoware_gpu", _loader)
gpu = importlib.util.module_from_spec(_spec)
sys.modules["noctoware_gpu"] = gpu  # dataclasses resolve annotations via sys.modules
_loader.exec_module(gpu)

RTX_2080 = "10de:1e87"
RTX_3060_MOBILE = "10de:2560"
RTX_4070_SUPER = "10de:2783"
RTX_4090 = "10de:2684"
RTX_5090 = "10de:2b85"
GTX_1660 = "10de:2184"   # Turing without RT cores: still open-module capable
GTX_1080 = "10de:1b80"   # Pascal: not supported by open modules
NVIDIA_HDMI_AUDIO = "10de:22bc:040300"
INTEL_UHD_630 = "8086:3e92"
INTEL_ARC_A770 = "8086:56a0"
AMD_RX_7900XTX = "1002:744c"
AMD_RYZEN_APU = "1002:15bf"
QEMU_VIRTIO = "1af4:1050"
QEMU_STD = "1234:1111"
VMWARE_SVGA = "15ad:0405"


def plan_for(ids, **kw):
    return gpu.make_plan(gpu.parse_mock_ids(ids), **kw)


class NvidiaDesktop(unittest.TestCase):
    def test_each_supported_generation_gets_open_modules(self):
        for name, pid in [("RTX 20", RTX_2080), ("RTX 30", RTX_3060_MOBILE), ("RTX 40", RTX_4090),
                          ("RTX 50", RTX_5090), ("GTX 16", GTX_1660)]:
            with self.subTest(name):
                p = plan_for(pid)
                self.assertEqual(p.profile, "nvidia")
                self.assertIn("linux-cachyos-nvidia-open", p.install)
                self.assertIn("linux-cachyos-lts-nvidia-open", p.install)
                self.assertIn("lib32-nvidia-utils", p.install)
                self.assertNotIn("vulkan-nouveau", p.install)

    def test_nvidia_only_forces_nvidia_gl_and_gbm(self):
        env = plan_for(RTX_4090).files["/etc/environment.d/50-noctoware-nvidia.conf"]
        self.assertIn("__GLX_VENDOR_LIBRARY_NAME=nvidia", env)
        self.assertIn("GBM_BACKEND=nvidia-drm", env)
        self.assertIn("LIBVA_DRIVER_NAME=nvidia", env)

    def test_modeset_and_suspend_services(self):
        p = plan_for(RTX_4070_SUPER)
        self.assertIn("modeset=1", p.files["/etc/modprobe.d/noctoware-nvidia.conf"])
        self.assertIn("nvidia-suspend.service", p.services)

    def test_does_not_install_other_vendor_drivers(self):
        p = plan_for(RTX_4090)
        for pkg in ("vulkan-intel", "vulkan-radeon", "lib32-vulkan-intel", "lib32-vulkan-radeon", "nvidia-prime"):
            self.assertNotIn(pkg, p.install)
            self.assertIn(pkg, p.remove)

    def test_dkms_alternative(self):
        p = plan_for(RTX_4090, dkms=True)
        self.assertIn("nvidia-open-dkms", p.install)
        self.assertIn("linux-cachyos-headers", p.install)
        self.assertNotIn("linux-cachyos-nvidia-open", p.install)
        self.assertIn("linux-cachyos-nvidia-open", p.remove)

    def test_never_both_prebuilt_and_dkms(self):
        for dkms in (False, True):
            p = plan_for(RTX_4090, dkms=dkms)
            self.assertFalse({"nvidia-open-dkms", "linux-cachyos-nvidia-open"} <= set(p.install))

    def test_hdmi_audio_function_is_ignored(self):
        p = plan_for(f"{RTX_4090},{NVIDIA_HDMI_AUDIO}")
        self.assertEqual(len(p.gpus), 1)

    def test_secure_boot_warning(self):
        self.assertTrue(any("Secure Boot" in w for w in plan_for(RTX_4090, secure_boot=True).warnings))
        self.assertFalse(any("Secure Boot" in w for w in plan_for(RTX_4090, secure_boot=False).warnings))
        self.assertFalse(any("Secure Boot" in w for w in plan_for(AMD_RX_7900XTX, secure_boot=True).warnings))


class NvidiaLegacy(unittest.TestCase):
    def test_pascal_stays_on_nouveau(self):
        p = plan_for(GTX_1080)
        self.assertIn("vulkan-nouveau", p.install)
        self.assertIn("lib32-vulkan-nouveau", p.install)
        self.assertNotIn("nvidia-utils", p.install)
        self.assertTrue(any("older than Turing" in w for w in p.warnings))
        self.assertEqual(p.profile, "nouveau")

    def test_turing_boundary(self):
        self.assertFalse(gpu.parse_mock_ids("10de:1dff")[0].nvidia_open_supported)
        self.assertTrue(gpu.parse_mock_ids("10de:1e00")[0].nvidia_open_supported)


class Hybrid(unittest.TestCase):
    def test_intel_plus_nvidia_laptop(self):
        p = plan_for(f"{INTEL_UHD_630},{RTX_3060_MOBILE}")
        self.assertEqual(p.profile, "hybrid-nvidia")
        for pkg in ("vulkan-intel", "lib32-vulkan-intel", "linux-cachyos-nvidia-open", "nvidia-prime"):
            self.assertIn(pkg, p.install)
        env = p.files["/etc/environment.d/50-noctoware-nvidia.conf"]
        self.assertNotIn("__GLX_VENDOR_LIBRARY_NAME", env, "must not force NVIDIA GL on hybrid")
        self.assertNotIn("GBM_BACKEND", env)

    def test_amd_apu_plus_nvidia(self):
        p = plan_for(f"{AMD_RYZEN_APU},{RTX_4070_SUPER}")
        self.assertEqual(p.profile, "hybrid-nvidia")
        self.assertIn("vulkan-radeon", p.install)
        self.assertIn("nvidia-prime", p.install)
        self.assertNotIn("vulkan-intel", p.install)


class AmdIntel(unittest.TestCase):
    def test_amd(self):
        p = plan_for(AMD_RX_7900XTX)
        self.assertEqual(p.profile, "amd")
        self.assertIn("vulkan-radeon", p.install)
        self.assertIn("lib32-vulkan-radeon", p.install)
        self.assertFalse(any(x.startswith("nvidia") or "nvidia" in x for x in p.install))
        self.assertNotIn("/etc/environment.d/50-noctoware-nvidia.conf", p.files)

    def test_intel_arc(self):
        p = plan_for(INTEL_ARC_A770)
        self.assertEqual(p.profile, "intel")
        self.assertIn("vulkan-intel", p.install)
        self.assertIn("intel-media-driver", p.install)
        self.assertNotIn("vulkan-radeon", p.install)

    def test_mesa_base_always_present(self):
        for ids in (AMD_RX_7900XTX, INTEL_ARC_A770, RTX_4090, QEMU_VIRTIO, ""):
            with self.subTest(ids):
                p = plan_for(ids)
                for pkg in gpu.MESA_BASE:
                    self.assertIn(pkg, p.install)


class Virtual(unittest.TestCase):
    def test_qemu_virtio(self):
        p = plan_for(QEMU_VIRTIO)
        self.assertEqual(p.profile, "virtual")
        for pkg in ("vulkan-virtio", "lib32-vulkan-virtio", "vulkan-swrast", "spice-vdagent", "qemu-guest-agent"):
            self.assertIn(pkg, p.install)
        self.assertIn("qemu-guest-agent.service", p.services)
        self.assertNotIn("nvidia-utils", p.install)

    def test_qemu_stdvga_and_vmware(self):
        self.assertIn("vulkan-swrast", plan_for(QEMU_STD).install)
        p = plan_for(VMWARE_SVGA)
        self.assertIn("open-vm-tools", p.install)
        self.assertNotIn("spice-vdagent", p.install)

    def test_no_gpu_falls_back_to_software(self):
        p = plan_for("")
        self.assertEqual(p.profile, "fallback")
        self.assertIn("lib32-vulkan-swrast", p.install)


class SteamRequirement(unittest.TestCase):
    """steam depends on lib32-vulkan-driver; every plan must satisfy it."""
    def test_every_profile_has_a_32bit_vulkan_driver(self):
        for ids in (RTX_4090, GTX_1080, AMD_RX_7900XTX, INTEL_ARC_A770, QEMU_VIRTIO, QEMU_STD, "",
                    f"{INTEL_UHD_630},{RTX_3060_MOBILE}"):
            with self.subTest(ids):
                inst = plan_for(ids).install
                self.assertTrue(any(p.startswith("lib32-vulkan-") or p == "lib32-nvidia-utils" for p in inst))

    def test_install_and_remove_are_disjoint(self):
        for ids in (RTX_4090, AMD_RX_7900XTX, f"{INTEL_UHD_630},{RTX_3060_MOBILE}", QEMU_VIRTIO):
            p = plan_for(ids)
            self.assertFalse(set(p.install) & set(p.remove))


class Sysfs(unittest.TestCase):
    def _fake(self, root: Path, slot, vendor, device, cls, boot=None):
        d = root / "bus/pci/devices" / slot
        d.mkdir(parents=True)
        (d / "vendor").write_text(f"0x{vendor}\n")
        (d / "device").write_text(f"0x{device}\n")
        (d / "class").write_text(f"0x{cls}\n")
        if boot is not None:
            (d / "boot_vga").write_text(f"{int(boot)}\n")

    def test_scan_filters_non_display_devices(self):
        with tempfile.TemporaryDirectory() as t:
            root = Path(t)
            self._fake(root, "0000:00:02.0", "8086", "3e92", "030000", boot=True)
            self._fake(root, "0000:01:00.0", "10de", "2560", "030200", boot=False)
            self._fake(root, "0000:01:00.1", "10de", "22bc", "040300")
            self._fake(root, "0000:00:1f.3", "8086", "a348", "040380")
            gpus = gpu.scan_sysfs(root)
            self.assertEqual([g.slot for g in gpus], ["0000:00:02.0", "0000:01:00.0"])
            self.assertTrue(gpus[0].boot_vga)
            self.assertEqual(gpu.make_plan(gpus).profile, "hybrid-nvidia")

    def test_secure_boot_efivar(self):
        with tempfile.TemporaryDirectory() as t:
            root = Path(t)
            self.assertIsNone(gpu.secure_boot_enabled(root))
            ev = root / "firmware/efi/efivars"
            ev.mkdir(parents=True)
            (ev / "SecureBoot-8be4df61-93ca-11d2-aa0d-00e098032b8c").write_bytes(b"\x06\x00\x00\x00\x01")
            self.assertTrue(gpu.secure_boot_enabled(root))
            (ev / "SecureBoot-8be4df61-93ca-11d2-aa0d-00e098032b8c").write_bytes(b"\x06\x00\x00\x00\x00")
            self.assertFalse(gpu.secure_boot_enabled(root))


class Cli(unittest.TestCase):
    def test_plan_json(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = gpu.main(["plan", "--json", "--mock-ids", f"{INTEL_UHD_630},{RTX_3060_MOBILE}", "--secure-boot", "off"])
        self.assertEqual(rc, 0)
        data = json.loads(buf.getvalue())
        self.assertEqual(data["profile"], "hybrid-nvidia")
        self.assertEqual(len(data["gpus"]), 2)

    def test_bad_mock_id(self):
        with self.assertRaises(ValueError):
            gpu.parse_mock_ids("nonsense")


if __name__ == "__main__":
    unittest.main()
