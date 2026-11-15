"""Direct GPU selector contract tests, independent of generated bin wrappers.

These tests check chosen flags and fallback sequencing, not actual GLX/CEF
rendering. Run a real NVIDIA GPU process check separately on the target host.
"""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'src' / 'spotify-gpu.sh'


class GPUModeContractTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.sysfs = self.root / 'sys'
        self.os_release = self.root / 'os-release'
        self.set_os_release('fedora', '44')  # Keep legacy-policy tests host-independent.
        self.capture = self.root / 'capture'
        self.capture.mkdir()
        self.bin_dir = self.root / 'bin'
        self.bin_dir.mkdir()
        self.fake_spotify = self.bin_dir / 'spotify'
        self.fake_spotify.write_text('''#!/usr/bin/env bash
set -eu
n=0
[[ ! -f "$CAPTURE/count" ]] || read -r n < "$CAPTURE/count"
n=$((n + 1))
printf '%s\\n' "$n" > "$CAPTURE/count"
printf '%s\\0' "$@" > "$CAPTURE/args-$n"
if [[ ${FAKE_FAIL_DESKTOP:-0} == 1 && " $* " == *" --use-gl=desktop "* ]]; then
    echo 'Requested GL implementation not found' >&2
    exit 1
fi
if [[ ${FAKE_WARN_ONLY:-0} == 1 ]]; then
    echo 'GPU process unusable' >&2
fi
exit 0
''')
        self.fake_spotify.chmod(0o755)
        self.glxinfo = self.bin_dir / 'glxinfo'
        self.glxinfo.write_text('#!/usr/bin/env bash\nprintf "%s\\n" "${GLX_RENDERER:-OpenGL renderer string: NVIDIA}"\n')
        self.glxinfo.chmod(0o755)
        self.env = dict(os.environ,
            PATH=str(self.bin_dir) + os.pathsep + os.environ['PATH'],
            CAPTURE=str(self.capture), SPOTIFY_SYSFS_ROOT=str(self.sysfs),
            XDG_SESSION_TYPE='wayland', DISPLAY=':77',
            SPOT_FLY_LIGHT_OS_RELEASE_FILE=str(self.os_release))
        for key in ('GLX_RENDERER', 'FAKE_FAIL_DESKTOP', 'FAKE_WARN_ONLY',
                    '__NV_PRIME_RENDER_OFFLOAD', '__GLX_VENDOR_LIBRARY_NAME'):
            self.env.pop(key, None)

    def set_os_release(self, os_id, version):
        self.os_release.write_text(f'ID="{os_id}"\nVERSION_ID="{version}"\n')

    def gpu(self, index, vendor, driver, version=None):
        device = self.sysfs / f'class/drm/card{index}/device'
        device.mkdir(parents=True)
        (device / 'vendor').write_text(vendor + '\n')
        (device / 'driver').symlink_to(self.sysfs / 'drivers' / driver)
        if version:
            module = self.sysfs / 'module/nvidia'
            module.mkdir(parents=True, exist_ok=True)
            (module / 'version').write_text(version + '\n')

    def run_mode(self, mode='auto', *args):
        return subprocess.run(
            ['bash', str(SCRIPT), str(self.fake_spotify), mode, '1', '0', '0', *args],
            env=self.env, capture_output=True, text=True, timeout=10)

    def flags(self, attempt=1):
        return (self.capture / f'args-{attempt}').read_bytes().split(b'\0')[:-1]

    def test_auto_nvidia_580_prefers_desktop_gl_under_current_policy(self):
        self.gpu(0, '0x10de', 'nvidia', '580.196.07')
        result = self.run_mode('auto', 'spotify:track:abc')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('gpu-mode=nvidia-desktop', result.stderr)
        self.assertIn(b'--use-gl=desktop', self.flags())
        self.assertIn(b'--enable-zero-copy', self.flags())
        self.assertIn(b'--ignore-gpu-blocklist', self.flags())
        self.assertNotIn(b'--use-gl=angle', self.flags())
        self.assertEqual(self.flags()[-1], b'spotify:track:abc')

    def test_fedora45_auto_nvidia_580_uses_working_angle_path(self):
        self.set_os_release('fedora', '45')
        self.gpu(0, '0x10de', 'nvidia', '580.196.07')
        result = self.run_mode('auto')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('gpu-mode=nvidia ', result.stderr)
        self.assertIn(b'--use-gl=angle', self.flags())
        self.assertIn(b'--use-angle=gl', self.flags())
        self.assertIn(b'--enable-zero-copy', self.flags())
        self.assertIn(b'--ignore-gpu-blocklist', self.flags())
        self.assertNotIn(b'--use-gl=desktop', self.flags())

    def test_fedora45_auto_old_nvidia_driver_keeps_desktop_gl(self):
        self.set_os_release('fedora', '45')
        self.gpu(0, '0x10de', 'nvidia', '570.86.16')
        result = self.run_mode('auto')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('gpu-mode=nvidia-desktop', result.stderr)
        self.assertIn(b'--use-gl=desktop', self.flags())

    def test_fedora45_hybrid_nvidia_580_keeps_existing_prime_policy(self):
        self.set_os_release('fedora', '45')
        self.gpu(0, '0x8086', 'i915')
        self.gpu(1, '0x10de', 'nvidia', '580.196.07')
        result = self.run_mode('auto')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('gpu-mode=nvidia-desktop', result.stderr)
        self.assertIn(b'--use-gl=desktop', self.flags())

    def test_other_distro_nvidia_580_keeps_desktop_gl(self):
        self.set_os_release('ubuntu', '26.10')
        self.gpu(0, '0x10de', 'nvidia', '580.196.07')
        result = self.run_mode('auto')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('gpu-mode=nvidia-desktop', result.stderr)
        self.assertIn(b'--use-gl=desktop', self.flags())

    def test_fedora45_explicit_desktop_gl_remains_available(self):
        self.set_os_release('fedora', '45')
        self.gpu(0, '0x10de', 'nvidia', '580.196.07')
        result = self.run_mode('nvidia-desktop')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(b'--use-gl=desktop', self.flags())

    def test_explicit_nvidia_uses_angle_gl(self):
        self.gpu(0, '0x10de', 'nvidia', '580.196.07')
        result = self.run_mode('nvidia')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('gpu-mode=nvidia', result.stderr)
        self.assertIn(b'--use-gl=angle', self.flags())
        self.assertIn(b'--use-angle=gl', self.flags())
        self.assertIn(b'--enable-zero-copy', self.flags())
        self.assertIn(b'--ignore-gpu-blocklist', self.flags())
        self.assertNotIn(b'--use-gl=desktop', self.flags())

    def test_auto_retries_angle_after_fatal_desktop_gl_startup(self):
        self.gpu(0, '0x10de', 'nvidia', '580.196.07')
        self.env['FAKE_FAIL_DESKTOP'] = '1'
        result = self.run_mode('auto')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((self.capture / 'count').read_text().strip(), '2')
        self.assertIn(b'--use-gl=desktop', self.flags(1))
        self.assertIn(b'--use-gl=angle', self.flags(2))
        self.assertIn(b'--use-angle=gl', self.flags(2))

    def test_successful_process_does_not_retry_gpu_warning(self):
        # Demonstrates the current blind spot: a CEF fallback can remain silent
        # to the launcher if the process ultimately exits with status zero.
        self.gpu(0, '0x10de', 'nvidia', '580.196.07')
        self.env['FAKE_WARN_ONLY'] = '1'
        result = self.run_mode('auto')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((self.capture / 'count').read_text().strip(), '1')

    def test_auto_intel_selects_mesa_without_nvidia_override(self):
        self.gpu(0, '0x8086', 'i915')
        result = self.run_mode('auto')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('gpu-mode=mesa', result.stderr)
        self.assertIn(b'--use-gl=angle', self.flags())
        self.assertNotIn(b'--ignore-gpu-blocklist', self.flags())

    def test_software_renderer_probe_precedes_nvidia_detection(self):
        self.gpu(0, '0x10de', 'nvidia', '580.196.07')
        self.env['GLX_RENDERER'] = 'OpenGL renderer string: llvmpipe'
        result = self.run_mode('auto')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('gpu-mode=software', result.stderr)
        self.assertIn(b'--disable-gpu', self.flags())


if __name__ == '__main__':
    unittest.main()
