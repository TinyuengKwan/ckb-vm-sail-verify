"""Recorder regressions; temporary fixtures are NOT production generation evidence."""
import copy
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import record_generation as recorder
import generated_output_inventory as inventory
import check_proof
import rebuilt_main_tools


class RecorderTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='generation-record-test-')
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.parent = self.root / 'artifacts/generation-runs'
        self.parent.mkdir(parents=True)
        (self.root / recorder.PARENT).mkdir()
        self.out = self.parent / 'run'
        self.out.mkdir()

    def test_fixed_recipe_uses_current_rust_and_both_sail_backends(self):
        rows = recorder.recipe()
        self.assertEqual([row[0] for row in rows], ['sail-config', 'generate-rust',
                         'generate-sail-lean', 'generate-sail-rocq'])
        self.assertEqual(rows[0][1], ['/usr/bin/make', 'sail-config'])
        self.assertEqual(rows[1][1], [sys.executable, 'scripts/generate_rebuilt_rust.py'])
        self.assertEqual([row[1][-1] for row in rows[2:]], ['lean', 'rocq'])

    def test_output_must_be_new_and_in_fixed_parent(self):
        path = recorder.new_output(self.parent / 'new', self.root)
        self.assertTrue(path.is_dir())
        with self.assertRaisesRegex(RuntimeError, 'already exists'):
            recorder.new_output(path, self.root)
        with self.assertRaisesRegex(RuntimeError, 'direct child'):
            recorder.new_output(self.root / 'not-evidence', self.root)

    def test_output_dangling_symlink_is_rejected(self):
        path = self.parent / 'link'
        path.symlink_to(self.parent / 'absent')
        with self.assertRaisesRegex(RuntimeError, 'already exists'):
            recorder.new_output(path, self.root)
        self.assertFalse((self.parent / 'absent').exists())

    def test_output_ancestor_link_is_rejected(self):
        link = self.root / 'alias'
        link.symlink_to(self.parent)
        with self.assertRaisesRegex(RuntimeError, 'linked directory'):
            recorder.new_output(link / 'run', self.root)

    def test_parent_listing_does_not_follow_link(self):
        path = self.root / recorder.PARENT
        path.rmdir()
        path.symlink_to(self.parent)
        with self.assertRaisesRegex(RuntimeError, 'linked directory'):
            recorder.parent_names(self.root)

    def test_concurrent_recorders_are_rejected(self):
        with recorder.recording_lock(self.root):
            with self.assertRaises(BlockingIOError):
                recorder.recording_lock(self.root)
        with recorder.recording_lock(self.root):
            pass

    def test_recording_lock_symlink_is_rejected(self):
        (self.parent / '.record-generation.lock').symlink_to(self.root / 'no-target')
        with self.assertRaises(OSError):
            recorder.recording_lock(self.root)
        self.assertFalse((self.root / 'no-target').exists())

    def snapshot(self):
        return inventory.capture(self.root, recorder.EXTRAS)

    def test_new_staging_has_absence_proof_without_rewriting_original(self):
        before = self.snapshot()
        preserved = copy.deepcopy(before)
        expanded, added = recorder.expand_before(before, ['old'], ['old', recorder.PREFIX + 'abc'])
        self.assertEqual(before, preserved)
        name = recorder.PARENT + '/' + recorder.PREFIX + 'abc'
        self.assertEqual(added, [name])
        self.assertIsNone(expanded['entries'][name])
        self.assertNotIn(name, before['entries'])
        inventory.validate(expanded)

    def test_existing_staging_never_gets_fabricated_empty_baseline(self):
        name = recorder.PREFIX + 'old'
        before = self.snapshot()
        expanded, added = recorder.expand_before(before, [name], [name])
        self.assertEqual(expanded, before)
        self.assertEqual(added, [])

    def test_unknown_added_sibling_is_not_silently_filtered(self):
        with self.assertRaisesRegex(RuntimeError, 'unclassified'):
            recorder.expand_before(self.snapshot(), [], ['unrelated-job'])

    def test_deleted_sibling_is_rejected(self):
        with self.assertRaisesRegex(RuntimeError, 'disappeared'):
            recorder.expand_before(self.snapshot(), ['old'], [])

    def test_bad_parent_listings_are_rejected(self):
        for earlier, later in [(['b', 'a'], ['b', 'a']), ([], ['a', 'a']),
                               ([], [recorder.PREFIX]), ([], [recorder.PREFIX + '../escape'])]:
            with self.subTest(earlier=earlier, later=later), self.assertRaises(RuntimeError):
                recorder.expand_before(self.snapshot(), earlier, later)

    def execute(self, payload, timeout=10):
        return recorder.command(self.out, 'fixture', [sys.executable, '-c', payload],
                                {'PATH': '/usr/bin:/bin'}, timeout, cwd=self.root)

    def test_actual_child_stdout_stderr_and_terminal_record(self):
        row = self.execute("import sys; print('out'); print('err', file=sys.stderr)")
        self.assertEqual(row['status'], 'completed')
        self.assertEqual(row['exit_code'], 0)
        self.assertEqual(row['log_sha256'], recorder.sha(self.out / row['log']))
        self.assertEqual(set((self.out / row['log']).read_text().splitlines()), {'out', 'err'})
        self.assertEqual(json.loads((self.out / 'fixture-finished.json').read_text()), row)
        self.assertIn('pid', json.loads((self.out / 'fixture-process.json').read_text()))

    def test_nonzero_child_keeps_raw_log_and_exit(self):
        row = self.execute("print('partial', flush=True); raise SystemExit(7)")
        self.assertEqual(row['status'], 'command_failed')
        self.assertEqual(row['exit_code'], 7)
        self.assertEqual((self.out / row['log']).read_text(), 'partial\n')

    def test_timeout_is_distinct_from_ordinary_nonzero_exit(self):
        row = self.execute("import time; print('partial', flush=True); time.sleep(30)", timeout=1)
        self.assertEqual(row['status'], 'execution_error')
        self.assertEqual(row['error_type'], 'TimeoutExpired')
        self.assertIsNone(row['exit_code'])
        self.assertEqual(row['termination_returncode'], -9)
        self.assertIn('partial', (self.out / row['log']).read_text())

    def test_launch_error_is_recorded(self):
        row = recorder.command(self.out, 'absent', ['/no-such-generation-test-command'], {}, 1, self.root)
        self.assertEqual(row['status'], 'execution_error')
        self.assertEqual(row['error_type'], 'FileNotFoundError')
        self.assertIsNone(row['exit_code'])
        self.assertTrue((self.out / 'absent-finished.json').exists())

    def test_nonpositive_timeout_never_starts_child(self):
        with self.assertRaisesRegex(RuntimeError, 'positive'):
            self.execute('raise SystemExit(0)', timeout=0)
        self.assertFalse((self.out / 'fixture-started.json').exists())

    def test_stage_cannot_overwrite_previous_record(self):
        self.execute("print('first')")
        old = (self.out / 'fixture.log').read_bytes()
        with self.assertRaises(FileExistsError):
            self.execute("print('second')")
        self.assertEqual((self.out / 'fixture.log').read_bytes(), old)

    def transaction_fixture(self, backend='lean'):
        before = self.snapshot()
        source = self.root / ('deps/sail-riscv/build/model/Lean_RV64D' if backend == 'lean'
                              else 'deps/sail-riscv/build/rocq')
        destination = self.root / ('proof/' + backend + '/generated/sail')
        generation_backup = source.parent / '.sail-generation-fixture'
        installation_backup = destination.parent / '.sail-install-fixture'
        for path in (source, destination, generation_backup, installation_backup):
            path.mkdir(parents=True, exist_ok=True)
        (source / 'model').write_text('raw fixture')
        (destination / 'model').write_text('adapted fixture')
        row = {'status': 'installed', 'published': True, 'policy_changed': False,
               'source': str(source), 'destination': str(destination),
               'generation_backup': str(generation_backup), 'installation_backup': str(installation_backup),
               'raw_files': ['model'], 'installed_files': ['model']}
        recorder.write(installation_backup / 'transaction.json', row)
        (self.out / 'sail.log').write_text('SAIL_INSTALL_JSON=' + json.dumps(row) + '\n')
        return row, before, self.snapshot()

    def validate_transaction(self, before, after, backend='lean'):
        return recorder.sail_transaction(self.out, {'log': 'sail.log'}, backend, before, after, self.root)

    def test_actual_transaction_fixture_links_fresh_tree_and_log(self):
        row, before, after = self.transaction_fixture()
        self.assertEqual(self.validate_transaction(before, after), row)

    def test_rocq_transaction_fixture(self):
        row, before, after = self.transaction_fixture('rocq')
        self.assertEqual(self.validate_transaction(before, after, 'rocq'), row)

    def test_reused_transaction_is_rejected(self):
        _, _, after = self.transaction_fixture()
        with self.assertRaisesRegex(RuntimeError, 'not fresh'):
            self.validate_transaction(after, after)

    def test_transaction_extra_installed_file_is_rejected(self):
        row, before, _ = self.transaction_fixture()
        (Path(row['destination']) / 'undeclared').write_text('extra')
        with self.assertRaisesRegex(RuntimeError, 'file inventory differs'):
            self.validate_transaction(before, self.snapshot())

    def test_transaction_marker_missing_or_duplicate_is_rejected(self):
        _, before, after = self.transaction_fixture()
        log = self.out / 'sail.log'
        original = log.read_text()
        for text in ('ordinary output', original + original):
            log.write_text(text)
            with self.assertRaisesRegex(RuntimeError, 'missing/duplicate'):
                self.validate_transaction(before, after)

    def test_transaction_wrong_target_is_rejected(self):
        row, before, after = self.transaction_fixture()
        row['destination'] = '/another/checkout'
        (self.out / 'sail.log').write_text('SAIL_INSTALL_JSON=' + json.dumps(row) + '\n')
        with self.assertRaisesRegex(RuntimeError, 'target differs'):
            self.validate_transaction(before, after)

    def test_transaction_disk_record_drift_is_rejected(self):
        row, before, after = self.transaction_fixture()
        path = Path(row['installation_backup']) / 'transaction.json'
        path.write_text('{}')
        with self.assertRaisesRegex(RuntimeError, 'record differs'):
            self.validate_transaction(before, after)

    def run_fixture(self, *, failure=None, stale_provenance=False, source_drift=False):
        # Exercise orchestration with real tiny inventories/files; stub tool
        # qualification and generators, so this NEVER attests a production run.
        policy = self.root / 'proof/lean/audit/step-policy.json'
        policy.parent.mkdir(parents=True)
        policy.write_text('{}')
        state = {'fixture_source': 'before'}
        calls = []

        def capture(out, label, extras, env, timeout):
            value = inventory.capture(self.root, extras)
            (out / label).mkdir()
            recorder.write(out / label / 'snapshot.json', value)
            return value

        def execute(out, name, argv, env, timeout):
            calls.append(name)
            if name == 'generate-rust':
                (self.root / recorder.PARENT / (recorder.PREFIX + 'fixture')).mkdir()
            if name == 'generate-sail-rocq':
                config = self.root / 'proof/rocq/generated/sail/ckb_vm_config.json'
                config.parent.mkdir(parents=True)
                config.write_text('{}')
            if source_drift:
                state['fixture_source'] = 'after'
            (out / (name + '.log')).write_text('fixture command only\n')
            return {'name': name, 'status': 'command_failed' if failure == name else 'completed',
                    'exit_code': 8 if failure == name else 0, 'log': name + '.log'}

        producer = recorder.PARENT + '/' + recorder.PREFIX + ('old' if stale_provenance else 'fixture')
        with patch.object(recorder, 'ROOT', self.root), \
             patch.object(recorder.source_snapshot, 'capture', side_effect=lambda root: dict(state)), \
             patch.object(rebuilt_main_tools, 'policy_identity'), \
             patch.object(rebuilt_main_tools, 'resolve', return_value=({}, {}, self.root, 'lake')), \
             patch.object(check_proof, 'source_evidence', return_value={'fixture': True}), \
             patch.object(check_proof, 'generated_evidence', return_value={
                 'rust_provenance': {'rebuilt_extraction': {'report': producer + '/report.json'}},
                 'sail_config_sha256': recorder.sha(policy)}), \
             patch.object(recorder, 'capture_command', side_effect=capture), \
             patch.object(recorder, 'command', side_effect=execute), \
             patch.object(recorder, 'sail_transaction', return_value={'fixture': True}), \
             patch('builtins.print'):
            code = recorder.run(self.out)
        return code, json.loads((self.out / 'report.json').read_text()), calls

    def test_success_records_all_stages_but_no_release_or_kernel_claim(self):
        code, report, calls = self.run_fixture()
        self.assertEqual(code, 0)
        self.assertEqual(calls, [row[0] for row in recorder.recipe()])
        self.assertTrue(report['generation_commands_completed'])
        self.assertTrue(report['source_bookends_match'])
        self.assertTrue(all(report[name] is False for name in recorder.FLAGS))
        self.assertFalse(report['output_scope_is_whole_workspace'])
        self.assertFalse(report['environment_values_published'])
        for name, digest in report['references'].items():
            self.assertEqual(recorder.sha(self.out / name), digest)

    def test_failure_stops_later_stages_but_records_after_and_delta(self):
        code, report, calls = self.run_fixture(failure='generate-rust')
        self.assertEqual(code, 1)
        self.assertEqual(calls, ['sail-config', 'generate-rust'])
        self.assertEqual(report['status'], 'failed')
        self.assertFalse(report['generation_commands_completed'])
        self.assertTrue((self.out / 'after/snapshot.json').is_file())
        self.assertTrue((self.out / 'delta.json').is_file())

    def test_stale_rust_provenance_cannot_certify_fresh_execution(self):
        code, report, _ = self.run_fixture(stale_provenance=True)
        self.assertEqual(code, 1)
        self.assertIn('not from this run', report['error'])

    def test_source_drift_is_not_relabelled_as_success(self):
        code, report, _ = self.run_fixture(source_drift=True)
        self.assertEqual(code, 1)
        self.assertFalse(report['source_bookends_match'])


if __name__ == '__main__':
    unittest.main()
