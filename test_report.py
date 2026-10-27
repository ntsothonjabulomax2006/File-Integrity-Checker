import tempfile
import unittest
from pathlib import Path

from baseline import save_baseline
from checker import scan_folder
from compare import check_folder
from report import build_report, has_changes, save_report

CLEAN = {"unchanged": ["a.txt", "b.txt"], "modified": [], "missing": [], "new": []}
DIRTY = {
    "unchanged": ["same.txt"],
    "modified": ["edited.txt"],
    "missing": ["gone.txt"],
    "new": ["added.txt"],
}


class TestHasChanges(unittest.TestCase):
    # ---- Step 6 tests ----
    def test_clean_has_no_changes(self):
        self.assertFalse(has_changes(CLEAN))

    def test_each_kind_of_change_counts(self):
        for key in ("modified", "missing", "new"):
            result = {"unchanged": [], "modified": [], "missing": [], "new": []}
            result[key] = ["x.txt"]
            self.assertTrue(has_changes(result), key)


class TestBuildReport(unittest.TestCase):
    def report(self, result, **kwargs):
        return build_report("/some/folder", "2026-01-01T10:00:00", result, **kwargs)

    def test_clean_report_says_ok(self):
        text = self.report(CLEAN)
        self.assertIn("STATUS: OK - no changes detected", text)
        self.assertNotIn("CHANGES DETECTED", text)

    def test_dirty_report_says_changes_detected(self):
        text = self.report(DIRTY)
        self.assertIn("STATUS: CHANGES DETECTED", text)
        self.assertNotIn("STATUS: OK", text)

    def test_counts_are_correct(self):
        text = self.report(DIRTY)
        self.assertIn("Unchanged: 1", text)
        self.assertIn("Modified:  1", text)
        self.assertIn("Missing:   1", text)
        self.assertIn("New:       1", text)

    def test_changed_files_are_listed_under_their_headings(self):
        text = self.report(DIRTY)
        self.assertIn("[MODIFIED]\n  - edited.txt", text)
        self.assertIn("[MISSING]\n  - gone.txt", text)
        self.assertIn("[NEW]\n  - added.txt", text)

    def test_unchanged_files_are_counted_but_not_listed(self):
        text = self.report(DIRTY)
        self.assertNotIn("same.txt", text)

    def test_empty_sections_have_no_heading(self):
        text = self.report(CLEAN)
        for heading in ("[MODIFIED]", "[MISSING]", "[NEW]"):
            self.assertNotIn(heading, text)

    def test_only_sections_with_files_appear(self):
        result = {"unchanged": [], "modified": ["a.txt"], "missing": [], "new": []}
        text = self.report(result)
        self.assertIn("[MODIFIED]", text)
        self.assertNotIn("[MISSING]", text)
        self.assertNotIn("[NEW]", text)

    def test_shows_folder_and_baseline_time(self):
        text = self.report(CLEAN)
        self.assertIn("Folder:        /some/folder", text)
        self.assertIn("Baseline from: 2026-01-01T10:00:00", text)

    def test_checked_at_can_be_given(self):
        text = self.report(CLEAN, checked_at="2026-02-02T09:30:00")
        self.assertIn("Checked at:    2026-02-02T09:30:00", text)

    def test_checked_at_defaults_to_now(self):
        self.assertIn("Checked at:    20", self.report(CLEAN))

    def test_multiple_files_keep_their_order(self):
        result = {"unchanged": [], "modified": ["a.txt", "b.txt", "c.txt"],
                  "missing": [], "new": []}
        text = self.report(result)
        self.assertLess(text.index("a.txt"), text.index("b.txt"))
        self.assertLess(text.index("b.txt"), text.index("c.txt"))


class TestSaveReport(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_saved_file_matches_the_report(self):
        text = build_report("/f", "2026-01-01T10:00:00", DIRTY)
        target = self.dir / "report.txt"
        save_report(text, target)
        self.assertEqual(target.read_text(), text + "\n")

    def test_saving_again_overwrites(self):
        target = self.dir / "report.txt"
        save_report("first", target)
        save_report("second", target)
        self.assertEqual(target.read_text(), "second\n")


class TestReportOnRealFolder(unittest.TestCase):
    def test_full_scenario_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            watched = root / "watched"
            watched.mkdir()
            (watched / "keep.txt").write_text("same")
            (watched / "edit.txt").write_text("before")
            (watched / "delete.txt").write_text("bye")
            baseline_file = root / "baseline.json"
            save_baseline(watched, scan_folder(watched), baseline_file)

            (watched / "edit.txt").write_text("after")
            (watched / "delete.txt").unlink()
            (watched / "add.txt").write_text("hello")

            data, result = check_folder(baseline_file)
            text = build_report(data["folder"], data["created"], result)

        self.assertIn("STATUS: CHANGES DETECTED", text)
        self.assertIn("[MODIFIED]\n  - edit.txt", text)
        self.assertIn("[MISSING]\n  - delete.txt", text)
        self.assertIn("[NEW]\n  - add.txt", text)
        self.assertIn("Unchanged: 1", text)


if __name__ == "__main__":
    unittest.main()
