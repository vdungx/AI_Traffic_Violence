"""Reset application - Xoa lock file."""

import sys
from pathlib import Path

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

lock_file = Path("app.lock")

if lock_file.exists():
    print("Ung dung dang chay.")
    lock_file.unlink()

print("Thoat")

if lock_file.exists():
    lock_file.unlink()

sys.exit()
