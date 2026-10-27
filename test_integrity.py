import contextlib
import io
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from integrity import main

PROJECT_DIR = Path(__file__).parent


class TestCommands(unittest.TestCase):
    # ---- Step 7 tests ----
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.watched = self.root / "watched"
        (self.watched / "sub").mkdir(parents=True)
        (self.watched / "a.txt").write_text("one")
        (self.watched / "sub" / "b.txt").write_text("two")
        self.bf = self.root / "baseline.json"

    def tearDown(self):
        self._tmp.cleanup()

    def run_cli(self, *args):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = main([str(a) for a in args])
        return code, out.getvalue(), err.getvalue()

    def init(self):
        return self.run_cli("init", self.watched, "--baseline", self.bf)

    def check(self, *extra):
        return self.run_cli("check", "--baseline", self.bf, *extra)

    def update(self):
        return self.run_cli("update", "--baseline", self.bf)

    # init
    def test_init_creates_baseline(self):
        code, out, _ = self.init()
        self.assertEqual(code, 0)
        self.assertIn("Baseline created for 2 files", out)
        files = json.loads(self.bf.read_text())["files"]
        self.assertEqual(set(files), {"a.txt", "sub/b.txt"})

    def test_init_on_missing_folder_is_an_error(self):
        code, _, err = self.run_cli("init", self.root / "nope", "--baseline", self.bf)
        self.assertEqual(code, 2)
        self.assertIn("Not a folder", err)
        self.assertFalse(self.bf.exists())

    def test_init_refuses_to_overwrite_existing_baseline(self):
        self.init()
        before = self.bf.read_text()
        (self.watched / "extra.txt").write_text("x")
        code, _, err = self.init()
        self.assertEqual(code, 2)
        self.assertIn("already exists", err)
        self.assertEqual(self.bf.read_text(), before)

    def test_init_force_replaces_baseline(self):
        self.init()
        (self.watched / "extra.txt").write_text("x")
        code, _, _ = self.run_cli("init", self.watched, "--baseline", self.bf, "--force")
        self.assertEqual(code, 0)
        self.assertIn("extra.txt", json.loads(self.bf.read_text())["files"])

    def test_init_leaves_baseline_inside_folder_out_of_the_hashes(self):
        inside = self.watched / "baseline.json"
        self.run_cli("init", self.watched, "--baseline", inside)
        self.run_cli("init", self.watched, "--baseline", inside, "--force")
        self.assertNotIn("baseline.json", json.loads(inside.read_text())["files"])

    # check
    def test_check_clean_exits_0(self):
        self.init()
        code, out, _ = self.check()
        self.assertEqual(code, 0)
        self.assertIn("STATUS: OK", out)

    def test_check_modified_exits_1(self):
        self.init()
        (self.watched / "a.txt").write_text("tampered")
        code, out, _ = self.check()
        self.assertEqual(code, 1)
        self.assertIn("[MODIFIED]\n  - a.txt", out)

    def test_check_missing_exits_1(self):
        self.init()
        (self.watched / "a.txt").unlink()
        code, out, _ = self.check()
        self.assertEqual(code, 1)
        self.assertIn("[MISSING]\n  - a.txt", out)

    def test_check_new_exits_1(self):
        self.init()
        (self.watched / "extra.txt").write_text("x")
        code, out, _ = self.check()
        self.assertEqual(code, 1)
        self.assertIn("[NEW]\n  - extra.txt", out)

    def test_check_saves_report_file(self):
        self.init()
        (self.watched / "a.txt").write_text("tampered")
        report = self.root / "report.txt"
        code, out, _ = self.check("--report", report)
        self.assertEqual(code, 1)
        self.assertIn("Report saved", out)
        self.assertIn("[MODIFIED]", report.read_text())

    def test_check_without_baseline_is_a_friendly_error(self):
        code, out, err = self.check()
        self.assertEqual(code, 2)
        self.assertIn("No baseline found", err)
        self.assertNotIn("Traceback", out + err)

    def test_check_with_corrupted_baseline_is_a_friendly_error(self):
        self.bf.write_text("garbage {")
        code, _, err = self.check()
        self.assertEqual(code, 2)
        self.assertIn("corrupted", err)

    def test_check_when_folder_was_deleted_is_an_error(self):
        self.init()
        for p in sorted(self.watched.rglob("*"), reverse=True):
            p.rmdir() if p.is_dir() else p.unlink()
        self.watched.rmdir()
        code, _, err = self.check()
        self.assertEqual(code, 2)
        self.assertIn("Not a folder", err)

    # update
    def test_update_accepts_changes(self):
        self.init()
        (self.watched / "a.txt").write_text("tampered")
        (self.watched / "sub" / "b.txt").unlink()
        (self.watched / "extra.txt").write_text("x")
        self.assertEqual(self.check()[0], 1)
        code, out, _ = self.update()
        self.assertEqual(code, 0)
        self.assertIn("1 modified, 1 missing, 1 new accepted", out)
        self.assertEqual(self.check()[0], 0)

    def test_update_without_baseline_is_an_error(self):
        code, _, err = self.update()
        self.assertEqual(code, 2)
        self.assertIn("No baseline found", err)

    # usage
    def test_no_command_shows_usage_error(self):
        with contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as cm:
                main([])
        self.assertEqual(cm.exception.code, 2)

    def test_unknown_command_shows_usage_error(self):
        with contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as cm:
                main(["explode"])
        self.assertEqual(cm.exception.code, 2)

    # the real script
    def test_real_script_exit_codes(self):
        self.init()
        cmd = [sys.executable, "integrity.py", "check", "--baseline", str(self.bf)]
        clean = subprocess.run(cmd, cwd=PROJECT_DIR, capture_output=True, text=True)
        self.assertEqual(clean.returncode, 0)
        (self.watched / "a.txt").write_text("tampered")
        dirty = subprocess.run(cmd, cwd=PROJECT_DIR, capture_output=True, text=True)
        self.assertEqual(dirty.returncode, 1)
        self.assertIn("CHANGES DETECTED", dirty.stdout)


if __name__ == "__main__":
    unittest.main()
