import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from probes import probe_rebuilt_sail_cpp as p


class RebuiltSailCppTests(unittest.TestCase):
    def test_configuration_merge_disables_defaults_then_applies_override(self):
        defaults = {'extensions': {'A': {'supported': True}, 'B': {'supported': True},
                                   'nested': [{'supported': True}]}, 'platform': {'x': 1, 'y': 2}}
        override = {'extensions': {'B': {'supported': True}}, 'platform': {'x': 3}}
        result = subprocess.run(['/usr/bin/jq', '-s', p.MERGE],
                                input=json.dumps(defaults) + '\n' + json.dumps(override),
                                text=True, capture_output=True, check=True)
        self.assertEqual(json.loads(result.stdout),
                         {'extensions': {'A': {'supported': False}, 'B': {'supported': True},
                                         'nested': [{'supported': False}]}, 'platform': {'x': 3, 'y': 2}})

    def test_environment_cannot_redirect_compiler_cache_or_support(self):
        hostile = {key: '/bad' for key in ('CMAKE_TOOLCHAIN_FILE', 'CC', 'CXX', 'CFLAGS', 'CXXFLAGS',
                   'CPPFLAGS', 'LDFLAGS', 'AR', 'RANLIB', 'LD_PRELOAD', 'LD_LIBRARY_PATH', 'CPATH',
                   'COMPILER_PATH', 'GCC_EXEC_PREFIX', 'CCACHE_DIR', 'SCCACHE_DIR', 'MAKEFLAGS',
                   'GIT_CONFIG_COUNT', 'SAIL_DIR', 'SAIL_PLUGIN_DIR', 'BASH_ENV', 'CONFIG_SITE')}
        with patch.dict(os.environ, hostile):
            env = p.environment(Path('/fresh'), Path('/sail'))
        for key in hostile.keys() - {'SAIL_DIR', 'SAIL_PLUGIN_DIR'}:
            self.assertNotIn(key, env)
        self.assertEqual(env['SAIL_DIR'], '/sail/share/sail')
        self.assertEqual(env['SAIL_PLUGIN_DIR'], '/sail/share/libsail/plugins')
        self.assertEqual(env['PATH'], '/usr/bin:/bin')

    def test_generated_requires_all_three_real_single_link_files(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            with self.assertRaises(RuntimeError):
                p.generated(root)
            for name in p.GENERATED:
                (root / name).write_text(name)
            self.assertEqual(set(p.generated(root)), set(p.GENERATED))
            (root / p.GENERATED[0]).unlink()
            (root / p.GENERATED[0]).symlink_to(root / p.GENERATED[1])
            with self.assertRaisesRegex(RuntimeError, 'linked'):
                p.generated(root)

    def test_generated_rejects_hardlinks(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for name in p.GENERATED:
                (root / name).write_text(name)
            os.link(root / p.GENERATED[0], root / 'old-cache')
            with self.assertRaisesRegex(RuntimeError, 'linked'):
                p.generated(root)

    def test_install_check_cannot_accept_only_a_binary_hash(self):
        report = {'prefix': '/sail', 'installed_closure': {'expected': True}}
        with patch.object(p.model.install.rocq, 'installed_inventory', return_value={}):
            with self.assertRaisesRegex(RuntimeError, 'Sail install drift'):
                p.check_install(report)

    def test_install_checks_opam_support_and_compiler_source(self):
        report = {'prefix': '/sail', 'installed_closure': {'a': 1}, 'opam_root': '/opam', 'switch': 's',
                  'opam_installed_closure': {'b': 2}, 'source': '/source', 'source_after': {'c': 3}}
        with patch.object(p.model.install.rocq, 'installed_inventory', side_effect=[{'a': 1}, {}]):
            with self.assertRaisesRegex(RuntimeError, 'OPAM closure'):
                p.check_install(report)
        with patch.object(p.model.install.rocq, 'installed_inventory', side_effect=[{'a': 1}, {'b': 2}]), \
             patch.object(p.model.install, 'check_source', return_value={}):
            with self.assertRaisesRegex(RuntimeError, 'compiler source'):
                p.check_install(report)

    def test_failed_preflight_never_claims_compile_or_release(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            with patch.object(p, 'sha', return_value='drift'), patch('builtins.print'):
                self.assertEqual(p.run(root), 1)
            report = json.loads((root / 'report.json').read_text())
        self.assertEqual(report['status'], 'failed')
        self.assertEqual(report['stages'], [])
        for key in ('cpp_compiled', 'emulator_config_executed', 'runtime_differential_executed',
                    'tool_adopted', 'policy_changed', 'generated_sources_edited', 'clean_room_claimed', 'release_claimed'):
            self.assertIs(report[key], False)


if __name__ == '__main__':
    unittest.main()
