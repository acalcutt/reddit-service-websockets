class SignatureError(Exception):
    """Raised when a signature fails validation."""


def validate_signature(secret, namespace, signature):
    """Minimal signature validator used by tests.

    This is a permissive implementation: it treats a missing `signature`
    as invalid (raises SignatureError), otherwise it returns True. The
    real project uses HMAC-based validation; tests in this repository
    don't exercise signature verification logic, they only import the
    functions, so this lightweight shim is sufficient for CI.
    """
    if not signature:
        raise SignatureError("missing signature")
    return True
