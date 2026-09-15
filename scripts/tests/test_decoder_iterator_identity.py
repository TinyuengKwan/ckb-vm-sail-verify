"""Relocation never hides changes outside the fixed iterator source location."""
import hashlib
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import decoder_model_identity as identity


class IteratorIdentityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="iterator-identity-test-")
        self.addCleanup(self.temp.cleanup)
        self.cwd = Path(self.temp.name)
        self.checkout = self.cwd / "checkout"
        self.model = self.cwd / "FnPtrFullMir.lean"
        self.legacy_source = (identity.LEGACY_CHECKOUT + "/" + identity.ITERATOR_RELATIVE).encode()
        self.relative_source = ("checkout/" + identity.ITERATOR_RELATIVE).encode()
        self.legacy = (b"/-- [example]\n    Source: '" + self.legacy_source +
                       b"', lines 1:0-2:1\n    Visibility: public -/\ndef example : Nat := 1\n" +
                       b"/-- [trait]\n    Source: '" + self.legacy_source +
                       b"', lines 3:0-4:1 -/\ndef other : Nat := 2\n")
        self.relative = self.legacy.replace(self.legacy_source, self.relative_source)
        approved = patch.object(identity, "ITERATOR_SHA256", hashlib.sha256(self.legacy).hexdigest())
        approved.start()
        self.addCleanup(approved.stop)

    def check(self, data, checkout=None, cwd=None):
        self.model.write_bytes(data)
        return identity.check_iterator(self.model, checkout or self.checkout, cwd or self.cwd)

    def test_relative_source_and_comment_end_preserved_without_file_edit(self):
        result = self.check(self.relative)
        self.assertEqual(result["source_comment_count"], 2)
        self.assertFalse(result["generated_file_edited"])
        self.assertEqual(self.model.read_bytes(), self.relative)

    def test_absolute_source_supported(self):
        absolute = str(self.checkout / identity.ITERATOR_RELATIVE).encode()
        self.assertEqual(self.check(self.relative.replace(self.relative_source, absolute))["source_comment_count"], 2)

    def test_legacy_model_keeps_exact_hash(self):
        self.assertEqual(self.check(self.legacy)["source_comment_count"], 0)

    def test_wrong_checkout_or_cwd_rejected(self):
        for kwargs in [{"checkout": self.cwd / "other"}, {"cwd": self.cwd / "other"}]:
            with self.subTest(kwargs=kwargs), self.assertRaises(RuntimeError):
                self.check(self.relative, **kwargs)

    def test_wrong_filename_positions_visibility_rejected(self):
        for old, new in [(b"fnptr_cases.rs", b"other.rs"), (b"1:0-2:1", b"1:0-3:1"),
                         (b"Visibility: public", b"Visibility: private")]:
            with self.subTest(old=old), self.assertRaises(RuntimeError):
                self.check(self.relative.replace(old, new))

    def test_function_or_axiom_change_rejected(self):
        for data in [self.relative.replace(b":= 1", b":= 0"), self.relative + b"axiom injected : False\n"]:
            with self.subTest(data=data), self.assertRaises(RuntimeError):
                self.check(data)

    def test_comment_delimiter_or_extra_text_rejected(self):
        for data in [self.relative.replace(b"3:0-4:1 -/", b"3:0-4:1"),
                     self.relative.replace(b"1:0-2:1\n", b"1:0-2:1 extra\n"),
                     self.relative.replace(b"/--", b"--")]:
            with self.subTest(data=data), self.assertRaises(RuntimeError):
                self.check(data)

    def test_source_like_executable_string_not_mapped(self):
        data = b'def s := "Source: \'' + self.relative_source + b'\', lines 1:0-2:1"\n'
        self.assertEqual(identity.canonicalize_iterator(data, self.checkout, self.cwd), (data, 0))

    def test_other_source_comment_not_mapped(self):
        data = self.relative.replace(self.relative_source, b"checkout/deps/ckb-vm/src/decoder.rs")
        self.assertEqual(identity.canonicalize_iterator(data, self.checkout, self.cwd), (data, 0))

    def test_equivalent_but_unexpected_path_spelling_rejected(self):
        with self.assertRaises(RuntimeError):
            self.check(self.relative.replace(b"checkout/proof/", b"checkout/./proof/"))


if __name__ == "__main__":
    unittest.main()
