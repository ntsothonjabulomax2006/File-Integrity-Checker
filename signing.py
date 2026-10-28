import hashlib
import hmac
import os
from pathlib import Path

from baseline import BaselineError

KEY_ENV_VAR = "INTEGRITY_KEY"


class SignatureError(BaselineError):
    """Raised when the baseline's signature is missing, wrong or unexpected."""


def get_key(environ=None):
    """Return the signing key from the environment as bytes, or None if unset."""
    environ = os.environ if environ is None else environ
    value = environ.get(KEY_ENV_VAR, "")
    return value.encode("utf-8") if value else None


def signature_path(baseline_file):
    """The signature lives next to the baseline: baseline.json.sig"""
    path = Path(baseline_file)
    return path.with_name(path.name + ".sig")


def compute_signature(baseline_file, key):
    """HMAC-SHA256 of the exact bytes of the baseline file, as hex."""
    return hmac.new(key, Path(baseline_file).read_bytes(), hashlib.sha256).hexdigest()


def sign_baseline(baseline_file, key):
    signature_path(baseline_file).write_text(compute_signature(baseline_file, key) + "\n")


def verify_baseline(baseline_file, key):
    """Raise SignatureError unless the baseline matches its signature.

    - no key and no signature: unsigned mode, nothing to check
    - signature but no key:    refuse (we can't verify it)
    - key but no signature:    refuse (the signature may have been removed)
    - key and signature:       they must match
    """
    if not Path(baseline_file).exists():
        return  # load_baseline reports a missing baseline
    sig_file = signature_path(baseline_file)
    if key is None:
        if sig_file.exists():
            raise SignatureError(
                f"{baseline_file} is signed, but {KEY_ENV_VAR} is not set. "
                "Set it to the key used when the baseline was created."
            )
        return
    if not sig_file.exists():
        raise SignatureError(
            f"{baseline_file} has no signature, but {KEY_ENV_VAR} is set. "
            "The signature may have been removed."
        )
    expected = compute_signature(baseline_file, key)
    actual = sig_file.read_text().strip()
    if not hmac.compare_digest(expected, actual):
        raise SignatureError(
            "Baseline signature does not match: the baseline was modified, "
            "or the key is wrong."
        )
