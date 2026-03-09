import sys
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
VENDOR_DIR = BASE_DIR / ".deps"

if VENDOR_DIR.exists():
    sys.path.insert(0, str(VENDOR_DIR))


__all__ = ["app", "search"]
