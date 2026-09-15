import os
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from probes import probe_isolated_rust_lean as probe


class InstallationTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory(prefix='tool-install-test-')
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)

    def binary(self):
        binary = self.root / 'rustup/toolchains/fixed/bin/rustc'
        binary.parent.mkdir(parents=True)
        binary.write_bytes(b'synthetic fixture, never executed')
        binary.chmod(0o755)
        return binary

    def test_private_homes_and_ambient_overrides_removed(self):
        original = {key: 'ambient' for key in probe.STRIP}
        original.update(HOME='/unchanged-user-home', PATH='/bootstrap/path')
        env = probe.environment(self.root, original)
        self.assertEqual(env['HOME'], original['HOME'])
        self.assertEqual(env['PATH'], original['PATH'])
        for key, name in probe.HOMES.items(): self.assertEqual(env[key], str(self.root / name))
        for key in probe.STRIP: self.assertNotIn(key, env)
        self.assertIn('RUSTFLAGS', original)

    def test_fresh_homes_created(self):
        probe.create_homes(self.root)
        for name in probe.HOMES.values(): self.assertEqual(list((self.root / name).iterdir()), [])

    def test_existing_home_refused_before_any_creation(self):
        (self.root / 'cargo').mkdir()
        with self.assertRaisesRegex(RuntimeError, 'absent'): probe.create_homes(self.root)
        self.assertFalse((self.root / 'rustup').exists())

    def test_broken_home_link_refused(self):
        (self.root / 'elan').symlink_to(self.root / 'absent')
        with self.assertRaisesRegex(RuntimeError, 'absent'): probe.create_homes(self.root)

    def test_binary_inside_private_tree_and_hash(self):
        binary = self.binary()
        self.assertEqual(probe.installed_binary(binary, self.root / 'rustup', probe.sha(binary)), binary)

    def test_wrong_binary_hash_refused(self):
        binary = self.binary()
        with self.assertRaisesRegex(RuntimeError, 'pinned'): probe.installed_binary(binary, self.root / 'rustup', '0' * 64)

    def test_external_compiler_refused(self):
        binary = self.binary()
        with self.assertRaisesRegex(RuntimeError, 'escaped'): probe.installed_binary(binary, self.root / 'elan', probe.sha(binary))

    def test_nonexecutable_refused(self):
        binary = self.binary()
        binary.chmod(0o644)
        with self.assertRaisesRegex(RuntimeError, 'executable'): probe.installed_binary(binary, self.root / 'rustup', probe.sha(binary))

    def test_hardlinked_compiler_refused(self):
        binary = self.binary()
        os.link(binary, self.root / 'shared')
        with self.assertRaisesRegex(RuntimeError, 'hardlinked'): probe.installed_binary(binary, self.root / 'rustup', probe.sha(binary))

    def test_rust_commit_release_and_host_checked(self):
        pin = {'commit': 'exact-commit', 'release': 'fixed'}
        text = 'commit-hash: exact-commit\nrelease: fixed\nhost: ' + probe.HOST
        probe.rust_identity(text, pin)
        for word in ['exact-commit', 'fixed', probe.HOST]:
            with self.subTest(word=word), self.assertRaises(RuntimeError): probe.rust_identity(text.replace(word, 'wrong'), pin)

    def test_component_inventory_exact(self):
        base = ['cargo', 'rustc', 'rust-std', 'rustc-dev', 'llvm-tools']
        text = '\n'.join(name + '-' + probe.HOST for name in base) + '\nrust-src'
        extra = ['llvm-tools', 'rust-src', 'rustc-dev']
        probe.components(text, extra)
        for changed in [text + '\nextra', text + '\nrust-src', text.replace('\nrust-src', '')]:
            with self.assertRaises(RuntimeError): probe.components(changed, extra)

    def test_inventory_includes_library_bytes(self):
        self.binary()
        first = probe.inventory(self.root / 'rustup')
        lib = self.root / 'rustup/toolchains/fixed/lib'
        lib.mkdir()
        (lib / 'support').write_text('library')
        self.assertNotEqual(probe.inventory(self.root / 'rustup')['sha256'], first['sha256'])

    def test_internal_symlink_inventoried(self):
        binary = self.binary()
        binary.with_name('proxy').symlink_to('rustc')
        self.assertEqual(probe.inventory(self.root / 'rustup')['files']['toolchains/fixed/bin/proxy'], {'symlink':'rustc'})

    def test_external_installed_symlink_refused(self):
        binary = self.binary()
        external = self.root / 'outside'
        external.write_text('external')
        binary.with_name('proxy').symlink_to(external)
        with self.assertRaisesRegex(RuntimeError, 'external'): probe.inventory(self.root / 'rustup')

    def test_empty_inventory_refused(self):
        with self.assertRaisesRegex(RuntimeError, 'empty'): probe.inventory(self.root)


if __name__ == '__main__':
    unittest.main()
