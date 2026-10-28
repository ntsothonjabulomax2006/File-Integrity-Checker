import hashlib
import json
import os
import unittest
from unittest import mock

import test_e2e


class SignedEndToEndTests(test_e2e.EndToEndTests):
    """Every end-to-end test again, with signing switched on, plus new ones."""

    # ---- Step 9b tests ----
    KEY = "correct horse battery staple"

    def setUp(self):
        super().setUp()
        patcher = mock.patch.dict(os.environ, {"INTEGRITY_KEY": self.KEY})
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_hand_edited_baseline_is_detected(self):
        """The attack from Step 8 (edit a file AND its hash) is now caught."""
        self.init()
        (self.watched / "notes.txt").write_text("evil")
        baseline = self.root / "baseline.json"
        data = json.loads(baseline.read_text())
        data["files"]["notes.txt"] = hashlib.sha256(b"evil").hexdigest()
        baseline.write_text(json.dumps(data))
        result = self.check()
        self.assertEqual(result.returncode, 2)
        self.assertIn("does not match", result.stderr)

    def test_init_creates_a_signature_file(self):
        result = self.init()
        self.assertEqual(result.returncode, 0)
        self.assertIn("Baseline signed", result.stdout)
        self.assertTrue((self.root / "baseline.json.sig").exists())

    def test_wrong_key_is_rejected(self):
        self.init()
        with mock.patch.dict(os.environ, {"INTEGRITY_KEY": "some other key"}):
            result = self.check()
        self.assertEqual(result.returncode, 2)
        self.assertIn("does not match", result.stderr)

    def test_signed_baseline_without_a_key_is_rejected(self):
        self.init()
        with mock.patch.dict(os.environ):
            os.environ.pop("INTEGRITY_KEY")
            result = self.check()
        self.assertEqual(result.returncode, 2)
        self.assertIn("is not set", result.stderr)

    def test_deleting_the_signature_is_caught(self):
        self.init()
        (self.root / "baseline.json.sig").unlink()
        result = self.check()
        self.assertEqual(result.returncode, 2)
        self.assertIn("has no signature", result.stderr)

    def test_update_refuses_a_tampered_baseline(self):
        self.init()
        baseline = self.root / "baseline.json"
        baseline.write_text(baseline.read_text() + " ")
        before = baseline.read_text()
        result = self.run_tool("update")
        self.assertEqual(result.returncode, 2)
        self.assertEqual(baseline.read_text(), before)

    def test_update_signs_the_new_baseline(self):
        self.init()
        sig = self.root / "baseline.json.sig"
        old_signature = sig.read_text()
        (self.watched / "notes.txt").write_text("changed")
        self.assertEqual(self.run_tool("update").returncode, 0)
        self.assertNotEqual(sig.read_text(), old_signature)
        self.assertEqual(self.check().returncode, 0)

    def test_the_key_is_never_written_to_disk(self):
        self.init()
        for name in ("baseline.json", "baseline.json.sig"):
            self.assertNotIn(self.KEY, (self.root / name).read_text())

    def test_init_force_without_a_key_removes_the_old_signature(self):
        self.init()
        with mock.patch.dict(os.environ):
            os.environ.pop("INTEGRITY_KEY")
            result = self.run_tool("init", self.watched, "--force")
            check = self.check()
        self.assertEqual(result.returncode, 0)
        self.assertFalse((self.root / "baseline.json.sig").exists())
        self.assertEqual(check.returncode, 0)


if __name__ == "__main__":
    unittest.main()
