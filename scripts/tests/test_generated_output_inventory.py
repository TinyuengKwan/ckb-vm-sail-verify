"""Filesystem and CLI regression tests; fixtures are not regeneration evidence."""
import copy
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import generated_output_inventory as inventory


class InventoryTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='generated-inventory-test-')
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name)
        self.root = self.directory / 'checkout'
        self.root.mkdir()
        self.build = self.root / 'build'
        self.build.mkdir()
        self.file = self.build / 'model'
        self.file.write_bytes(b'fixture bytes\x00\xff')

    def capture(self, extra=()):
        return inventory.capture(self.root, extra)

    def resign(self, value):
        value['snapshot_sha256'] = inventory.digest({k: v for k, v in value.items() if k != 'snapshot_sha256'})

    def cli(self, *args):
        with patch.object(sys, 'argv', ['generated_output_inventory.py', *map(str, args)]), \
             patch('builtins.print'):
            return inventory.main()

    def test_inventory_counts_bytes_and_records_absent_roots(self):
        value = self.capture()
        self.assertEqual(inventory.summary(value)['files'], 1)
        self.assertEqual(inventory.summary(value)['bytes'], len(self.file.read_bytes()))
        self.assertEqual(len(inventory.summary(value)['absent_roots']), 8)
        self.assertIsNone(value['entries']['target'])
        self.assertEqual(value['entries']['build/model']['kind'], 'file')

    def test_whole_trees_include_caches_backups_and_nested_git_metadata(self):
        for name in ('.lake/compiled.olean', '.rust-install-old/retained', '.git/HEAD', 'target/cache'):
            path = self.build/name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text('fixture retained byte')
        result = self.capture()['entries']
        for name in ('.lake/compiled.olean', '.rust-install-old/retained', '.git/HEAD', 'target/cache'):
            self.assertIn('build/'+name, result)

    def test_empty_directories_are_explicit(self):
        (self.build/'empty').mkdir()
        self.assertEqual(self.capture()['entries']['build/empty']['kind'], 'directory')

    def test_symlinks_are_recorded_without_dereferencing(self):
        outside = self.directory/'outside'
        outside.mkdir()
        (outside/'hidden').write_text('must not enter inventory')
        for name, target in [('outside', str(outside)), ('broken', '../missing'), ('self', 'self')]:
            (self.build/name).symlink_to(target)
        value = self.capture()
        self.assertEqual(inventory.summary(value)['symlinks'], 3)
        self.assertFalse(any('hidden' in name for name in value['entries']))
        self.assertEqual(value['entries']['build/broken']['target'], '../missing')

    def test_selected_root_link_is_a_link_not_an_empty_directory(self):
        (self.root/'target').symlink_to(self.build, target_is_directory=True)
        value = self.capture()
        self.assertEqual(value['entries']['target']['kind'], 'symlink')
        self.assertNotIn('target/model', value['entries'])

    def test_symlink_ancestor_is_rejected(self):
        (self.root/'proof').symlink_to(self.build, target_is_directory=True)
        with self.assertRaises(OSError): self.capture()

    def test_non_directory_ancestor_is_rejected(self):
        (self.root/'proof').write_text('not a directory')
        with self.assertRaises(OSError): self.capture()

    def test_special_fifo_node_rejected_without_reading(self):
        os.mkfifo(self.build/'pipe')
        with self.assertRaisesRegex(RuntimeError, 'special output node'): self.capture()

    def test_extra_run_root_is_explicit(self):
        path = self.root/'artifacts/run/output'
        path.mkdir(parents=True)
        (path/'result').write_text('run output')
        without = self.capture()
        with_extra = self.capture(['artifacts/run/output'])
        self.assertNotIn('artifacts/run/output/result', without['entries'])
        self.assertIn('artifacts/run/output/result', with_extra['entries'])
        self.assertIs(with_extra['whole_workspace_coverage_claimed'], False)

    def test_unsafe_duplicate_and_overlapping_roots_rejected(self):
        for values in (['../escape'], ['/absolute'], ['.git'], ['a//b'], ['build'],
                       ['build/nested'], ['proof'], ['extra', 'extra-other', 'extra/child']):
            with self.subTest(values=values), self.assertRaises(RuntimeError): self.capture(values)

    def test_comparison_includes_add_delete_bytes_and_mode(self):
        removed = self.build/'removed'
        removed.write_text('old')
        mode = self.build/'mode'
        mode.write_text('same content')
        before = self.capture()
        removed.unlink()
        mode.chmod(0o755)
        self.file.write_text('new bytes')
        (self.build/'added').write_text('new')
        after = self.capture()
        changes = inventory.compare(before, after)['changes']
        self.assertEqual({name: row['operation'] for name, row in changes.items()},
                         {'build/removed': 'deleted', 'build/mode': 'modified',
                          'build/model': 'modified', 'build/added': 'added'})

    def test_comparison_handles_absent_root_becoming_directory(self):
        before = self.capture()
        (self.root/'target').mkdir()
        (self.root/'target/model').write_text('new')
        changes = inventory.compare(before, self.capture())['changes']
        self.assertEqual(changes['target']['operation'], 'added')
        self.assertEqual(changes['target/model']['operation'], 'added')

    def test_comparison_handles_node_kind_and_link_target_changes(self):
        (self.build/'link').symlink_to('old-target')
        before = self.capture()
        self.file.unlink()
        self.file.mkdir()
        (self.build/'link').unlink()
        (self.build/'link').symlink_to('new-target')
        changes = inventory.compare(before, self.capture())['changes']
        self.assertEqual(changes['build/model']['after']['kind'], 'directory')
        self.assertEqual(changes['build/link']['after']['target'], 'new-target')

    def test_equal_snapshots_do_not_prove_regeneration_or_approval(self):
        value = self.capture()
        delta = inventory.compare(value, copy.deepcopy(value))
        self.assertEqual(delta['changes'], {})
        for name in ('regeneration_execution_proven', 'generated_outputs_audited',
                     'worktree_audit_closed', 'release_claimed', 'week6_closed'):
            self.assertIs(delta[name], False)

    def test_comparison_rejects_changed_scope(self):
        with self.assertRaisesRegex(RuntimeError, 'different output scopes'):
            inventory.compare(self.capture(), self.capture(['artifacts/extra']))

    def test_mandatory_root_cannot_be_removed_even_with_new_digest(self):
        value = self.capture()
        value['roots'].remove('target')
        del value['entries']['target']
        self.resign(value)
        with self.assertRaisesRegex(RuntimeError, 'mandatory'): inventory.validate(value)

    def test_missing_root_node_rejected(self):
        value = self.capture()
        del value['entries']['target']
        self.resign(value)
        with self.assertRaisesRegex(RuntimeError, 'root node'): inventory.validate(value)

    def test_child_under_absent_or_non_directory_parent_rejected(self):
        value = self.capture()
        value['entries']['target/hidden'] = copy.deepcopy(value['entries']['build/model'])
        self.resign(value)
        with self.assertRaisesRegex(RuntimeError, 'parent'): inventory.validate(value)

    def test_outside_scope_node_rejected(self):
        value = self.capture()
        value['entries']['unscoped'] = copy.deepcopy(value['entries']['build/model'])
        self.resign(value)
        with self.assertRaisesRegex(RuntimeError, 'outside'): inventory.validate(value)

    def test_unknown_fields_boolean_schema_and_assurance_upgrade_rejected(self):
        for name, item in [('schema_version', True), ('whole_workspace_coverage_claimed', True),
                           ('symlinks_followed', 0), ('approve', True)]:
            value = self.capture()
            value[name] = item
            self.resign(value)
            with self.subTest(name=name), self.assertRaises(RuntimeError): inventory.validate(value)

    def test_bad_node_type_hash_size_or_mode_rejected(self):
        for name, item in [('kind', 'socket'), ('sha256', 'A'*64), ('size', True),
                           ('size', -1), ('mode', True), ('mode', 0o10000)]:
            value = self.capture()
            value['entries']['build/model'][name] = item
            self.resign(value)
            with self.subTest(name=name, item=item), self.assertRaises(RuntimeError): inventory.validate(value)

    def test_snapshot_digest_tampering_rejected(self):
        value = self.capture()
        value['entries']['build/model']['size'] += 1
        with self.assertRaisesRegex(RuntimeError, 'digest'): inventory.validate(value)

    def test_directory_mutation_during_capture_rejected(self):
        original = inventory.regular
        def mutate(parent_fd, leaf, initial):
            value = original(parent_fd, leaf, initial)
            (self.build/'arrived-during-scan').write_text('unexpected')
            return value
        with patch.object(inventory, 'regular', side_effect=mutate), \
             self.assertRaisesRegex(RuntimeError, 'directory changed'): self.capture()

    def test_file_mutation_after_open_rejected(self):
        original = os.fstat
        calls = 0
        def mutate(fd):
            nonlocal calls
            result = original(fd)
            if inventory.stat.S_ISREG(result.st_mode):
                calls += 1
                if calls == 1: self.file.write_text('different content')
            return result
        with patch.object(inventory.os, 'fstat', side_effect=mutate), \
             self.assertRaisesRegex(RuntimeError, 'changed during hashing'): self.capture()

    def test_cli_capture_compare_and_existing_output_protection(self):
        before_out = self.directory/'before'
        after_out = self.directory/'after'
        delta_out = self.directory/'delta'
        self.assertEqual(self.cli('capture', '--root', self.root, '--out', before_out), 0)
        old = (before_out/'snapshot.json').read_bytes()
        self.assertEqual(self.cli('capture', '--root', self.root, '--out', before_out), 1)
        self.assertEqual((before_out/'snapshot.json').read_bytes(), old)
        self.file.write_text('changed')
        self.assertEqual(self.cli('capture', '--root', self.root, '--out', after_out), 0)
        self.assertEqual(self.cli('compare', '--before', before_out/'snapshot.json',
                                  '--after', after_out/'snapshot.json', '--out', delta_out), 0)
        self.assertEqual(set(json.loads((delta_out/'delta.json').read_text())['changes']), {'build/model'})

    def test_cli_rejects_output_inside_inventory_before_creating_it(self):
        out = self.build/'self-reference'
        self.assertEqual(self.cli('capture', '--root', self.root, '--out', out), 1)
        self.assertFalse(out.exists())

    def test_cli_rejects_duplicate_json_keys(self):
        path = self.directory/'bad.json'
        path.write_text('{"schema_version":1,"schema_version":1}')
        out = self.directory/'bad-out'
        self.assertEqual(self.cli('compare', '--before', path, '--after', path, '--out', out), 1)
        self.assertFalse(out.exists())


if __name__ == '__main__':
    unittest.main()
