import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

BUNDLE = Path(__file__).resolve().parent


class InstallerTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='herdr-fix-test-')
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.target = self.root / 'plugin.js'
        self.stock = (BUNDLE / 'stock-herdr-tui-session.js').read_bytes()
        self.patched = (BUNDLE / 'herdr-tui-session.js').read_bytes()
        self.target.write_bytes(self.stock)
        self.target.chmod(0o640)
        self.environment = {**os.environ, 'XDG_STATE_HOME': str(self.root / 'state')}

    def run_helper(self, *arguments):
        return subprocess.run([sys.executable, str(BUNDLE / 'manage.py'), '--target', str(self.target),
                               *arguments], env=self.environment, capture_output=True, text=True)

    def backups(self):
        return list((self.root / 'state/herdr-opencode-v2-fix').glob('*.backup'))

    def test_check_does_not_write(self):
        result = self.run_helper()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.target.read_bytes(), self.stock)
        self.assertEqual(self.backups(), [])

    def test_apply_preserves_mode_and_creates_exact_backup(self):
        result = self.run_helper('--apply')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.target.read_bytes(), self.patched)
        self.assertEqual(self.target.stat().st_mode & 0o777, 0o640)
        self.assertEqual(len(self.backups()), 1)
        self.assertEqual(self.backups()[0].read_bytes(), self.stock)
        self.assertEqual(self.backups()[0].stat().st_mode & 0o777, 0o600)

    def test_apply_is_idempotent(self):
        self.assertEqual(self.run_helper('--apply').returncode, 0)
        self.assertEqual(self.run_helper('--apply').returncode, 0)
        self.assertEqual(len(self.backups()), 1)

    def test_unknown_upstream_file_is_not_overwritten(self):
        newer = self.stock + b'\n// new upstream change\n'
        self.target.write_bytes(newer)
        result = self.run_helper('--apply')
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.target.read_bytes(), newer)
        self.assertEqual(self.backups(), [])

    def test_restore_round_trip(self):
        self.assertEqual(self.run_helper('--apply').returncode, 0)
        result = self.run_helper('--restore', str(self.backups()[0]))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.target.read_bytes(), self.stock)

    def test_restore_does_not_replace_a_newer_upstream_file(self):
        self.assertEqual(self.run_helper('--apply').returncode, 0)
        newer = self.patched + b'\n// upstream changed again\n'
        self.target.write_bytes(newer)
        result = self.run_helper('--restore', str(self.backups()[0]))
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.target.read_bytes(), newer)

    def test_invalid_backup_is_not_restored(self):
        self.assertEqual(self.run_helper('--apply').returncode, 0)
        invalid = self.root / 'invalid.backup'
        invalid.write_bytes(b'not the plugin')
        self.assertNotEqual(self.run_helper('--restore', str(invalid)).returncode, 0)
        self.assertEqual(self.target.read_bytes(), self.patched)

    def test_symlinks_are_not_replaced(self):
        actual = self.root / 'actual.js'
        self.target.rename(actual)
        self.target.symlink_to(actual)
        self.assertNotEqual(self.run_helper('--apply').returncode, 0)
        self.assertTrue(self.target.is_symlink())
        self.assertEqual(actual.read_bytes(), self.stock)


if __name__ == '__main__':
    unittest.main()
