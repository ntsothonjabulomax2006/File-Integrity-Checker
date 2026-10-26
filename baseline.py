import json
from datetime import datetime
from pathlib import Path

BASELINE_FILE = Path("baseline.json")


class BaselineError(Exception):
    """Raised when the baseline file is missing or can't be trusted."""


def save_baseline(folder, hashes, baseline_file=BASELINE_FILE):
    """Save a {relative path: hash} dict as the trusted baseline."""
    data = {
        "folder": str(Path(folder).resolve()),
        "created": datetime.now().isoformat(timespec="seconds"),
        "files": hashes,
    }
    Path(baseline_file).write_text(json.dumps(data, indent=2))


def load_baseline(baseline_file=BASELINE_FILE):
    """Load a saved baseline. Raises BaselineError if it is missing or invalid."""
    path = Path(baseline_file)
    if not path.exists():
        raise BaselineError(f"No baseline found: {path}")
    try:
        data = json.loads(path.read_text())
    except json.JSONDecodeError:
        raise BaselineError(f"Baseline is corrupted (not valid JSON): {path}")
    if (
        not isinstance(data, dict)
        or not isinstance(data.get("files"), dict)
        or "folder" not in data
        or "created" not in data
    ):
        raise BaselineError(f"Baseline has the wrong structure: {path}")
    return data
