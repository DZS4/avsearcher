import os
import sys
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
VENDOR_DIR = BASE_DIR / ".deps"

if VENDOR_DIR.exists():
    sys.path.insert(0, str(VENDOR_DIR))

import uvicorn


if __name__ == "__main__":
    uvicorn.run(
        "avsearcher.app:app",
        host=os.getenv("AVSEARCHER_HOST", "127.0.0.1"),
        port=int(os.getenv("AVSEARCHER_PORT", "8000")),
        reload=False,
    )

