import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = str(Path(__file__).parent / "integrity.py")


class EndToEndTests(unittest.TestCase):
    """Run the real script the way a user would, in a throwaway folder."""

    # ---- Step 8 tests ----
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)  # where the tool is "run" from
        self.watched = self.root / "watched"
        (self.watched / "docs").mkdir(parents=True)
        (self.watched / "notes.txt").write_text("Meeting notes")
        (self.watched / "data.csv").write_text("id,name\n1,Alice\n")
        (self.watched / "docs" / "guide.txt").write_text("Read the guide")

    def tearDown(self):
        self._tmp.cleanup()

    def run_tool(self, *args):
        return subprocess.run(
            [sys.executable, SCRIPT, *[str(a) for a in args]],
            cwd=self.root,
            capture_output=True,
            text=True,
            encoding="utf-8",
            env={**os.environ, "PYTHONIOENCODING": "utf-8"},
        )

    def init(self):
        return self.run_tool("init", self.watched)

    def check(self, *extra):
        return self.run_tool("check", *extra)

    def test_full_lifecycle(self):
        self.assertEqual(self.init().returncode, 0)
        self.assertEqual(self.check().returncode, 0)

        (self.watched / "notes.txt").write_text("Meeting notes - TAMPERED")
        result = self.check()
        self.assertEqual(result.returncode, 1)
        self.assertIn("[MODIFIED]\n  - notes.txt", result.stdout)

        self.assertEqual(self.run_tool("update").returncode, 0)
        self.assertEqual(self.check().returncode, 0)

    def test_modified_missing_and_new_at_once(self):
        self.init()
        (self.watched / "notes.txt").write_text("changed")
        (self.watched / "docs" / "guide.txt").unlink()
        (self.watched / "docs" / "extra.txt").write_text("brand new")
        result = self.check()
        self.assertEqual(result.returncode, 1)
        self.assertIn("[MODIFIED]\n  - notes.txt", result.stdout)
        self.assertIn("[MISSING]\n  - docs/guide.txt", result.stdout)
        self.assertIn("[NEW]\n  - docs/extra.txt", result.stdout)
        self.assertIn("Unchanged: 1", result.stdout)

    def test_rename_is_missing_plus_new(self):
        self.init()
        (self.watched / "notes.txt").rename(self.watched / "renamed.txt")
        result = self.check()
        self.assertEqual(result.returncode, 1)
        self.assertIn("[MISSING]\n  - notes.txt", result.stdout)
        self.assertIn("[NEW]\n  - renamed.txt", result.stdout)

    def test_same_length_change_is_detected(self):
        (self.watched / "notes.txt").write_text("aaaa")
        self.init()
        (self.watched / "notes.txt").write_text("bbbb")
        self.assertEqual(self.check().returncode, 1)

    def test_one_byte_change_in_a_large_file_is_detected(self):
        big = self.watched / "big.bin"
        big.write_bytes(bytes(100_000))
        self.init()
        data = bytearray(big.read_bytes())
        data[50_000] ^= 1
        big.write_bytes(bytes(data))
        result = self.check()
        self.assertEqual(result.returncode, 1)
        self.assertIn("[MODIFIED]\n  - big.bin", result.stdout)

    def test_touching_a_file_without_changing_it_is_not_a_change(self):
        self.init()
        os.utime(self.watched / "notes.txt", (1_000_000_000, 1_000_000_000))
        self.assertEqual(self.check().returncode, 0)

    def test_spaces_and_unicode_in_file_names(self):
        (self.watched / "my notes (final).txt").write_text("one")
        (self.watched / "caf\u00e9.txt").write_text("two")
        self.init()
        (self.watched / "caf\u00e9.txt").write_text("changed")
        result = self.check()
        self.assertEqual(result.returncode, 1)
        self.assertIn("[MODIFIED]\n  - caf\u00e9.txt", result.stdout)
        self.assertNotIn("my notes (final).txt", result.stdout.split("[MODIFIED]")[1])

    def test_changes_inside_ignored_folders_are_not_reported(self):
        (self.watched / ".git").mkdir()
        (self.watched / ".git" / "config").write_text("before")
        self.init()
        (self.watched / ".git" / "config").write_text("after")
        self.assertEqual(self.check().returncode, 0)

    def test_empty_folder(self):
        empty = self.root / "empty"
        empty.mkdir()
        result = self.run_tool("init", empty)
        self.assertEqual(result.returncode, 0)
        self.assertIn("0 files", result.stdout)
        self.assertEqual(self.check().returncode, 0)
        (empty / "first.txt").write_text("hello")
        result = self.check()
        self.assertEqual(result.returncode, 1)
        self.assertIn("[NEW]\n  - first.txt", result.stdout)

    def test_deleted_folder_is_an_error(self):
        self.init()
        shutil.rmtree(self.watched)
        result = self.check()
        self.assertEqual(result.returncode, 2)
        self.assertIn("Not a folder", result.stderr)
        self.assertNotIn("Traceback", result.stderr)

    def test_baseline_defaults_to_the_working_directory(self):
        self.init()
        self.assertTrue((self.root / "baseline.json").exists())

    def test_report_option_writes_a_file(self):
        self.init()
        (self.watched / "notes.txt").write_text("changed")
        result = self.check("--report", "out.txt")
        self.assertEqual(result.returncode, 1)
        self.assertIn("[MODIFIED]", (self.root / "out.txt").read_text(encoding="utf-8"))

    def test_many_files(self):
        for i in range(300):
            folder = self.watched / f"dir{i % 10}"
            folder.mkdir(exist_ok=True)
            (folder / f"file{i}.txt").write_text(f"content {i}")
        self.assertIn("303 files", self.init().stdout)
        (self.watched / "dir3" / "file3.txt").write_text("changed")
        result = self.check()
        self.assertEqual(result.returncode, 1)
        self.assertIn("Modified:  1", result.stdout)
        self.assertIn("Unchanged: 302", result.stdout)

    def test_update_with_no_changes_is_harmless(self):
        self.init()
        result = self.run_tool("update")
        self.assertEqual(result.returncode, 0)
        self.assertIn("0 modified, 0 missing, 0 new accepted", result.stdout)
        self.assertEqual(self.check().returncode, 0)

    def test_checking_twice_gives_the_same_answer(self):
        self.init()
        self.assertEqual(self.check().returncode, 0)
        self.assertEqual(self.check().returncode, 0)

    @unittest.expectedFailure
    def test_hand_edited_baseline_is_detected(self):
        """KNOWN GAP, fixed in Step 9.

        Today, an attacker who edits a file AND rewrites its hash in
        baseline.json hides the change completely. This test describes the
        behaviour we want; it is marked as an expected failure until Step 9.
        """
        self.init()
        (self.watched / "notes.txt").write_text("evil")
        baseline = self.root / "baseline.json"
        data = json.loads(baseline.read_text())
        data["files"]["notes.txt"] = hashlib.sha256(b"evil").hexdigest()
        baseline.write_text(json.dumps(data))
        self.assertNotEqual(self.check().returncode, 0)


if __name__ == "__main__":
    unittest.main()
