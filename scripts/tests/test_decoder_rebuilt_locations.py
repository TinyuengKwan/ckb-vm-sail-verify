import copy
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import decoder_rebuilt_locations as p


class RebuiltLocationsTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='rebuilt-location-test-')
        self.addCleanup(temporary.cleanup); self.root = Path(temporary.name)

    def test_unknown_root_rejected_before_any_load(self):
        with patch.object(p, 'load') as load, self.assertRaisesRegex(RuntimeError, 'unknown extraction root'):
            p.check_extraction({}, self.root, '../replacement')
        load.assert_not_called()

    def test_missing_v2_inputs_do_not_fall_back(self):
        with patch.object(p, 'load', side_effect=RuntimeError('v2 missing')) as load:
            with self.assertRaisesRegex(RuntimeError, 'v2 missing'): p.configuration(self.root)
        load.assert_called_once_with(self.root)

    def test_fresh_metadata_keeps_every_flag_except_locations(self):
        (self.root / 'llbc').mkdir()
        old = {'has_errors': False, 'charon_version': 'pinned', 'translated': {
            'crate_name': 'outer', 'target_information': {'pointer_size': 64},
            'options': {'sysroot': '/original', 'dest_file': '/old', 'include': ['body'], 'opaque': []}}}
        (self.root / 'llbc/OuterClosedDepsV3.llbc').write_text(json.dumps(old))
        fresh = copy.deepcopy(old); fresh['translated']['options'].update(sysroot=str(self.root / 'sysroot'), dest_file='/new')
        with patch.object(p, 'load', return_value={'payload': str(self.root)}):
            self.assertTrue(p.check_extraction(fresh, self.root)['only_sysroot_location_and_output_path_vary'])
            fresh['translated']['options']['opaque'] = ['decoder']
            with self.assertRaisesRegex(RuntimeError, 'options changed'): p.check_extraction(fresh, self.root)

    def test_environment_has_fresh_caches_and_no_public_flag_bleed(self):
        runtime = {'rustup_home': '/private/rustup', 'opam_root': '/private/opam', 'opam_switch': 'fixed'}
        ambient = {'PATH': '/unreviewed', 'AENEAS_EXTRA': '1', 'RUSTFLAGS': 'bad', 'LD_PRELOAD': 'bad',
                   'CARGO_TARGET_DIR': '/old/cache', 'OPAMROOT': '/wrong', 'LEAN_PATH': '/old/oleans'}
        with patch.dict(os.environ, ambient, clear=True): env = p.environment(self.root, runtime, {'rust_toolchain': 'fixed-nightly'})
        self.assertEqual(env['CARGO_HOME'], str(self.root / 'cargo'))
        self.assertEqual(env['CARGO_TARGET_DIR'], str(self.root / 'cargo-target'))
        self.assertEqual(env['CHARON_CACHE_DIR'], str(self.root / 'charon-cache'))
        self.assertEqual(env['RUSTUP_HOME'], '/private/rustup')
        self.assertEqual(env['OPAMROOT'], '/private/opam')
        for name in ('AENEAS_EXTRA', 'RUSTFLAGS', 'LD_PRELOAD', 'LEAN_PATH'): self.assertNotIn(name, env)

    def test_translator_uses_explicit_opam_and_exact_binary(self):
        runtime = {'opam_bootstrap': {'path': '/pinned/opam'}, 'opam_switch': 'fixed'}
        self.assertEqual(p.translator_command(runtime, '/new/aeneas', ['-checks']),
            ['/pinned/opam', 'exec', '--switch=fixed', '--set-switch', '--', '/new/aeneas', '-checks'])

    def test_runtime_inventory_detects_bytes_permissions_and_extra_files(self):
        (self.root / 'lib').mkdir(); path = self.root / 'lib/file'; path.write_bytes(b'original'); path.chmod(0o644)
        original = p.installation_inventory(self.root, ['lib'])
        path.write_bytes(b'changed'); self.assertNotEqual(p.installation_inventory(self.root, ['lib']), original)
        path.write_bytes(b'original'); path.chmod(0o755)
        self.assertNotEqual(p.installation_inventory(self.root, ['lib']), original)
        path.chmod(0o644); (self.root / 'lib/extra').write_bytes(b'new')
        self.assertNotEqual(p.installation_inventory(self.root, ['lib']), original)

    def test_external_runtime_link_rejected(self):
        (self.root / 'lib').mkdir(); (self.root / 'outside').write_text('outside')
        (self.root / 'lib/link').symlink_to('/etc/passwd')
        with self.assertRaisesRegex(RuntimeError, 'external installed symlink'): p.installation_inventory(self.root, ['lib'])

    def test_empty_runtime_cannot_pass(self):
        with self.assertRaisesRegex(RuntimeError, 'empty installed runtime'): p.installation_inventory(self.root, ['lib'])

    def test_lower_policy_only_migrates_two_proved_map_bodies(self):
        directory = p.ROOT / 'artifacts/decoder-inputs/rebuilt-v2'
        with patch.object(p, 'load', return_value={'payload': str(directory / 'payload')}):
            new = p.lower_policy(directory)
        old = p.read(p.raw.POLICY)
        for key in ('sources', 'scope', 'field_policy_sha256'): self.assertEqual(new[key], old[key])
        expected = copy.deepcopy(old['audit'])
        expected['definitions'].update(p.MAP_DEFINITIONS)
        self.assertEqual(new['audit'], expected)
        self.assertEqual(new['rebuilt_admission']['raw_audit_sha256'], p.MAP_RAW_AUDIT_SHA)
        self.assertNotEqual(new['generated_normalized_sha256'], old['generated_normalized_sha256'])

    def reject_audit_edit(self, edit):
        original_read = p.read
        new = original_read(p.RAW_POLICY)
        edit(new['audit'])
        def changed(path): return new if Path(path) == p.RAW_POLICY else original_read(path)
        with patch.object(p, 'load', return_value={'payload': str(self.root)}), patch.object(p, 'read', side_effect=changed), \
             self.assertRaisesRegex(RuntimeError, 'theorem/type/body/axiom policy changed'):
            p.lower_policy(self.root)

    def test_old_map_fingerprint_cannot_survive_model_migration(self):
        old = p.read(p.raw.POLICY)
        for name in p.MAP_DEFINITIONS:
            with self.subTest(name=name):
                self.reject_audit_edit(lambda audit: audit['definitions'].update({name: old['audit']['definitions'][name]}))

    def test_third_definition_change_is_not_a_map_exception(self):
        self.reject_audit_edit(lambda audit: audit['definitions'].update({'unreviewed.operation': '0'*64}))

    def test_theorem_type_and_axiom_changes_still_rejected(self):
        for key in ('types', 'axioms'):
            with self.subTest(key=key): self.reject_audit_edit(lambda audit: audit.update({key: {}}))

    def test_lower_policy_rejects_weakened_theorem_or_extra_axiom(self):
        original_read = p.read
        new = original_read(p.RAW_POLICY)
        new['audit'] = {'weakened': True}
        def changed(path): return new if Path(path) == p.RAW_POLICY else original_read(path)
        with patch.object(p, 'load', return_value={'payload': str(self.root)}), patch.object(p, 'read', side_effect=changed), \
             self.assertRaisesRegex(RuntimeError, 'theorem/type/body/axiom policy changed'):
            p.lower_policy(self.root)


if __name__ == '__main__':
    unittest.main()
