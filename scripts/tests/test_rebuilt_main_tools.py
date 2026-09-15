"""Candidate main tool integration fails closed on identity and path drift."""
import copy
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import rebuilt_main_tools as tools


class MainToolsTests(unittest.TestCase):
    def setUp(self):
        self.policy = {'main_toolchain': tools.PROFILE, 'tool_binaries': tools.BINARIES.copy(),
                       'translator_versions': tools.VERSIONS.copy(), 'lean_toolchain': tools.TOOLCHAIN,
                       'aeneas_lean_sources_sha256': tools.SUPPORT}

    def test_explicit_complete_identity(self):
        before = copy.deepcopy(self.policy)
        tools.policy_identity(self.policy)
        self.assertEqual(self.policy, before)

    def test_no_implicit_legacy_fallback(self):
        for profile in (None, 'legacy', '', True):
            with self.subTest(profile=profile), self.assertRaisesRegex(RuntimeError, 'explicitly selected'):
                tools.policy_identity({**self.policy, 'main_toolchain': profile})

    def test_each_old_or_missing_binary_rejected(self):
        for name in tools.BINARIES:
            policy = copy.deepcopy(self.policy)
            policy['tool_binaries'][name] = 'old'
            with self.subTest(binary=name), self.assertRaisesRegex(RuntimeError, 'binary policy'):
                tools.policy_identity(policy)

    def test_versions_and_lean_support_rejected(self):
        for key, value in [('translator_versions', {}), ('lean_toolchain', 'same-label-other-install'),
                           ('aeneas_lean_sources_sha256', 'new')]:
            with self.subTest(key=key), self.assertRaises(RuntimeError):
                tools.policy_identity({**self.policy, key: value})

    def test_profile_checked_before_loading_any_installation(self):
        with patch.object(tools.locations, 'configuration') as configuration:
            with self.assertRaises(RuntimeError): tools.resolve(Path('/unused'), {})
            configuration.assert_not_called()

    def test_lean_rehash_not_merely_version(self):
        report = {'private_homes': {'ELAN_HOME': '/private'},
                  'installed_closures': {'elan': {'sha256': tools.LEAN_CLOSURE, 'files': {}}}}
        with patch.object(tools.locations, 'installation_inventory', return_value={}) as inventory:
            with self.assertRaisesRegex(RuntimeError, 'installation drift'):
                tools.lean_install(report)
            inventory.assert_called_once_with(Path('/private'), ['toolchains'])

    def test_wrong_lean_closure_rejected_before_read(self):
        report = {'private_homes': {'ELAN_HOME': '/private'},
                  'installed_closures': {'elan': {'sha256': 'different'}}}
        with patch.object(tools.locations, 'installation_inventory') as inventory:
            with self.assertRaisesRegex(RuntimeError, 'unreviewed Lean'):
                tools.lean_install(report)
            inventory.assert_not_called()

    def test_cmake_compiler_and_source_exact(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            cache = root / 'deps/sail-riscv/build/CMakeCache.txt'
            cache.parent.mkdir(parents=True)
            good = 'CMAKE_HOME_DIRECTORY:INTERNAL=' + str(root / 'deps/sail-riscv') + '\nSAIL_BIN:FILEPATH=/new/sail\n'
            cache.write_text(good)
            tools.cmake_compiler(root, Path('/new/sail'))
            for data in (good.replace('/new/sail', '/old/sail'), good.replace('deps/sail-riscv', 'wrong'),
                         good + 'SAIL_BIN:FILEPATH=/new/sail\n'):
                cache.write_text(data)
                with self.subTest(data=data), self.assertRaises(RuntimeError):
                    tools.cmake_compiler(root, Path('/new/sail'))

    def test_missing_cmake_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(RuntimeError, 'cache missing'):
                tools.cmake_compiler(Path(directory), Path('/new/sail'))

    def test_sail_report_rejected_before_installation_scan(self):
        with patch.object(tools, 'sha', return_value='wrong'), \
             patch.object(tools.locations, 'installation_inventory') as inventory:
            with self.assertRaisesRegex(RuntimeError, 'report drift'):
                tools.sail_install(Path('/unused'))
            inventory.assert_not_called()

    def test_production_import_closure_is_pinned_without_historical_probes(self):
        import generate_rebuilt_rust
        root = Path(__file__).resolve().parents[2]
        # These modules form the actual ordinary import closure; other test
        # runner modules may also be loaded and are outside this assertion.
        for module in (tools, generate_rebuilt_rust, generate_rebuilt_rust.extraction,
                       tools.locations, tools.locations.admitted, tools.locations.legacy,
                       tools.snapshot, tools.proof, generate_rebuilt_rust.transaction):
            self.assertIn(str(Path(module.__file__).resolve().relative_to(root)), tools.SOURCES)
        self.assertFalse(any('/probes/' in name for name in tools.SOURCES))

    def test_environment_fixed_lean_sail_and_base_tools(self):
        runtime = {'rustup_home': '/private/rust', 'opam_root': '/private/opam', 'opam_switch': 'fixed'}
        binaries = {name: Path('/base') / name for name in ('charon', 'aeneas')}
        dirty = {'LEAN_PATH': '/old', 'LEAN_NUM_THREADS': '128', 'ELAN_HOME': '/old',
                 'SAIL_DIR': '/old', 'SAIL_PLUGIN_DIR': '/old', 'AENEAS_RELAXED': '1',
                 'PATH': '/old', 'BASH_ENV': '/old', 'CXXFLAGS': '-bad', 'LD_PRELOAD': '/old',
                 'RUSTC_WRAPPER': '/old', 'CARGO_TARGET_DIR': '/old'}
        with patch.dict(tools.os.environ, dirty, clear=True):
            env = tools.environment(Path('/new'), runtime, {'rust_toolchain': 'fixed-nightly'},
                                    Path('/sail'), Path('/elan'), Path('/lean'), Path('/support'), binaries)
        for name in ('LEAN_PATH', 'AENEAS_RELAXED', 'BASH_ENV', 'CXXFLAGS', 'LD_PRELOAD', 'RUSTC_WRAPPER'):
            self.assertNotIn(name, env)
        expected = {'PATH': '/lean/bin:/sail/bin:/usr/bin:/bin', 'ELAN_HOME': '/elan',
                    'SAIL_PLUGIN_DIR': '/sail/share/libsail/plugins', 'AENEAS_HOME': '/support',
                    'AENEAS': '/base/aeneas', 'CHARON': '/base/charon', 'LEAN_NUM_THREADS': '8',
                    'CARGO_TARGET_DIR': '/new/artifacts/rebuilt-main-runtime/cargo-target'}
        for key, value in expected.items(): self.assertEqual(env[key], value)


if __name__ == '__main__':
    unittest.main()
