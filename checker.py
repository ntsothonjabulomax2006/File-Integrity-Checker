import hashlib


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


if __name__ == "__main__":
    filename = input("Enter the file path: ")
    file_hash = calculate_hash(filename)
    if file_hash:
        print("SHA-256:", file_hash)