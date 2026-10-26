from pathlib import Path

from baseline import BASELINE_FILE, load_baseline
from checker import scan_folder


def compare_hashes(old, new):
    """Compare two {path: hash} dicts and sort every file into a group.

    unchanged: in both, same hash
    modified:  in both, different hash
    missing:   in old only (deleted since the baseline)
    new:       in new only (added since the baseline)
    A renamed file shows up as one missing file plus one new file.
    """
    return {
        "unchanged": sorted(f for f in old if f in new and old[f] == new[f]),
        "modified": sorted(f for f in old if f in new and old[f] != new[f]),
        "missing": sorted(f for f in old if f not in new),
        "new": sorted(f for f in new if f not in old),
    }


def check_folder(baseline_file=BASELINE_FILE):
    """Re-scan the folder recorded in the baseline and compare the two.

    Returns (baseline_data, result). Raises BaselineError if the baseline
    is missing or damaged, and NotADirectoryError if the folder is gone.
    """
    data = load_baseline(baseline_file)
    folder = Path(data["folder"])
    old = dict(data["files"])
    new = scan_folder(folder)

    # If the baseline file lives inside the monitored folder, ignore it.
    try:
        own_name = Path(baseline_file).resolve().relative_to(folder.resolve()).as_posix()
    except ValueError:
        own_name = None
    if own_name:
        old.pop(own_name, None)
        new.pop(own_name, None)

    return data, compare_hashes(old, new)
