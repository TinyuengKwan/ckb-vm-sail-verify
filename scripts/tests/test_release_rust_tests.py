import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import release_rust_tests as checks


def output(names):
    return '\n'.join([f'running {len(names)} tests', *['test ' + n + ' ... ok' for n in names],
        f'test result: ok. {len(names)} passed; 0 failed; 0 ignored; 0 measured; 0 filtered out; finished in 0.01s'])


class TestLogs(unittest.TestCase):
    def test_listing_exact_names_and_empty_suite(self):
        self.assertEqual(checks.listings('a: test\nb: test\n2 tests, 0 benchmarks\n\n0 tests, 0 benchmarks'),
                         [['a', 'b'], []])

    def test_execution_matches_inventory(self):
        self.assertEqual(checks.results(output(['b', 'a']) + '\n' + output([]), [['a', 'b'], []]), 2)

    def test_listing_duplicate_or_wrong_count_or_benchmark(self):
        for text in ['a: test\na: test\n2 tests, 0 benchmarks', 'a: test\n2 tests, 0 benchmarks',
                     'a: test', '0 tests, 1 benchmarks', 'unexpected']:
            with self.subTest(text=text), self.assertRaises(RuntimeError): checks.listings(text)

    def test_missing_extra_duplicate_test_rejected(self):
        for names in [[], ['a'], ['a', 'b', 'c'], ['a', 'a']]:
            with self.subTest(names=names), self.assertRaises(RuntimeError):
                checks.results(output(names), [['a', 'b']])

    def test_ignored_filtered_or_failed_rejected(self):
        for old, new in [('0 ignored', '1 ignored'), ('0 filtered out', '1 filtered out'),
                         ('0 failed', '1 failed'), ('... ok', '... ignored'), ('... ok', '... FAILED')]:
            with self.subTest(new=new), self.assertRaises(RuntimeError):
                checks.results(output(['a']).replace(old, new), [['a']])

    def test_no_test_results_not_a_pass(self):
        with self.assertRaises(RuntimeError): checks.results('', [[]])

    def test_missing_final_summary_or_wrong_running_count(self):
        for text in ['running 1 test\ntest a ... ok', output(['a']).replace('running 1', 'running 0')]:
            with self.subTest(text=text), self.assertRaises(RuntimeError): checks.results(text, [['a']])

    def test_no_reused_summary_for_another_suite(self):
        with self.assertRaises(RuntimeError): checks.results(output(['a']), [['a'], []])


class CatalogueTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='rust-tests-catalogue-')
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.patcher = patch.object(checks, 'ROOT', self.root)
        self.patcher.start()
        self.addCleanup(self.patcher.stop)
        self.target = self.root / 'new-target'
        self.target.mkdir()
        self.binary = self.target / 'test-binary'
        self.binary.write_bytes(b'synthetic test only')
        self.item = {'name': 'fixture', 'kind': ['lib'], 'test': True, 'doctest': True}
        self.metadata = {'workspace_root': str(self.root), 'workspace_members': ['fixture'],
            'packages': [{'id': 'fixture', 'name': 'fixture',
                'manifest_path': str(self.root / 'crates/fixture/Cargo.toml'), 'targets': [self.item]}]}
        self.artifact = {'reason': 'compiler-artifact', 'profile': {'test': True}, 'package_id': 'fixture',
                         'target': self.item, 'executable': str(self.binary)}

    def build(self, rows=None):
        return '\n'.join(json.dumps(row) for row in (rows if rows is not None else [self.artifact]) +
                         [{'reason': 'build-finished', 'success': True}])

    def test_exact_build_target_catalogue(self):
        rows, docs = checks.catalogue(self.metadata, self.build(), self.target)
        self.assertEqual(rows[0]['id'], 'fixture/fixture/lib')
        self.assertEqual(docs, ['fixture'])

    def test_missing_executable(self):
        with self.assertRaises(RuntimeError): checks.catalogue(self.metadata, self.build([]), self.target)

    def test_duplicate_executable(self):
        with self.assertRaises(RuntimeError):
            checks.catalogue(self.metadata, self.build([self.artifact, self.artifact]), self.target)

    def test_binary_outside_new_target(self):
        self.artifact['executable'] = str(self.root / 'old-target/binary')
        with self.assertRaises(RuntimeError): checks.catalogue(self.metadata, self.build(), self.target)

    def test_wrong_workspace_or_missing_member(self):
        self.metadata['workspace_members'].append('absent')
        with self.assertRaises(RuntimeError): checks.catalogue(self.metadata, self.build(), self.target)

    def test_build_not_finished_or_failed(self):
        for build in [json.dumps(self.artifact), self.build().replace('"success": true', '"success": false')]:
            with self.subTest(build=build), self.assertRaises(RuntimeError):
                checks.catalogue(self.metadata, build, self.target)

    def test_unknown_test_target_kind(self):
        self.item['kind'] = ['custom-build']
        with self.assertRaises(RuntimeError): checks.catalogue(self.metadata, self.build(), self.target)


if __name__ == '__main__':
    unittest.main()
