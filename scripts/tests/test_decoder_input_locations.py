"""Moving verified std files must not allow extraction flags to change."""
import copy
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import decoder_input_locations as locations


class LocationTests(unittest.TestCase):
    def setUp(self):
        self.old = {"has_errors": False, "charon_version": "0.1.247", "translated": {
            "crate_name": "outer_decoder_probe", "target_information": {"pointer_size": 64},
            "options": {"sysroot": "/legacy/std", "dest_file": "/old/Outer.llbc",
                        "include": ["ckb_vm::decoder::_"], "opaque": ["ckb_vm::memory::_"],
                        "exclude": [], "skip_borrowck": False, "no_typecheck": False}}}
        self.fresh = copy.deepcopy(self.old)
        self.fresh["translated"]["options"].update(sysroot="/installed/std", dest_file="/new/Outer.llbc")

    def test_only_two_verified_locations_can_vary(self):
        old, new = copy.deepcopy(self.old), copy.deepcopy(self.fresh)
        result = locations._compare_metadata(self.old, self.fresh, "/installed/std")
        self.assertTrue(result["only_sysroot_location_and_output_path_vary"])
        self.assertEqual(self.old, old)
        self.assertEqual(self.fresh, new)

    def test_unverified_location_rejected(self):
        with self.assertRaisesRegex(RuntimeError, "verified installed sysroot"):
            locations._compare_metadata(self.old, self.fresh, "/some/other/std")

    def test_extraction_flag_drift_rejected(self):
        for key, value in [("include", []), ("opaque", ["ckb_vm::decoder::_"]),
                           ("exclude", ["ckb_vm::_"]), ("skip_borrowck", True), ("no_typecheck", True)]:
            fresh = copy.deepcopy(self.fresh)
            fresh["translated"]["options"][key] = value
            with self.subTest(key=key), self.assertRaises(RuntimeError):
                locations._compare_metadata(self.old, fresh, "/installed/std")

    def test_format_or_error_drift_rejected(self):
        for key, value in [("has_errors", True), ("charon_version", "different")]:
            fresh = copy.deepcopy(self.fresh)
            fresh[key] = value
            with self.subTest(key=key), self.assertRaises(RuntimeError):
                locations._compare_metadata(self.old, fresh, "/installed/std")

    def test_target_change_rejected(self):
        self.fresh["translated"]["target_information"]["pointer_size"] = 32
        with self.assertRaises(RuntimeError):
            locations._compare_metadata(self.old, self.fresh, "/installed/std")

    def test_public_entry_validates_payload_before_reading_archive(self):
        with patch.object(locations, "load", side_effect=RuntimeError("unverified bundle")) as load:
            with self.assertRaisesRegex(RuntimeError, "unverified bundle"):
                locations.check_extraction(self.fresh, "/not/installed")
            load.assert_called_once_with("/not/installed")

    def test_unknown_root_rejected(self):
        with self.assertRaisesRegex(RuntimeError, "unknown extraction root"):
            locations.check_extraction(self.fresh, "/not/installed", "../../replacement.llbc")


if __name__ == "__main__":
    unittest.main()
