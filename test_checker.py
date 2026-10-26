import contextlib
import hashlib
import io
import os
import tempfile
import unittest
from pathlib import Path

from checker import calculate_hash, scan_folder


class TempDirTestCase(unittest.TestCase):
    """Gives each test a fresh temporary folder."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def make_file(self, name, content):
        path = self.dir / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        return path


class TestCalculateHash(TempDirTestCase):
    # ---- Step 1 tests ----
    def test_known_hash(self):
        f = self.make_file("a.txt", b"hello")
        self.assertEqual(
            calculate_hash(f),
            "2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824",
        )

    def test_same_content_same_hash(self):
        a = self.make_file("a.txt", b"same")
        b = self.make_file("b.txt", b"same")
        self.assertEqual(calculate_hash(a), calculate_hash(b))

    def test_different_content_different_hash(self):
        a = self.make_file("a.txt", b"original")
        b = self.make_file("b.txt", b"tampered")
        self.assertNotEqual(calculate_hash(a), calculate_hash(b))

    def test_large_file_matches_hashlib(self):
        data = b"x" * 100_000  # bigger than the 4096-byte block size
        f = self.make_file("big.bin", data)
        self.assertEqual(calculate_hash(f), hashlib.sha256(data).hexdigest())

    # ---- Step 2 tests ----
    def test_missing_file_returns_none(self):
        with contextlib.redirect_stdout(io.StringIO()) as out:
            result = calculate_hash(self.dir / "nope.txt")
        self.assertIsNone(result)
        self.assertIn("not found", out.getvalue())

    def test_folder_returns_none(self):
        with contextlib.redirect_stdout(io.StringIO()):
            result = calculate_hash(self.dir)
        self.assertIsNone(result)

    @unittest.skipIf(os.name == "nt" or os.geteuid() == 0,
                     "permissions can't be tested on Windows or as root")
    def test_unreadable_file_returns_none(self):
        f = self.make_file("secret.txt", b"data")
        f.chmod(0o000)
        try:
            with contextlib.redirect_stdout(io.StringIO()) as out:
                result = calculate_hash(f)
            self.assertIsNone(result)
            self.assertIn("permission denied", out.getvalue())
        finally:
            f.chmod(0o644)  # so the temp folder can be cleaned up


class TestScanFolder(TempDirTestCase):
    # ---- Step 3 tests ----
    def test_hashes_files_in_folder_and_subfolders(self):
        self.make_file("a.txt", b"one")
        self.make_file("sub/b.txt", b"two")
        self.make_file("sub/deeper/c.txt", b"three")
        result = scan_folder(self.dir)
        self.assertEqual(set(result), {"a.txt", "sub/b.txt", "sub/deeper/c.txt"})

    def test_values_are_the_file_hashes(self):
        self.make_file("sub/b.txt", b"two")
        result = scan_folder(self.dir)
        self.assertEqual(result["sub/b.txt"], hashlib.sha256(b"two").hexdigest())

    def test_empty_folder_gives_empty_dict(self):
        self.assertEqual(scan_folder(self.dir), {})

    def test_empty_subfolders_are_not_listed(self):
        (self.dir / "emptydir").mkdir()
        self.make_file("a.txt", b"one")
        self.assertEqual(set(scan_folder(self.dir)), {"a.txt"})

    def test_ignored_folders_are_skipped(self):
        self.make_file("keep.txt", b"keep")
        self.make_file(".git/config", b"git stuff")
        self.make_file("__pycache__/x.pyc", b"cache")
        self.make_file("sub/__pycache__/y.pyc", b"cache")
        self.assertEqual(set(scan_folder(self.dir)), {"keep.txt"})

    def test_custom_ignore_list(self):
        self.make_file("a.txt", b"one")
        self.make_file("tmp/b.txt", b"two")
        result = scan_folder(self.dir, ignored_dirs={"tmp"})
        self.assertEqual(set(result), {"a.txt"})

    def test_results_are_in_sorted_order(self):
        self.make_file("b.txt", b"2")
        self.make_file("a.txt", b"1")
        self.make_file("c/d.txt", b"3")
        keys = list(scan_folder(self.dir))
        self.assertEqual(keys, sorted(keys))

    def test_missing_folder_raises(self):
        with self.assertRaises(NotADirectoryError):
            scan_folder(self.dir / "does_not_exist")

    def test_a_file_path_raises(self):
        f = self.make_file("a.txt", b"one")
        with self.assertRaises(NotADirectoryError):
            scan_folder(f)

    @unittest.skipIf(os.name == "nt" or os.geteuid() == 0,
                     "permissions can't be tested on Windows or as root")
    def test_unreadable_file_is_skipped(self):
        self.make_file("ok.txt", b"fine")
        bad = self.make_file("secret.txt", b"data")
        bad.chmod(0o000)
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                result = scan_folder(self.dir)
            self.assertEqual(set(result), {"ok.txt"})
        finally:
            bad.chmod(0o644)


if __name__ == "__main__":
    unittest.main()
