import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from probes import probe_rebuilt_charon_diagnostics as p


class RebuiltDiagnosticsTests(unittest.TestCase):
    def test_historical_replay_checks_each_case_not_just_counts(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            archived, historical = {'cases': {}}, {'failed_cases': {}, 'counts': {'identical': 26}}
            for index in range(26):
                name = f'charon/tests/ui/case-{index}.rs'
                archived['cases'][name] = {'results': {}}
                hashes = {}
                for side in ('baseline', 'candidate'):
                    path = root / 'logs' / f'tests/ui/case-{index}' / side / 'stderr.log'
                    path.parent.mkdir(parents=True)
                    path.write_text("error[E0463]: can't find crate for `std`\n")
                    hashes[side] = p.sha(path)
                    archived['cases'][name]['results'][side] = {
                        'status': 'command-failed', 'stderr_sha256': p.sha(path)}
                historical['failed_cases'][name] = {'classification': 'identical', 'log_sha256': hashes}
            with patch.object(p.ui, 'OLD', root / 'report.json'):
                result = p.replay_historical(archived, historical)
                self.assertEqual(result['case_count'], 26)
                self.assertFalse(result['historical_classifier_source_identity_matched'])
                historical['failed_cases']['charon/tests/ui/case-0.rs']['classification'] = 'line-order-only'
                with self.assertRaisesRegex(RuntimeError, 'per-case'):
                    p.replay_historical(archived, historical)

    def test_std_core_and_duplicate_counts_are_preserved(self):
        text = ("error[E0463]: can't find crate for `std`\n" * 2 +
                "error[E0463]: can't find crate for `core`\nerror: aborting due to 3 previous errors\n")
        self.assertEqual(p.missing_crates(text), {'std': 2, 'core': 1})

    def test_extra_error_cannot_be_explained_as_missing_target(self):
        base = "error[E0463]: can't find crate for `std`\n"
        for error in ('error: new bug', 'error[E0308]: mismatched types',
                      "error[E0463]: can't find crate for `other`"):
            with self.assertRaisesRegex(RuntimeError, 'additional compiler error'):
                p.missing_crates(base + error + '\n')

    def test_summary_without_actual_missing_crate_is_not_evidence(self):
        for text in ('', 'warning only\n', 'error: aborting due to 1 previous error\n'):
            with self.assertRaises(RuntimeError):
                p.missing_crates(text)

    def test_failed_preflight_cannot_upgrade_ui_or_adopt_tool(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            with patch.object(p, 'sha', return_value='drift'), patch('builtins.print'):
                self.assertEqual(p.run(root), 1)
            result = json.loads((root / 'report.json').read_text())
        self.assertEqual(result['status'], 'failed')
        for key in ('tests_rerun', 'full_upstream_suite_passed', 'tool_adopted', 'policy_changed',
                    'goldens_updated', 'kernel_executed', 'clean_room_claimed', 'release_claimed'):
            self.assertIs(result[key], False)


if __name__ == '__main__':
    unittest.main()
