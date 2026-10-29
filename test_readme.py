import os
import re
import shlex
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from integrity import build_parser

ROOT = Path(__file__).parent
README = (ROOT / "README.md").read_text(encoding="utf-8")
RUNTIME_FILES = [
    "integrity.py",
    "checker.py",
    "baseline.py",
    "compare.py",
    "report.py",
    "signing.py",
]
FENCE = re.compile(r"^```(?P<info>[^\n]*)\n(?P<body>.*?)^```", re.S | re.M)


def code_blocks():
    return [(m["info"].strip(), m["body"]) for m in FENCE.finditer(README)]


class TestReadme(unittest.TestCase):
    # ---- Step 10 tests ----
    def test_has_all_the_main_sections(self):
        headings = [
            "# File Integrity Checker",
            "## What it does",
            "## How it works",
            "## Requirements",
            "## Quick start",
            "## Commands",
            "## Protecting the baseline (signing)",
            "## Exit codes",
            "## Project structure",
            "## Running the tests",
            "## Security notes and limitations",
            "## Ideas for the future",
        ]
        for heading in headings:
            self.assertIn(heading + "\n", README, heading)

    def test_every_documented_command_matches_the_real_cli(self):
        parser = build_parser()
        checked = 0
        for info, body in code_blocks():
            if not info.startswith("bash"):
                continue
            for line in body.splitlines():
                if not line.startswith("python3 integrity.py"):
                    continue
                tokens = shlex.split(line, comments=True)
                if "||" in tokens:
                    tokens = tokens[: tokens.index("||")]
                parser.parse_args(tokens[2:])  # exits with an error if the docs are wrong
                checked += 1
        self.assertGreaterEqual(checked, 8)

    def test_the_quick_start_really_runs(self):
        scripts = [body for info, body in code_blocks() if info == "bash quickstart"]
        self.assertEqual(len(scripts), 1)
        env = {k: v for k, v in os.environ.items() if k != "INTEGRITY_KEY"}
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            for name in RUNTIME_FILES:
                shutil.copy(ROOT / name, tmp)
            shutil.copytree(ROOT / "sample_data", tmp / "sample_data")
            result = subprocess.run(
                ["bash", "-e", "-c", scripts[0]],
                cwd=tmp,
                capture_output=True,
                text=True,
                env=env,
            )
        self.assertEqual(result.returncode, 0, result.stderr)
        out = result.stdout
        self.assertRegex(out, r"Baseline created for \d+ files")
        self.assertIn("STATUS: OK - no changes detected", out)
        self.assertIn("STATUS: CHANGES DETECTED", out)
        self.assertIn("[MODIFIED]\n  - notes.txt", out)
        self.assertIn("exit code: 1", out)
        self.assertIn("Baseline updated", out)

    def test_documents_the_signing_key_and_exit_codes(self):
        self.assertIn("INTEGRITY_KEY", README)
        self.assertIn("baseline.json.sig", README)
        for phrase in ("No changes detected", "Changes detected", "Error"):
            self.assertIn(phrase, README)

    def test_mentions_every_project_file_and_they_exist(self):
        for name in RUNTIME_FILES:
            self.assertTrue((ROOT / name).exists(), name)
            self.assertIn(name, README, name)
        self.assertTrue((ROOT / "sample_data").is_dir())
        self.assertIn("sample_data/", README)

    def test_says_how_to_run_the_tests(self):
        self.assertIn("python3 -m unittest", README)

    def test_is_honest_about_limitations(self):
        self.assertIn("limitations", README.lower())
        self.assertIn("real time", README.lower())


if __name__ == "__main__":
    unittest.main()
