import os
import sys

# Ensure repository root is first on sys.path so our local `baseplate`
# shim is preferred over any system-installed package named `baseplate`.
REPO_ROOT = os.path.dirname(os.path.dirname(__file__))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

# If a different `baseplate` was already imported from site-packages,
# remove it so imports resolve to the local package in this repo.
if "baseplate" in sys.modules:
    del sys.modules["baseplate"]
