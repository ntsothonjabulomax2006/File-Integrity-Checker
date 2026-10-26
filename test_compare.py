import tempfile
import unittest
from pathlib import Path

from baseline import BaselineError, save_baseline
from checker import scan_folder
from compare import check_folder, compare_hashes


class TestCompareHashes(unittest.TestCase):
    # ---- Step 5 tests: the comparison logic ----
    def test_identical_is_all_unchanged(self):
        d = {"a.txt": "1", "b.txt": "2"}
        r = compare_hashes(d, dict(d))
        self.assertEqual(r["unchanged"], ["a.txt", "b.txt"])
        self.assertEqual((r["modified"], r["missing"], r["new"]), ([], [], []))

    def test_detects_modified(self):
        r = compare_hashes({"a.txt": "1", "b.txt": "2"}, {"a.txt": "1", "b.txt": "CHANGED"})
        self.assertEqual(r["modified"], ["b.txt"])
        self.assertEqual(r["unchanged"], ["a.txt"])

    def test_detects_missing(self):
        r = compare_hashes({"a.txt": "1", "b.txt": "2"}, {"a.txt": "1"})
        self.assertEqual(r["missing"], ["b.txt"])

    def test_detects_new(self):
        r = compare_hashes({"a.txt": "1"}, {"a.txt": "1", "c.txt": "3"})
        self.assertEqual(r["new"], ["c.txt"])

    def test_all_four_at_once(self):
        old = {"same.txt": "1", "edited.txt": "2", "gone.txt": "3"}
        new = {"same.txt": "1", "edited.txt": "X", "added.txt": "4"}
        r = compare_hashes(old, new)
        self.assertEqual(r["unchanged"], ["same.txt"])
        self.assertEqual(r["modified"], ["edited.txt"])
        self.assertEqual(r["missing"], ["gone.txt"])
        self.assertEqual(r["new"], ["added.txt"])

    def test_both_empty(self):
        r = compare_hashes({}, {})
        self.assertEqual(r, {"unchanged": [], "modified": [], "missing": [], "new": []})

    def test_empty_baseline_makes_everything_new(self):
        r = compare_hashes({}, {"a.txt": "1", "b.txt": "2"})
        self.assertEqual(r["new"], ["a.txt", "b.txt"])

    def test_everything_deleted(self):
        r = compare_hashes({"a.txt": "1", "b.txt": "2"}, {})
        self.assertEqual(r["missing"], ["a.txt", "b.txt"])

    def test_rename_is_one_missing_plus_one_new(self):
        r = compare_hashes({"old.txt": "1"}, {"renamed.txt": "1"})
        self.assertEqual(r["missing"], ["old.txt"])
        self.assertEqual(r["new"], ["renamed.txt"])

    def test_results_are_sorted(self):
        r = compare_hashes({}, {"c.txt": "1", "a.txt": "2", "b.txt": "3"})
        self.assertEqual(r["new"], ["a.txt", "b.txt", "c.txt"])


class TestCheckFolder(unittest.TestCase):
    # ---- Step 5 tests: the whole check on a real folder ----
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.watched = self.root / "watched"
        (self.watched / "sub").mkdir(parents=True)
        (self.watched / "a.txt").write_text("one")
        (self.watched / "sub" / "b.txt").write_text("two")
        self.baseline_file = self.root / "baseline.json"
        save_baseline(self.watched, scan_folder(self.watched), self.baseline_file)

    def tearDown(self):
        self._tmp.cleanup()

    def check(self):
        return check_folder(self.baseline_file)[1]

    def test_no_changes(self):
        r = self.check()
        self.assertEqual(r["unchanged"], ["a.txt", "sub/b.txt"])
        self.assertEqual((r["modified"], r["missing"], r["new"]), ([], [], []))

    def test_edited_file_is_modified(self):
        (self.watched / "a.txt").write_text("one - tampered")
        self.assertEqual(self.check()["modified"], ["a.txt"])

    def test_edited_file_in_subfolder_is_modified(self):
        (self.watched / "sub" / "b.txt").write_text("changed")
        self.assertEqual(self.check()["modified"], ["sub/b.txt"])

    def test_deleted_file_is_missing(self):
        (self.watched / "a.txt").unlink()
        self.assertEqual(self.check()["missing"], ["a.txt"])

    def test_added_file_is_new(self):
        (self.watched / "extra.txt").write_text("hello")
        self.assertEqual(self.check()["new"], ["extra.txt"])

    def test_returns_baseline_data_too(self):
        data, _ = check_folder(self.baseline_file)
        self.assertEqual(data["folder"], str(self.watched.resolve()))

    def test_baseline_inside_watched_folder_is_ignored(self):
        inside = self.watched / "baseline.json"
        save_baseline(self.watched, scan_folder(self.watched), inside)
        # the baseline file now exists in the folder; a second baseline saved
        # while it exists would list it, so save again to cover that case
        save_baseline(self.watched, scan_folder(self.watched), inside)
        r = check_folder(inside)[1]
        self.assertEqual((r["modified"], r["missing"], r["new"]), ([], [], []))

    def test_missing_baseline_raises(self):
        with self.assertRaises(BaselineError):
            check_folder(self.root / "nope.json")

    def test_deleted_watched_folder_raises(self):
        for p in sorted(self.watched.rglob("*"), reverse=True):
            p.rmdir() if p.is_dir() else p.unlink()
        self.watched.rmdir()
        with self.assertRaises(NotADirectoryError):
            self.check()


if __name__ == "__main__":
    unittest.main()
