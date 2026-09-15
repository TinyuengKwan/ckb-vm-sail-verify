from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import sail_cpp_correspondence as p


class SailCppCorrespondenceTests(unittest.TestCase):
    def test_inline_body_method_is_checked_in_gap_not_discarded(self):
        inline = 'void Model::create_letbind_49(void) { int stable = 1;\n}\n'
        old, new = self.cpp() + inline, self.cpp(2, 20, 5) + inline
        result = p.analyze(old, new, self.header(), self.header(2))
        self.assertEqual(result['method_count'], 1)
        self.assertEqual(result['gaps_checked'], 2)
        with self.assertRaisesRegex(RuntimeError, 'unaccounted'):
            p.analyze(old, new.replace('stable = 1', 'stable = 2'), self.header(), self.header(2))

    def test_unchanged_occurrence_cannot_capture_renamed_variable(self):
        old = self.cpp().replace('  bool z2zE11;', '  bool z2zE21;\n  bool z2zE11;')
        new = self.cpp(2, 20, 5).replace('  bool z2zE21;', '  bool z2zE21;\n  bool z2zE21;')
        with self.assertRaisesRegex(RuntimeError, 'non-injective'):
            p.analyze(old, new, self.header(), self.header(2))

    def test_two_field_declarations_cannot_be_reordered(self):
        old = self.cpp().replace('  goto', '  z0zE3 = z0zE1;\n  goto')
        new = self.cpp(2, 20, 5).replace('  goto', '  z0zE4 = z0zE2;\n  goto')
        ha = self.header().removesuffix('};\n') + '  // register zz50zE3\n  bool z0zE3 = {};\n};\n'
        hb = self.header(2).removesuffix('};\n') + '  // register zz50zE4\n  bool z0zE4 = {};\n};\n'
        self.assertEqual(p.analyze(old, new, ha, hb)['field_count'], 2)
        swapped = ('struct Model {\n  bool f(bool);\n  // register zz50zE4\n'
                   '  bool z0zE4 = {};\n  // register zz50zE2\n  bool z0zE2 = {};\n};\n')
        with self.assertRaisesRegex(RuntimeError, 'inconsistent'):
            p.analyze(old, new, ha, swapped)

    def test_constructor_indent_and_trailing_gap_are_not_discarded(self):
        source = 'Model::Model() {\n  }\n\nModel::~Model() {\n  }\n'
        self.assertEqual([name for name, _, _ in p.regions(source)], ['Model', '~Model'])
        old = self.cpp() + source + '\nint external_state = 0;\n'
        new = self.cpp(2, 20, 5) + source + '\nint external_state = 1;\n'
        with self.assertRaisesRegex(RuntimeError, 'unaccounted'):
            p.analyze(old, new, self.header(), self.header(2))

    def test_literal_and_comment_braces_do_not_terminate_method(self):
        body = self.cpp().replace('  bool z2zE11;', '  /* } */ const char *s = "}";\n  bool z2zE11;')
        self.assertEqual(p.regions(body)[0][2], len(body.rstrip()))

    def cpp(self, field=1, variable=10, label=1, method='f'):
        return (f'bool Model::{method}(bool z3zE{variable})\n{{\n'
                f'  bool z2zE{variable + 1};\n  z2zE{variable + 1} = z3zE{variable};\n'
                f'  z0zE{field} = z2zE{variable + 1};\n  goto end_function_{label};\n'
                f'end_function_{label}: ;\n  return z0zE{field};\n}}\n')

    def header(self, field=1, typ='bool'):
        return f'struct Model {{\n  bool f(bool);\n  // register zz50zE{field}\n  {typ} z0zE{field} = {{}};\n}};\n'

    def test_scoped_bijections_cover_header_types_and_order(self):
        result = p.analyze(self.cpp(), self.cpp(2, 20, 5), self.header(), self.header(2))
        self.assertEqual(result['fields'], {'z0zE1': 'z0zE2'})
        self.assertEqual(result['methods']['f']['variables'], {'z3zE10': 'z3zE20', 'z2zE11': 'z2zE21'})
        self.assertEqual(result['methods']['f']['labels'], {'end_function_1': 'end_function_5'})
        self.assertTrue(result['header_order_types_initializers_preserved'])

    def test_global_mapping_cannot_change_between_methods(self):
        old = self.cpp() + self.cpp(method='g')
        new = self.cpp(2, 20, 5) + self.cpp(3, 30, 6, 'g')
        with self.assertRaisesRegex(RuntimeError, 'inconsistent'):
            p.analyze(old, new, self.header(), self.header(2))

    def test_local_mapping_has_method_scope(self):
        old = self.cpp() + self.cpp(method='g')
        new = self.cpp(2, 20, 5) + self.cpp(2, 30, 6, 'g')
        self.assertEqual(p.analyze(old, new, self.header(), self.header(2))['method_count'], 2)

    def test_bijection_rejects_both_conflict_directions(self):
        for pair in [('a', 'c'), ('c', 'b')]:
            mapping = p.Bijection(); mapping.bind('a', 'b')
            with self.assertRaises(RuntimeError):
                mapping.bind(*pair)

    def test_string_char_and_ordinary_comment_are_not_renamed(self):
        for literal in ('"z3zE10"', "'a'", '/* z3zE10 */', '// z3zE10\n'):
            replacement = literal.replace('10', '20').replace("'a'", "'b'")
            with self.assertRaises(RuntimeError):
                p.compare(literal, replacement, p.Bijection(), set(), scoped=True)

    def test_only_exact_generated_field_comments_can_map(self):
        mapping = p.Bijection()
        p.compare('/* lifted zz50zE1 */', '/* lifted zz50zE2 */', mapping, set())
        self.assertEqual(mapping.forward, {'z0zE1': 'z0zE2'})
        with self.assertRaises(RuntimeError):
            p.compare('/* other zz50zE1 */', '/* other zz50zE2 */', p.Bijection(), set())

    def test_type_constant_operator_and_call_changes_rejected(self):
        old = self.cpp(); new = self.cpp(2, 20, 5)
        for changed in (new.replace('bool z2zE21', 'int z2zE21'), new.replace('= z3zE20', '= false'),
                        new.replace('= z3zE20', '= !z3zE20'), new.replace('return z0zE2', 'return other()')):
            with self.assertRaises(RuntimeError):
                p.analyze(old, changed, self.header(), self.header(2))

    def test_corresponding_field_type_must_match(self):
        with self.assertRaisesRegex(RuntimeError, 'field types'):
            p.analyze(self.cpp(), self.cpp(2, 20, 5), self.header(), self.header(2, 'int'))

    def test_header_layout_not_sorted_or_ignored(self):
        with self.assertRaises(RuntimeError):
            p.analyze(self.cpp(), self.cpp(2, 20, 5), self.header(), self.header(2).replace('  bool f(bool);\n', '\n  bool f(bool);\n'))

    def test_undeclared_or_duplicate_label_rejected(self):
        for source in (self.cpp().replace('end_function_1: ;', ''),
                       self.cpp().replace('end_function_1: ;', 'end_function_1: ;\nend_function_1: ;')):
            with self.assertRaises(RuntimeError):
                p.analyze(source, source, self.header(), self.header())

    def test_external_generated_name_is_conservatively_fixed(self):
        outside = 'bool z3zE10;\n'
        with self.assertRaisesRegex(RuntimeError, 'externally visible'):
            p.analyze(outside + self.cpp(), outside + self.cpp(2, 20, 5), self.header(), self.header(2))

    def test_unsupported_or_unterminated_lexical_forms_rejected(self):
        for text in ('R"(raw)"', 'u8R"(raw)"', '/* unfinished', '"unfinished', "'unfinished"):
            with self.assertRaises(RuntimeError):
                list(p.tokens(text))

    def test_function_order_duplicates_and_incomplete_spans_rejected(self):
        with self.assertRaises(RuntimeError):
            p.regions(self.cpp() + self.cpp())
        with self.assertRaises(RuntimeError):
            p.regions(self.cpp()[:-2])
        with self.assertRaisesRegex(RuntimeError, 'method set/order'):
            p.analyze(self.cpp(), self.cpp(method='g'), self.header(), self.header())

    def test_field_declaration_comment_and_inventory_guard(self):
        with self.assertRaises(RuntimeError):
            p.fields_in(self.header().replace('zz50zE1', 'zz50zE2'))
        with self.assertRaises(RuntimeError):
            p.fields_in(self.header() + self.header())

    def test_failed_preflight_cannot_claim_comparison_or_semantics(self):
        with tempfile.TemporaryDirectory() as temp:
            out = Path(temp)
            with patch.object(p.evidence, 'pinned', side_effect=RuntimeError('drift')), patch('builtins.print'):
                self.assertEqual(p.run(out), 1)
            report = p.evidence.read(out / 'report.json')
        self.assertEqual(report['status'], 'failed')
        for key in ('semantic_equivalence_proved', 'cpp_ast_or_macro_binding_proved', 'cpp_compiled',
                    'runtime_executed', 'tool_adopted', 'policy_changed', 'generated_sources_edited'):
            self.assertIs(report[key], False)


if __name__ == '__main__':
    unittest.main()
