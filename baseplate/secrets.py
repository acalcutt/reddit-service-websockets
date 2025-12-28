import json
import base64
import os


class SecretsStore(object):
    """A tiny SecretsStore compatible with the test suite.

    It loads a JSON file structured like `example_secrets.json` and
    exposes `get_versioned(key)` to return the decoded current secret.
    """

    def __init__(self, source):
        # Accept either a path to a JSON file or a dict-like object.
        if isinstance(source, str) and os.path.exists(source):
            with open(source, "rb") as fh:
                self._data = json.load(fh)
        elif isinstance(source, dict):
            self._data = source
        else:
            # Attempt to load as a path relative to repo root
            try:
                with open(source, "rb") as fh:
                    self._data = json.load(fh)
            except Exception:
                self._data = {}

    def get_versioned(self, key):
        secrets = self._data.get("secrets", {})
        entry = secrets.get(key)
        if not entry:
            raise KeyError(key)
        current = entry.get("current")
        encoding = entry.get("encoding")
        if encoding == "base64":
            return base64.b64decode(current).decode("utf-8")
        return current


def secrets_store_from_config(raw_config):
    """Construct a SecretsStore from a raw config mapping.

    This mirrors the minimal interface expected by `reddit_service_websockets.app`.
    If `raw_config` is a mapping containing a `secrets` key with the
    structure from `example_secrets.json`, it will be used directly.
    Otherwise, if `raw_config` contains `secrets_file`, that path will
    be used.
    """
    if isinstance(raw_config, dict) and "secrets" in raw_config:
        return SecretsStore(raw_config)
    if isinstance(raw_config, dict) and "secrets_file" in raw_config:
        return SecretsStore(raw_config["secrets_file"])
    # Fallback: look for example_secrets.json in repo root
    return SecretsStore("example_secrets.json")
