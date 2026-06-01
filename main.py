"""CCTV AI Traffic Violence Detection - Entry Point.

Ung dung desktop phat hien vi pham giao thong bang YOLO + Tkinter GUI.
"""

import atexit
import sys
import tkinter as tk
from pathlib import Path

# Force UTF-8 output on Windows
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# Lock file - đảm bảo chỉ chạy 1 instance
lock_file = Path("app.lock")
if lock_file.exists():
    print("Ứng dụng đang chạy.")
    sys.exit()
lock_file.touch()


def _remove_lock():
    if lock_file.exists():
        lock_file.unlink()


atexit.register(_remove_lock)

from src.gui.app import VideoApp


def main():
    root = tk.Tk()
    root.geometry("1600x900")
    app = VideoApp(root)

    def on_closing():
        app.close()
        _remove_lock()
        print("Thoát")

    root.protocol("WM_DELETE_WINDOW", on_closing)
    root.mainloop()


if __name__ == "__main__":
    main()
