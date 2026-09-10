"""Fail-closed option checks for fresh public decoder extraction."""
import copy
import unittest

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from decoder_public_source import check_reextraction


class ReextractionTests(unittest.TestCase):
    def setUp(self):
        self.archived = {
            'has_errors': False, 'charon_version': '0.1.247',
            'translated': {'crate_name': 'outer_decoder_probe',
                'target_information': {'pointer_size': 64},
                'options': {'dest_file': '/archive/Outer.llbc', 'sysroot': '/pinned/std',
                    'include': ['ckb_vm::decoder::_'], 'opaque': ['ckb_vm::memory::_'],
                    'start_from': ['outer_decoder_probe::_'], 'exclude': [],
                    'skip_borrowck': False, 'no_typecheck': False, 'preset': 'Aeneas'}}}
        self.fresh = copy.deepcopy(self.archived)

    def test_identical(self):
        check_reextraction(self.archived, self.fresh)

    def test_only_destination_can_change(self):
        self.fresh['translated']['options']['dest_file'] = '/fresh/Outer.llbc'
        check_reextraction(self.archived, self.fresh)

    def test_errors_rejected(self):
        self.fresh['has_errors'] = True
        with self.assertRaisesRegex(RuntimeError, 'frontend errors'):
            check_reextraction(self.archived, self.fresh)

    def test_version_rejected(self):
        self.fresh['charon_version'] = '0.1.248'
        with self.assertRaisesRegex(RuntimeError, 'format changed'):
            check_reextraction(self.archived, self.fresh)

    def test_crate_rejected(self):
        self.fresh['translated']['crate_name'] = 'replacement_decoder'
        with self.assertRaisesRegex(RuntimeError, 'crate_name changed'):
            check_reextraction(self.archived, self.fresh)

    def test_target_rejected(self):
        self.fresh['translated']['target_information']['pointer_size'] = 32
        with self.assertRaisesRegex(RuntimeError, 'target_information changed'):
            check_reextraction(self.archived, self.fresh)

    def test_option_drift_rejected(self):
        for option, value in [('sysroot', '/different/std'), ('include', []),
                ('opaque', ['ckb_vm::decoder::_']), ('start_from', []),
                ('exclude', ['ckb_vm::decoder::_']), ('skip_borrowck', True),
                ('no_typecheck', True), ('preset', 'RawMir')]:
            with self.subTest(option=option):
                fresh = copy.deepcopy(self.archived)
                fresh['translated']['options'][option] = value
                with self.assertRaisesRegex(RuntimeError, 'options changed'):
                    check_reextraction(self.archived, fresh)

    def test_added_option_rejected(self):
        self.fresh['translated']['options']['new_flag'] = True
        with self.assertRaisesRegex(RuntimeError, 'options changed'):
            check_reextraction(self.archived, self.fresh)

    def test_missing_option_rejected(self):
        del self.fresh['translated']['options']['no_typecheck']
        with self.assertRaisesRegex(RuntimeError, 'options changed'):
            check_reextraction(self.archived, self.fresh)

    def test_does_not_mutate_archived_options(self):
        before = copy.deepcopy(self.archived)
        self.fresh['translated']['options']['dest_file'] = '/new/Outer.llbc'
        check_reextraction(self.archived, self.fresh)
        self.assertEqual(self.archived, before)


if __name__ == '__main__':
    unittest.main()
