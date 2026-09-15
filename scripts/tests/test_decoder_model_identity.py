"""Only a generated doc-comment's checkout prefix may vary."""
import hashlib
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import decoder_model_identity as identity


class ModelIdentityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="model-identity-test-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.checkout = self.root / "new-checkout"
        self.legacy = ("/-- [ckb_vm::example]\n    Source: '" + identity.LEGACY_CHECKOUT +
                       "/deps/ckb-vm/src/decoder.rs', lines 1:0-2:1\n"
                       "    Visibility: public -/\ndef example : Nat := 1\n").encode()
        self.relocated = self.legacy.replace(identity.LEGACY_CHECKOUT.encode(), str(self.checkout).encode())
        self.model = self.root / "Example.lean"
        approved = patch.object(identity, "APPROVED_SHA256", hashlib.sha256(self.legacy).hexdigest())
        approved.start()
        self.addCleanup(approved.stop)

    def check(self, data):
        self.model.write_bytes(data)
        return identity.check(self.model, self.checkout)

    def test_only_checkout_prefix_is_mapped(self):
        actual = self.check(self.relocated)
        self.assertEqual(actual["source_comment_count"], 1)
        self.assertEqual(actual["canonical_sha256"], hashlib.sha256(self.legacy).hexdigest())
        self.assertEqual(self.model.read_bytes(), self.relocated)
        self.assertFalse(actual["generated_file_edited"])

    def test_legacy_bytes_keep_the_original_identity(self):
        self.assertEqual(self.check(self.legacy)["source_comment_count"], 0)

    def test_wrong_function_body_is_not_ignored(self):
        with self.assertRaises(RuntimeError):
            self.check(self.relocated.replace(b":= 1", b":= 2"))

    def test_line_column_filename_and_attributes_are_not_ignored(self):
        for old, new in [(b"1:0-2:1", b"1:0-3:1"), (b"decoder.rs", b"replacement.rs"),
                         (b"Visibility: public", b"Visibility: private")]:
            with self.subTest(old=old), self.assertRaises(RuntimeError):
                self.check(self.relocated.replace(old, new))

    def test_comment_delimiter_change_is_not_ignored(self):
        with self.assertRaises(RuntimeError):
            self.check(self.relocated.replace(b"/-", b"--"))

    def test_other_source_location_is_not_ignored(self):
        with self.assertRaises(RuntimeError):
            self.check(self.relocated.replace(str(self.checkout).encode(), b"/other/check-out"))

    def test_source_like_executable_text_is_not_mapped(self):
        data = ('def s := "Source: \'' + str(self.checkout) +
                '/deps/ckb-vm/src/decoder.rs\', lines 1:0-2:1"\n').encode()
        self.assertEqual(identity.canonicalize(data, self.checkout), (data, 0))

    def test_inline_or_extended_source_comment_is_not_mapped(self):
        for data in [self.relocated.replace(b"    Source:", b" -- Source:"),
                     self.relocated.replace(b"lines 1:0-2:1\n", b"lines 1:0-2:1 extra\n")]:
            with self.subTest(data=data), self.assertRaises(RuntimeError):
                self.check(data)

    def test_changed_non_source_bytes_fail(self):
        with self.assertRaises(RuntimeError):
            self.check(self.relocated + b"axiom injected : False\n")


if __name__ == "__main__":
    unittest.main()
