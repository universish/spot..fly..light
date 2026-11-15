"""Fedora 45 desktop identity and icon packaging regression tests."""
import importlib.util
from pathlib import Path
import sys
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
spec = importlib.util.spec_from_file_location(
    'spotify_bootstrap_desktop_test', ROOT / 'bootstrap' / 'spot..fly..light.py'
)
bootstrap = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bootstrap)


class Fedora45DesktopIdentityTests(unittest.TestCase):
    CURRENT = {
        'Kind': 'current',
        'Name': 'spot-fly-light',
        'client_name': 'spotify-client-via-spot-fly-light',
        'client_share': '/usr/share/spot..fly..light-client',
        'command': 'spot..fly..light',
        'icon': 'spot..fly..light',
        'desktop': 'spot..fly..light.desktop',
    }
    ARCHIVE = {
        **CURRENT,
        'Kind': 'archive',
        'Name': 'spot-fly-light-st1.2.63.394-unst1.2.86.502',
        'command': 'spot-fly-light-archive',
        'icon': 'spot-fly-light-archive',
        'desktop': 'spot-fly-light-archive.desktop',
    }

    def release(self, distro='fedora', version='45'):
        return mock.patch.object(
            bootstrap.platform, 'freedesktop_os_release',
            return_value={'ID': distro, 'VERSION_ID': version}
        )

    def test_fedora45_current_desktop_matches_spotify_window_and_icon(self):
        with self.release():
            desktop = bootstrap.client_desktop(self.CURRENT)
        self.assertIn('StartupWMClass=Spotify\n', desktop)
        self.assertIn('Icon=spotify\n', desktop)
        self.assertIn('Exec=spotify %U\n', desktop)
        self.assertIn('MimeType=x-scheme-handler/spotify;\n', desktop)

    def test_fedora44_current_desktop_unchanged(self):
        with self.release(version='44'):
            desktop = bootstrap.client_desktop(self.CURRENT)
        self.assertIn('StartupWMClass=spotify\n', desktop)
        self.assertIn('Icon=spot..fly..light\n', desktop)
        self.assertNotIn('StartupWMClass=Spotify\n', desktop)

    def test_other_distro_current_desktop_unchanged(self):
        with self.release(distro='ubuntu', version='26.10'):
            desktop = bootstrap.client_desktop(self.CURRENT)
        self.assertIn('StartupWMClass=spotify\n', desktop)
        self.assertIn('Icon=spot..fly..light\n', desktop)

    def test_fedora45_archive_keeps_its_unique_icon(self):
        with self.release():
            desktop = bootstrap.client_desktop(self.ARCHIVE)
        self.assertIn('StartupWMClass=spotify\n', desktop)
        self.assertIn('Icon=spot-fly-light-archive\n', desktop)
        self.assertIn('Exec=spot-fly-light-archive %U\n', desktop)
        self.assertNotIn('MimeType=x-scheme-handler/spotify;', desktop)

    def test_fedora45_current_rpm_files_use_new_icon_path(self):
        with self.release(), mock.patch.object(bootstrap, 'helper_layout', return_value=self.CURRENT):
            spec_text = bootstrap.target_spec('1.3.4.258', '6', '2.39')
        self.assertIn('/usr/share/icons/hicolor/*/apps/spotify.png', spec_text)
        self.assertNotIn('/usr/share/icons/hicolor/*/apps/spot..fly..light.png', spec_text)

    def test_fedora44_current_rpm_files_remain_unchanged(self):
        with self.release(version='44'), mock.patch.object(bootstrap, 'helper_layout', return_value=self.CURRENT):
            spec_text = bootstrap.target_spec('1.3.4.258', '6', '2.39')
        self.assertIn('/usr/share/icons/hicolor/*/apps/spot..fly..light.png', spec_text)
        self.assertNotIn('/usr/share/icons/hicolor/*/apps/spotify.png', spec_text)

    def test_os_release_failure_retains_original_behavior(self):
        with mock.patch.object(bootstrap.platform, 'freedesktop_os_release', side_effect=OSError):
            desktop = bootstrap.client_desktop(self.CURRENT)
        self.assertIn('StartupWMClass=spotify\n', desktop)
        self.assertIn('Icon=spot..fly..light\n', desktop)


if __name__ == '__main__':
    unittest.main()
    


