import os
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VENDOR_DIR = os.path.join(BASE_DIR, ".deps")

if os.path.exists(VENDOR_DIR):
    sys.path.insert(0, VENDOR_DIR)


__all__ = ["app", "search"]
