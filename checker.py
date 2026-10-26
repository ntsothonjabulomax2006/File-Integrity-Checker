import hashlib


def calculate_hash(filename):
    """Return the SHA-256 hash of a file as a hex string."""
    sha256 = hashlib.sha256()
    with open(filename, "rb") as file:
        for block in iter(lambda: file.read(4096), b""):
            sha256.update(block)
    return sha256.hexdigest()


if __name__ == "__main__":
    filename = input("Enter the file path: ")
    print("SHA-256:", calculate_hash(filename))