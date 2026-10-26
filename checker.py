import hashlib
from pathlib import Path

IGNORED_DIRS = {".git", "__pycache__", "node_modules", ".venv"}


def calculate_hash(filename):
    """Return the SHA-256 hash of a file as a hex string.

    Returns None (and prints a message) if the file can't be read.
    """
    sha256 = hashlib.sha256()
    try:
        with open(filename, "rb") as file:
            for block in iter(lambda: file.read(4096), b""):
                sha256.update(block)
    except FileNotFoundError:
        print(f"Error: file not found: {filename}")
        return None
    except PermissionError:
        print(f"Error: permission denied: {filename}")
        return None
    except OSError as e:  # e.g. the path is a folder
        print(f"Error: cannot read {filename}: {e}")
        return None
    return sha256.hexdigest()


def scan_folder(folder, ignored_dirs=IGNORED_DIRS):
    """Hash every file in a folder (including subfolders).

    Returns a dict of {relative file path: SHA-256 hash}.
    Files that can't be read are skipped. Raises NotADirectoryError if
    the folder doesn't exist, so a missing folder is never mistaken for
    an empty one.
    """
    folder = Path(folder)
    if not folder.is_dir():
        raise NotADirectoryError(f"Not a folder: {folder}")

    hashes = {}
    for path in sorted(folder.rglob("*")):
        relative = path.relative_to(folder)
        if any(part in ignored_dirs for part in relative.parts):
            continue
        if not path.is_file():
            continue
        digest = calculate_hash(path)
        if digest is not None:
            hashes[relative.as_posix()] = digest
    return hashes


if __name__ == "__main__":
    folder = input("Enter the folder path: ")
    try:
        hashes = scan_folder(folder)
    except NotADirectoryError as e:
        print(f"Error: {e}")
    else:
        for name, digest in hashes.items():
            print(f"{digest}  {name}")
        print(f"\n{len(hashes)} files hashed.")
