import contextlib
import hashlib
import io
import os
import tempfile
import unittest
from pathlib import Path

from checker import calculate_hash


class TestCalculateHash(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def make_file(self, name, content):
        path = self.dir / name
        path.write_bytes(content)
        return path

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


if __name__ == "__main__":
    unittest.main()