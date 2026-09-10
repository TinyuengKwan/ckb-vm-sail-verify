"""Checks that diagnostic classification cannot hide additional compiler errors."""
import unittest

from audit_charon_failure_diagnostics import classify


class DiagnosticsTests(unittest.TestCase):
    def setUp(self):
        self.body = ("error[E0463]: can't find crate for `std`\n"
                     '= note: the `target-a` target may not be installed\n'
                     '= note: the `target-b` target may not be installed\n')
        self.a = 'translation for target target-a failed with status exit status: 2\n'
        self.b = 'translation for target target-b failed with status exit status: 2\n'

    def test_identical(self):
        self.assertEqual(classify(self.body, self.body), 'identical')

    def test_order_only(self):
        self.assertEqual(classify(self.body, '\n'.join(reversed(self.body.splitlines())) + '\n'),
                         'line-order-only')

    def test_first_failure(self):
        self.assertEqual(classify(self.body + self.a, self.body + self.b),
                         'first-failed-target-and-line-order')

    def test_extra_error_not_hidden(self):
        self.assertEqual(classify(self.body + self.a, self.body + 'error: new bug\n' + self.b), 'unclassified')

    def test_duplicate_error_not_hidden(self):
        self.assertEqual(classify(self.body + self.a, self.body + self.body + self.b), 'unclassified')

    def test_unsupported_status(self):
        self.assertEqual(classify(self.body + self.a, self.body + self.b.replace(': 2', ': 3')), 'unclassified')

    def test_target_needs_actual_diagnostic(self):
        self.assertEqual(classify(self.body + self.a, self.body + self.b.replace('target-b', 'target-c')),
                         'unclassified')


if __name__ == '__main__':
    unittest.main()
