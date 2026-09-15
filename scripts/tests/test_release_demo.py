import copy
import json
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import release_demo as demo


class TerminalTests(unittest.TestCase):
    def setUp(self):
        self.body = b'fixture only\r\n'
        self.timing = b'0.100000 ' + str(len(self.body)).encode() + b'\n'
        self.log = b'Script started on fixture\n' + self.body + b'\nScript done on fixture [COMMAND_EXIT_CODE="0"]\n'

    def test_exact_output_and_timing(self):
        result = demo.check_terminal(self.log, self.timing, self.body)
        self.assertEqual(result, {'output_bytes': len(self.body), 'duration_seconds': 0.1, 'timing_events': 1})

    def test_timing_multiple_events(self):
        timing = b'0.000001 1\n0.100000 ' + str(len(self.body)-1).encode() + b'\n'
        self.assertEqual(demo.check_terminal(self.log, timing, self.body)['timing_events'], 2)

    def test_no_timing_not_a_recording(self):
        with self.assertRaisesRegex(RuntimeError, 'timing'): demo.check_terminal(self.log, b'', self.body)

    def test_malformed_negative_nonfinite_or_zero_size_timing(self):
        for line in [b'NaN 14', b'inf 14', b'-1.0 14', b'0.1 0', b'0.1 -1', b'O 0.1 14', b'0.1 14 extra']:
            with self.subTest(line=line), self.assertRaises(RuntimeError):
                demo.check_terminal(self.log, line, self.body)

    def test_missing_or_extra_output_bytes(self):
        for count in [len(self.body)-1, len(self.body)+1]:
            with self.subTest(count=count), self.assertRaisesRegex(RuntimeError, 'coverage'):
                demo.check_terminal(self.log, b'0.1 ' + str(count).encode(), self.body)

    def test_zero_or_excessive_duration(self):
        for delay in ['0.0', '1200.1', '9'*400+'.0']:
            with self.subTest(delay=delay), self.assertRaisesRegex(RuntimeError, 'duration'):
                demo.check_terminal(self.log, (delay+' '+str(len(self.body))).encode(), self.body)

    def test_spliced_display_cannot_match_raw_evidence(self):
        with self.assertRaisesRegex(RuntimeError, 'content'):
            demo.check_terminal(self.log.replace(b'fixture', b'fiction', 2), self.timing, self.body)

    def test_missing_terminal_header(self):
        with self.assertRaisesRegex(RuntimeError, 'header'):
            demo.check_terminal(self.body, self.timing, self.body)

    def test_nonzero_or_missing_completion(self):
        for log in [self.log.replace(b'EXIT_CODE="0"', b'EXIT_CODE="1"'), self.log[:-1], self.log+b'hidden output']:
            with self.subTest(log=log), self.assertRaisesRegex(RuntimeError, 'incomplete'):
                demo.check_terminal(log, self.timing, self.body)

    def test_actual_util_linux_round_trip(self):
        # This tests the installed recorder/player, not a fabricated timing file.
        with tempfile.TemporaryDirectory(prefix='demo-terminal-test-') as folder:
            out = Path(folder)
            argv = demo.recording_command(out)
            argv[-1] = shlex.join([sys.executable, '-c', 'print("fixture only", flush=True)'])
            result = subprocess.run(argv, stdin=subprocess.DEVNULL, capture_output=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout, self.body)
            demo.check_terminal((out/'terminal.log').read_bytes(), (out/'timing.log').read_bytes(), self.body)
            replay = subprocess.run(demo.playback_command(out), stdin=subprocess.DEVNULL,
                                    capture_output=True, timeout=30)
            self.assertEqual(replay.returncode, 0, replay.stderr)
            self.assertEqual(replay.stdout, self.body+b'\n')


class SessionTests(unittest.TestCase):
    def setUp(self):
        self.out = Path('/fixture/demo')
        self.commands = demo.commands(self.out, Path('/fixture/binary'), Path('/fixture/trap'))
        self.summary = {'fixture': 'independent result'}
        self.report = {'schema_version': 1, 'status': 'completed', 'summary': self.summary,
                      'stages': [{'name': n, 'argv': argv, 'exit_code': c,
                                  'logs': {n+'.stdout': 'fixture', n+'.stderr': 'fixture'}}
                                 for n, argv, c in self.commands]}
        for manager in [patch.object(demo.common, 'linked'),
                        patch.object(demo, 'results', return_value=self.summary)]:
            manager.start(); self.addCleanup(manager.stop)

    def check(self):
        return demo.check_session(self.out, self.report, self.commands, {}, Path('/fixture/trap'))

    def test_complete_session(self):
        self.assertEqual(self.check(), self.summary)

    def test_missing_or_duplicate_stage(self):
        for stages in [self.report['stages'][:-1], self.report['stages']*2]:
            self.report['stages'] = stages
            with self.assertRaisesRegex(RuntimeError, 'stage inventory'): self.check()

    def test_command_or_stage_order_substitution(self):
        self.report['stages'] = list(reversed(self.report['stages']))
        with self.assertRaisesRegex(RuntimeError, 'command/order/exit'): self.check()

    def test_failure_cannot_be_changed_to_success(self):
        self.report['stages'][-1]['exit_code'] = 0
        with self.assertRaisesRegex(RuntimeError, 'command/order/exit'): self.check()

    def test_boolean_exit_cannot_impersonate_zero(self):
        self.report['stages'][0]['exit_code'] = False
        with self.assertRaisesRegex(RuntimeError, 'command/order/exit'): self.check()

    def test_missing_stderr_not_silently_ignored(self):
        self.report['stages'][0]['logs'].pop('corpus-mutations.stderr')
        with self.assertRaisesRegex(RuntimeError, 'log inventory'): self.check()

    def test_summary_must_be_recomputed(self):
        self.report['summary'] = {'claim': 'PASS'}
        with self.assertRaisesRegex(RuntimeError, 'summary changed'): self.check()


class BoundaryTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='demo-boundary-test-')
        self.addCleanup(temporary.cleanup)
        self.out = Path(temporary.name)
        self.path = self.out / 'report.json'
        self.report = {'schema_version': 1, 'status': 'recorded_and_replayed', 'scope': demo.SCOPE,
                       **demo.CLAIMS, 'inputs_before': {}, 'inputs_after': {}}

    def check(self):
        self.path.write_text(json.dumps(self.report))
        return demo.check(self.path)

    def test_incomplete_or_overclaimed_report_rejected(self):
        for key, value in [('schema_version', True), ('status', 'running'), ('scope', 'entire VM verified'),
                           *[(name, True) for name in demo.CLAIMS]]:
            self.report.update({key: value})
            with self.subTest(key=key), self.assertRaisesRegex(RuntimeError, 'incomplete/overclaimed'):
                self.check()
            self.report = {'schema_version': 1, 'status': 'recorded_and_replayed', 'scope': demo.SCOPE, **demo.CLAIMS}

    def test_missing_assurance_flags_rejected(self):
        for key in demo.CLAIMS:
            report = copy.deepcopy(self.report); del self.report[key]
            with self.subTest(key=key), self.assertRaisesRegex(RuntimeError, 'overclaimed'): self.check()
            self.report = report

    def test_old_source_or_tools_rejected(self):
        with (patch.object(demo.runtime, 'environment', return_value=({}, 'fixture')),
              patch.object(demo, 'inputs', return_value={'changed': 'identity'})):
            with self.assertRaisesRegex(RuntimeError, 'source/tool drift'): self.check()

    def test_plan_schema_cannot_omit_or_add_dependencies(self):
        for plan in [{}, {'schema_version': True, 'runtime': {}, 'trap': {}},
                     {'schema_version': 1, 'runtime': {}, 'trap': {}, 'override': True}]:
            with self.subTest(plan=plan), self.assertRaisesRegex(RuntimeError, 'plan schema'): demo.prepare(plan)

    def test_reference_rejects_escape_and_unknown_fields(self):
        for row in [True, {'path': '../escape', 'sha256': '0'*64}, {'path': 'x', 'sha256': '0'*64, 'allow': True}]:
            with self.subTest(row=row), self.assertRaises(RuntimeError): demo.resolve(row)

    def test_recorder_does_not_record_input_or_run_interactive_shell(self):
        argv = demo.recording_command(self.out)
        self.assertNotIn('--log-in', argv); self.assertNotIn('--log-io', argv)
        self.assertIn('--return', argv)
        self.assertEqual(shlex.split(argv[-1]), [sys.executable, str(demo.SCRIPT), '--session', str(self.out)])

    def test_fixed_stage_order_and_known_failure_exit(self):
        stages = demo.commands(self.out, Path('/fixture/binary'), Path('/fixture/trap'))
        self.assertEqual([(n, c) for n, _, c in stages], [('corpus-mutations', 0), ('replay-add', 0), ('replay-known-trap', 1)])
        self.assertIn('--mutate', stages[0][1])
        self.assertIn(str(self.out/'corpus/add-zero.json'), stages[1][1])

    def test_caption_cannot_omit_scope_or_hide_expected_mismatch(self):
        summary = {'cases': 32, 'families': {'ADD': 13, 'ADDI': 10, 'BEQ': 9},
                   'mutations': {'applied': 188, 'skipped': 4}}
        text = demo.transcript(demo.commands(self.out, Path('/fixture/binary'), Path('/fixture/trap')), summary)
        self.assertIn('detected mutations=188', text)
        self.assertIn('expected exit 1', text)
        self.assertIn('NOT claimed', text)
        self.assertIn('no new kernel run', text)

    def test_unknown_stage_cannot_get_success_caption(self):
        with self.assertRaisesRegex(RuntimeError, 'unknown demo stage'): demo.conclusion('invented', {})

    def test_failed_producer_preserves_failed_report(self):
        with patch.object(demo.runtime, 'environment', side_effect=RuntimeError('fixture failure')), patch('builtins.print'):
            self.assertEqual(demo.record(self.out, Path('unused'), Path('unused')), 1)
        report = demo.read(self.path)
        self.assertEqual(report['status'], 'failed')
        self.assertEqual(report['error'], 'fixture failure')
        self.assertFalse(report['week6_closed'])

    def test_existing_output_cannot_be_overwritten(self):
        original = b'user data'
        self.path.write_bytes(original)
        with self.assertRaises(FileExistsError): demo.save(self.path, {})
        self.assertEqual(self.path.read_bytes(), original)


if __name__ == '__main__':
    unittest.main()
