import hashlib
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


if __name__ == "__main__":
    unittest.main()