"""Check the separate spotify.desktop generator without changing Fedora 44."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'src' / 'generate_desktopentry.sh'


class DesktopGeneratorFedora45Tests(unittest.TestCase):
    def produce(self, os_id, version):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            release = root / 'os-release'
            release.write_text(f'ID="{os_id}"\nVERSION_ID="{version}"\n')
            dest = root / 'directory with spaces'
            env = dict(os.environ, SPOT_FLY_LIGHT_OS_RELEASE_FILE=str(release))
            subprocess.run(['bash', str(SCRIPT), str(dest), '1.3.4.258'],
                           env=env, check=True, capture_output=True, text=True)
            return (dest / 'spotify.desktop').read_text()

    def test_fedora45_matches_observed_wm_class(self):
        desktop = self.produce('fedora', '45')
        self.assertIn('StartupWMClass=Spotify\n', desktop)
        self.assertIn('Exec=spotify %U\n', desktop)
        # Icon=spotify-client is intentionally unchanged in this legacy path;
        # icon installation is not shown by this generator.
        self.assertIn('Icon=spotify-client\n', desktop)

    def test_fedora44_remains_unchanged(self):
        self.assertIn('StartupWMClass=spotify\n', self.produce('fedora', '44'))

    def test_other_distros_remain_unchanged(self):
        self.assertIn('StartupWMClass=spotify\n', self.produce('ubuntu', '26.10'))


if __name__ == '__main__':
    unittest.main()
