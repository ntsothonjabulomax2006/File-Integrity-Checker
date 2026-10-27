from datetime import datetime
from pathlib import Path

SECTIONS = [("MODIFIED", "modified"), ("MISSING", "missing"), ("NEW", "new")]


def has_changes(result):
    """True if any file was modified, missing or new."""
    return any(result[key] for _, key in SECTIONS)


def build_report(folder, created, result, checked_at=None):
    """Turn a comparison result into a readable text report."""
    checked_at = checked_at or datetime.now().isoformat(timespec="seconds")
    status = (
        "STATUS: CHANGES DETECTED"
        if has_changes(result)
        else "STATUS: OK - no changes detected"
    )
    lines = [
        "=" * 50,
        "FILE INTEGRITY REPORT",
        "=" * 50,
        f"Folder:        {folder}",
        f"Baseline from: {created}",
        f"Checked at:    {checked_at}",
        "",
        status,
        "",
        f"Unchanged: {len(result['unchanged'])}",
        f"Modified:  {len(result['modified'])}",
        f"Missing:   {len(result['missing'])}",
        f"New:       {len(result['new'])}",
    ]
    for label, key in SECTIONS:
        if result[key]:
            lines.append("")
            lines.append(f"[{label}]")
            lines.extend(f"  - {name}" for name in result[key])
    return "\n".join(lines)


def save_report(text, report_file):
    """Write the report text to a file."""
    Path(report_file).write_text(text + "\n")
