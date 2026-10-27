#!/usr/bin/env python3
"""File Integrity Checker.

    python3 integrity.py init <folder>   create a baseline for a folder
    python3 integrity.py check           compare the folder with the baseline
    python3 integrity.py update          accept the current state as the new baseline

Exit codes: 0 = no changes, 1 = changes detected, 2 = error.
"""

import argparse
import sys
from pathlib import Path

from baseline import BASELINE_FILE, BaselineError, save_baseline
from checker import scan_folder
from compare import check_folder
from report import build_report, has_changes, save_report

EXIT_OK, EXIT_CHANGES, EXIT_ERROR = 0, 1, 2


def _without_baseline_file(hashes, folder, baseline_file):
    """Drop the baseline file itself from a scan if it lives in the folder."""
    try:
        own = Path(baseline_file).resolve().relative_to(Path(folder).resolve()).as_posix()
    except ValueError:
        return hashes
    return {name: digest for name, digest in hashes.items() if name != own}


def cmd_init(args):
    baseline_file = Path(args.baseline)
    if baseline_file.exists() and not args.force:
        print(
            f"Error: {baseline_file} already exists. Use 'update' to accept "
            "changes, or --force to replace it.",
            file=sys.stderr,
        )
        return EXIT_ERROR
    hashes = _without_baseline_file(scan_folder(args.folder), args.folder, baseline_file)
    save_baseline(args.folder, hashes, baseline_file)
    print(f"Baseline created for {len(hashes)} files -> {baseline_file}")
    return EXIT_OK


def cmd_check(args):
    data, result = check_folder(args.baseline)
    text = build_report(data["folder"], data["created"], result)
    print(text)
    if args.report:
        save_report(text, args.report)
        print(f"\nReport saved to {args.report}")
    return EXIT_CHANGES if has_changes(result) else EXIT_OK


def cmd_update(args):
    data, result = check_folder(args.baseline)
    folder = data["folder"]
    hashes = _without_baseline_file(scan_folder(folder), folder, args.baseline)
    save_baseline(folder, hashes, args.baseline)
    print(
        f"Baseline updated: {len(hashes)} files "
        f"({len(result['modified'])} modified, {len(result['missing'])} missing, "
        f"{len(result['new'])} new accepted)"
    )
    return EXIT_OK


def build_parser():
    parser = argparse.ArgumentParser(
        prog="integrity.py", description="SHA-256 file integrity checker"
    )
    sub = parser.add_subparsers(dest="command", required=True)
    default = str(BASELINE_FILE)

    p_init = sub.add_parser("init", help="create a baseline for a folder")
    p_init.add_argument("folder")
    p_init.add_argument("--baseline", default=default, help="baseline file to write")
    p_init.add_argument("--force", action="store_true", help="replace an existing baseline")
    p_init.set_defaults(func=cmd_init)

    p_check = sub.add_parser("check", help="compare the folder with the baseline")
    p_check.add_argument("--baseline", default=default, help="baseline file to read")
    p_check.add_argument("--report", help="also save the report to this file")
    p_check.set_defaults(func=cmd_check)

    p_update = sub.add_parser("update", help="accept the current state as the new baseline")
    p_update.add_argument("--baseline", default=default, help="baseline file to update")
    p_update.set_defaults(func=cmd_update)

    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except (BaselineError, NotADirectoryError) as e:
        print(f"Error: {e}", file=sys.stderr)
        return EXIT_ERROR


if __name__ == "__main__":
    sys.exit(main())
