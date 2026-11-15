"""Fedora 45-only Fontconfig XML compatibility regression tests."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
import fontconfig_runtime as fc


class Fedora45FontconfigTests(unittest.TestCase):
    @staticmethod
    def os_release(os_id, version):
        return patch.object(fc.platform, 'freedesktop_os_release',
                            return_value={'ID': os_id, 'VERSION_ID': version})

    def test_fedora45_unbound_xsi_nil_round_trip(self):
        source = b'<fontconfig><const xsi:nil="true"/></fontconfig>'
        with self.os_release('fedora', '45'):
            self.assertTrue(fc._is_fedora_45())
            root = fc._parse_fontconfig_xml(source, fedora_45=fc._is_fedora_45())
            rendered = fc._serialize_fontconfig_xml(root, fedora_45=True)
        self.assertIn(b'xsi:nil="true"', rendered)
        self.assertNotIn(fc._F45_XSI_NIL_TEMP, rendered)
        self.assertEqual(root.tag, 'fontconfig')

    def test_fedora44_and_other_distros_retain_strict_parsing(self):
        source = b'<fontconfig><const xsi:nil="true"/></fontconfig>'
        for system, release in (('fedora', '44'), ('fedora', '46'),
                                ('ubuntu', '24.04'), ('opensuse-tumbleweed', '20261115')):
            with self.subTest(system=system, release=release):
                with self.os_release(system, release):
                    self.assertFalse(fc._is_fedora_45())
                    with self.assertRaises(ET.ParseError):
                        fc._parse_fontconfig_xml(source, fedora_45=fc._is_fedora_45())

    def test_other_platforms_serialize_identically(self):
        root = ET.fromstring(b'<fontconfig><dir>/usr/share/fonts</dir></fontconfig>')
        legacy = ET.tostring(root, encoding='utf-8', xml_declaration=True)
        self.assertEqual(fc._serialize_fontconfig_xml(root, fedora_45=False), legacy)

    def test_fedora45_does_not_mask_other_invalid_xml(self):
        with self.assertRaises(ET.ParseError):
            fc._parse_fontconfig_xml(b'<fontconfig><unclosed>', fedora_45=True)

    def test_fedora45_rejects_marker_collision(self):
        with self.assertRaises(ValueError):
            fc._parse_fontconfig_xml(
                b'<fontconfig __spot_fly_light_xsi_nil__="1"/>', fedora_45=True)

    def test_os_release_read_failure_is_not_fedora45(self):
        with patch.object(fc.platform, 'freedesktop_os_release', side_effect=OSError):
            self.assertFalse(fc._is_fedora_45())

    def test_fedora45_private_snapshot_has_all_includes(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            source = home / 'fonts.conf'
            included = home / 'conf.d'
            included.mkdir()
            (included / '48-guessfamily.conf').write_bytes(
                b'<fontconfig><match target="pattern"><test name="genericfamily">'
                b'<const xsi:nil="true"/></test></match></fontconfig>')
            source.write_bytes(
                b'<fontconfig><include prefix="relative">conf.d</include>'
                b'<cachedir>/var/cache/fontconfig</cachedir>'
                b'<dir>/usr/share/fonts</dir></fontconfig>')
            env = {'HOME': str(home)}
            record = {'SHA256': 'a' * 64, 'Channel': 'stable'}
            profile = {'Name': 'spot-fly-light'}
            with self.os_release('fedora', '45'):
                child, info = fc.prepare_fontconfig(
                    env, record, profile, source_config=source,
                    cache_root=home / 'cache-root')
            config = Path(child['FONTCONFIG_FILE']).parent
            manifest = json.loads((config.parent / 'source.json').read_text())
            filenames = set(manifest['documents'])
            self.assertEqual(manifest['schema'], 2)
            self.assertEqual(len(filenames), 2)
            self.assertEqual(filenames, {p.name for p in config.glob('*.conf')})
            main = (config / Path(child['FONTCONFIG_FILE']).name).read_bytes()
            self.assertNotIn(b'/var/cache/fontconfig', main)
            self.assertIn(str(info['Cache']).encode(), main)
            for filename in filenames:
                data = (config / filename).read_bytes()
                self.assertNotIn(fc._F45_XSI_NIL_TEMP, data)
                if b'xsi:nil' in data:
                    self.assertIn(b'xsi:nil="true"', data)
                for include in fc._parse_fontconfig_xml(data, fedora_45=True).iter('include'):
                    if include.text and include.text.startswith(str(config)):
                        self.assertTrue(Path(include.text).is_file(), include.text)

    def test_fedora44_private_snapshot_schema_unchanged(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            source = home / 'fonts.conf'
            source.write_bytes(b'<fontconfig><dir>/usr/share/fonts</dir></fontconfig>')
            with self.os_release('fedora', '44'):
                child, _ = fc.prepare_fontconfig(
                    {'HOME': str(home)}, {'SHA256': 'a' * 64},
                    {'Name': 'spot-fly-light'}, source_config=source,
                    cache_root=home / 'cache-root')
            manifest = json.loads((Path(child['FONTCONFIG_FILE']).parent.parent / 'source.json').read_text())
            self.assertEqual(manifest['schema'], 1)


if __name__ == '__main__':
    unittest.main()
