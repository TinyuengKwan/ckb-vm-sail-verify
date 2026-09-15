import copy
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import decoder_rebuilt_inputs as p


class AdmissionTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='rebuilt-admission-test-')
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)

    def fixture(self):
        payload = self.root / 'payload'; payload.mkdir()
        policy = {'qualification': {}, 'known_regression_disposition':
                  {'ui_summary': {'full_upstream_suite_passed': False}, 'diagnostic_counts': {'identical': 12}}}
        for label in sorted(p.QUALIFICATIONS):
            name = 'qualification/' + label + '.json'; path = payload / name
            path.parent.mkdir(exist_ok=True)
            value = {'status': 'scoped-fixture'}
            if label == 'charon_ui': value['summary'] = policy['known_regression_disposition']['ui_summary']
            if label == 'charon_diagnostics':
                value.update(counts={'identical': 12}, historical_replay={'historical_classifier_source_identity_matched': False})
            path.write_text(json.dumps(value)); path.chmod(0o644)
            policy['qualification'][label] = {'file': name, 'status': 'scoped-fixture'}
        (payload / 'bin').mkdir(); (payload / 'bin/tool').write_bytes(b'fixture'); (payload / 'bin/tool').chmod(0o755)
        files = {f.relative_to(payload).as_posix(): {'sha256': p.sha(f), 'bytes': f.stat().st_size,
                 'mode': f.stat().st_mode & 0o777} for f in payload.rglob('*') if f.is_file()}
        catalogue = {'files': files, 'source_commits': {}, 'boundaries': {'tool_adopted': False}}
        manifest = {'schema_version': 1, 'kind': 'rebuilt-decoder-candidate-inputs', **copy.deepcopy(catalogue)}
        (payload / 'package.json').write_text(json.dumps(manifest)); (payload / 'package.json').chmod(0o644)
        policy['manifest_sha256'] = p.sha(payload / 'package.json')
        return payload, policy, catalogue, manifest

    def test_real_policy_preserves_scope_and_limits(self):
        policy, catalogue = p.load_policy()
        self.assertEqual(policy['configuration'], p.CONFIGURATION)
        self.assertEqual(len(catalogue['files']), 92)
        self.assertEqual(len(policy['source_variants']), 5)
        self.assertTrue(all(policy[key] is False for key in p.BOUNDARIES))

    def test_policy_rejects_gate_claim_or_weaker_scope(self):
        policy, catalogue = p.load_policy()
        changes = [('main_gate_adopted', True), ('proof_check_claimed', 0), ('limitations', []),
                   ('configuration', {**policy['configuration'], 'mop': 0}), ('source_variants', {})]
        for key, value in changes:
            changed = copy.deepcopy(policy); changed[key] = value
            with self.subTest(key=key), patch.object(p, 'read', side_effect=[changed, catalogue]), self.assertRaises(RuntimeError):
                p.load_policy()

    def test_duplicate_json_keys_rejected(self):
        path = self.root / 'policy.json'; path.write_text('{"status":"approved","status":"unknown"}')
        with self.assertRaisesRegex(RuntimeError, 'duplicate JSON key'): p.read(path)

    def test_safe_names_reject_escape_and_ambiguous_spellings(self):
        for name in ('../escape', '/absolute', 'a/./b', 'a//b', '.git/config', 'a\\b', ''):
            with self.subTest(name=name), self.assertRaises(RuntimeError): p.safe_name(name)
        self.assertEqual(p.safe_name('sources/charon.bundle'), 'sources/charon.bundle')

    def test_historical_candidate_payload_can_be_separately_admitted(self):
        payload, policy, catalogue, manifest = self.fixture()
        self.assertEqual(p.verify_payload(payload, policy, catalogue), manifest)
        self.assertIs(p.read(payload / 'package.json')['boundaries']['tool_adopted'], False)

    def test_manifest_cannot_self_approve_changed_tool(self):
        payload, policy, catalogue, manifest = self.fixture()
        (payload / 'bin/tool').write_bytes(b'changed')
        manifest['files']['bin/tool']['sha256'] = p.sha(payload / 'bin/tool')
        (payload / 'package.json').write_text(json.dumps(manifest))
        policy['manifest_sha256'] = p.sha(payload / 'package.json')
        with self.assertRaisesRegex(RuntimeError, 'external catalogue differs'):
            p.verify_payload(payload, policy, catalogue)

    def test_no_v1_or_boolean_schema_fallback(self):
        payload, policy, catalogue, manifest = self.fixture()
        for key, value in [('kind', 'public-decoder-inputs'), ('schema_version', True)]:
            changed = dict(manifest); changed[key] = value
            (payload / 'package.json').write_text(json.dumps(changed))
            policy['manifest_sha256'] = p.sha(payload / 'package.json')
            with self.assertRaisesRegex(RuntimeError, 'unknown candidate payload'):
                p.verify_payload(payload, policy, catalogue)

    def test_missing_extra_or_changed_permissions_fail(self):
        payload, policy, catalogue, _ = self.fixture()
        (payload / 'bin/tool').chmod(0o644)
        with self.assertRaises(RuntimeError): p.verify_payload(payload, policy, catalogue)
        (payload / 'bin/tool').chmod(0o755)
        (payload / 'unexpected').write_bytes(b'extra')
        with self.assertRaises(RuntimeError): p.verify_payload(payload, policy, catalogue)
        (payload / 'unexpected').unlink(); (payload / 'bin/tool').unlink()
        with self.assertRaises(RuntimeError): p.verify_payload(payload, policy, catalogue)

    def test_payload_hardlink_rejected(self):
        payload, policy, catalogue, _ = self.fixture()
        os.link(payload / 'bin/tool', self.root / 'external')
        with self.assertRaisesRegex(RuntimeError, 'hardlinked'): p.verify_payload(payload, policy, catalogue)

    def test_parent_symlink_rejected(self):
        real = self.root / 'real'; real.mkdir(); (real / 'file').write_text('input')
        link = self.root / 'link'; link.symlink_to(real, target_is_directory=True)
        with self.assertRaisesRegex(RuntimeError, 'linked input'): p.regular(link / 'file')

    def test_archive_identity_checked_before_creating_destination(self):
        archive = self.root / 'bad.tar.gz'; archive.write_bytes(b'wrong archive')
        destination = self.root / 'installed'
        with self.assertRaisesRegex(RuntimeError, 'archive identity'): p.install(archive, destination)
        self.assertFalse(destination.exists())

    def test_existing_destination_is_never_overwritten(self):
        with patch.object(p, 'load_policy') as load, self.assertRaisesRegex(RuntimeError, 'already exists'):
            p.install(self.root / 'unused', self.root)
        load.assert_not_called()

    def test_unsafe_tar_rejected_before_creating_destination(self):
        archive = self.root / 'unsafe.tar.gz'
        with tarfile.open(archive, 'w:gz') as stream:
            member = tarfile.TarInfo('../escape'); member.mode = 0o644; member.size = 1
            stream.addfile(member, io.BytesIO(b'x'))
        destination = self.root / 'installed'
        with patch.object(p, 'load_policy', return_value=({'archive_sha256': p.sha(archive)}, {})), self.assertRaises(RuntimeError):
            p.install(archive, destination)
        self.assertFalse(destination.exists())

    def test_receipt_is_not_an_authority_or_required_input(self):
        (self.root / 'install-report.json').write_text('{"proof_check_claimed":true}')
        with patch.object(p, 'load_policy', return_value=({}, {})), \
             patch.object(p, 'verify_payload', return_value={'files': {}}), \
             patch.object(p, 'verify_sources', return_value={}), patch.object(p, 'sha', return_value='fixed'):
            result = p.load(self.root)
        self.assertIs(result['scoped_inputs_admitted'], True)
        self.assertIs(result['proof_check_claimed'], False)
        self.assertIs(result['main_gate_adopted'], False)

    def test_real_git_inventory_detects_ignored_diff_and_index_change(self):
        def git(*args):
            return subprocess.check_output(['git', '-C', str(self.root), '-c', 'user.name=Fixture',
                                           '-c', 'user.email=fixture@example.invalid', *args], stderr=subprocess.PIPE)
        git('init'); (self.root / 'source').write_text('original\n')
        git('add', 'source'); git('commit', '-m', 'fixture')
        original = p.source_inventory(self.root)
        git('update-index', '--assume-unchanged', 'source'); (self.root / 'source').write_text('changed\n')
        self.assertEqual(git('diff'), b'')
        self.assertNotEqual(p.source_inventory(self.root), original)
        git('update-index', '--no-assume-unchanged', 'source'); git('add', 'source')
        with self.assertRaisesRegex(RuntimeError, 'index or untracked'): p.source_inventory(self.root)


if __name__ == '__main__':
    unittest.main()
