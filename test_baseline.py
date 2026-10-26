import json
import tempfile
import unittest
from pathlib import Path

from baseline import BaselineError, load_baseline, save_baseline
from checker import scan_folder


class TestBaseline(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)
        self.baseline_file = self.dir / "baseline.json"

    def tearDown(self):
        self._tmp.cleanup()

    # ---- Step 4 tests ----
    def test_round_trip_keeps_hashes_exactly(self):
        hashes = {"a.txt": "aaa", "sub/b.txt": "bbb"}
        save_baseline(self.dir, hashes, self.baseline_file)
        data = load_baseline(self.baseline_file)
        self.assertEqual(data["files"], hashes)

    def test_saves_folder_and_created_time(self):
        save_baseline(self.dir, {}, self.baseline_file)
        data = load_baseline(self.baseline_file)
        self.assertEqual(data["folder"], str(self.dir.resolve()))
        self.assertTrue(data["created"])

    def test_empty_baseline_round_trip(self):
        save_baseline(self.dir, {}, self.baseline_file)
        self.assertEqual(load_baseline(self.baseline_file)["files"], {})

    def test_saved_file_is_valid_json(self):
        save_baseline(self.dir, {"a.txt": "aaa"}, self.baseline_file)
        data = json.loads(self.baseline_file.read_text())
        self.assertEqual(data["files"], {"a.txt": "aaa"})

    def test_saving_again_overwrites(self):
        save_baseline(self.dir, {"old.txt": "111"}, self.baseline_file)
        save_baseline(self.dir, {"new.txt": "222"}, self.baseline_file)
        self.assertEqual(load_baseline(self.baseline_file)["files"], {"new.txt": "222"})

    def test_missing_baseline_raises(self):
        with self.assertRaises(BaselineError):
            load_baseline(self.dir / "nope.json")

    def test_corrupted_baseline_raises(self):
        self.baseline_file.write_text("this is { not json")
        with self.assertRaises(BaselineError):
            load_baseline(self.baseline_file)

    def test_empty_baseline_file_raises(self):
        self.baseline_file.write_text("")
        with self.assertRaises(BaselineError):
            load_baseline(self.baseline_file)

    def test_wrong_structure_raises(self):
        self.baseline_file.write_text(json.dumps({"folder": "x", "created": "y"}))
        with self.assertRaises(BaselineError):
            load_baseline(self.baseline_file)

    def test_json_list_instead_of_object_raises(self):
        self.baseline_file.write_text(json.dumps(["a", "b"]))
        with self.assertRaises(BaselineError):
            load_baseline(self.baseline_file)

    def test_scan_save_load_matches_original_scan(self):
        watched = self.dir / "watched"
        (watched / "sub").mkdir(parents=True)
        (watched / "a.txt").write_text("one")
        (watched / "sub" / "b.txt").write_text("two")
        scanned = scan_folder(watched)
        save_baseline(watched, scanned, self.baseline_file)
        self.assertEqual(load_baseline(self.baseline_file)["files"], scanned)


if __name__ == "__main__":
    unittest.main()
