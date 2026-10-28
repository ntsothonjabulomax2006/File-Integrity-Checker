import tempfile
import unittest
from pathlib import Path

from baseline import BaselineError
from signing import (
    KEY_ENV_VAR,
    SignatureError,
    compute_signature,
    get_key,
    sign_baseline,
    signature_path,
    verify_baseline,
)

KEY = b"correct horse battery staple"


class TestSigning(unittest.TestCase):
    # ---- Step 9a tests ----
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)
        self.bf = self.dir / "baseline.json"
        self.bf.write_text('{"folder": "x", "created": "y", "files": {}}')

    def tearDown(self):
        self._tmp.cleanup()

    # get_key
    def test_get_key_returns_none_when_unset(self):
        self.assertIsNone(get_key({}))

    def test_get_key_returns_none_when_empty(self):
        self.assertIsNone(get_key({KEY_ENV_VAR: ""}))

    def test_get_key_returns_bytes_when_set(self):
        self.assertEqual(get_key({KEY_ENV_VAR: "abc"}), b"abc")

    # signature_path / compute_signature
    def test_signature_file_sits_next_to_the_baseline(self):
        self.assertEqual(signature_path(self.bf), self.dir / "baseline.json.sig")

    def test_signature_is_64_hex_characters(self):
        sig = compute_signature(self.bf, KEY)
        self.assertEqual(len(sig), 64)
        int(sig, 16)  # raises if it is not hex

    def test_same_content_and_key_give_the_same_signature(self):
        self.assertEqual(compute_signature(self.bf, KEY), compute_signature(self.bf, KEY))

    def test_different_key_gives_a_different_signature(self):
        self.assertNotEqual(compute_signature(self.bf, KEY), compute_signature(self.bf, b"other"))

    def test_different_content_gives_a_different_signature(self):
        before = compute_signature(self.bf, KEY)
        self.bf.write_text('{"folder": "x", "created": "y", "files": {"a": "1"}}')
        self.assertNotEqual(before, compute_signature(self.bf, KEY))

    # verify_baseline
    def test_signed_baseline_verifies(self):
        sign_baseline(self.bf, KEY)
        verify_baseline(self.bf, KEY)  # no error

    def test_signing_writes_the_signature_file(self):
        sign_baseline(self.bf, KEY)
        self.assertEqual(signature_path(self.bf).read_text().strip(), compute_signature(self.bf, KEY))

    def test_modified_baseline_is_rejected(self):
        sign_baseline(self.bf, KEY)
        self.bf.write_text(self.bf.read_text() + " ")
        with self.assertRaises(SignatureError):
            verify_baseline(self.bf, KEY)

    def test_wrong_key_is_rejected(self):
        sign_baseline(self.bf, KEY)
        with self.assertRaises(SignatureError):
            verify_baseline(self.bf, b"some other key")

    def test_garbage_signature_is_rejected(self):
        sign_baseline(self.bf, KEY)
        signature_path(self.bf).write_text("not a real signature\n")
        with self.assertRaises(SignatureError):
            verify_baseline(self.bf, KEY)

    def test_signed_baseline_without_a_key_is_rejected(self):
        sign_baseline(self.bf, KEY)
        with self.assertRaises(SignatureError):
            verify_baseline(self.bf, None)

    def test_missing_signature_with_a_key_is_rejected(self):
        with self.assertRaises(SignatureError):
            verify_baseline(self.bf, KEY)

    def test_unsigned_mode_needs_nothing(self):
        verify_baseline(self.bf, None)  # no key, no signature: fine

    def test_missing_baseline_is_left_for_load_baseline_to_report(self):
        verify_baseline(self.dir / "nope.json", KEY)  # no error

    def test_signature_error_is_a_baseline_error(self):
        self.assertTrue(issubclass(SignatureError, BaselineError))


if __name__ == "__main__":
    unittest.main()
