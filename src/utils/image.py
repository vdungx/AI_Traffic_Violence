"""Image saving and file path helpers."""

import os
from datetime import datetime

SLASH = "\\"  # Windows

# Base directory của project (2 levels up from src/utils/)
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
STATIC_BASE = os.path.join(BASE_DIR, "database", "static")


def get_current_time() -> str:
    """Trả về thời gian hiện tại dạng dd-mm-yyyy HH-MM-SS."""
    return datetime.now().strftime("%d-%m-%Y %H-%M-%S")


def ensure_dirs(*paths: str):
    """Tạo thư mục nếu chưa tồn tại."""
    for p in paths:
        os.makedirs(p, exist_ok=True)


def build_violation_path(
    static_base: str,
    category: str,
    track_id: int,
    timestamp: str,
    suffix: str = "",
) -> str:
    """Tạo đường dẫn file ảnh vi phạm.

    Ví d: database/static/Helmet/[12]-01-06-2025 14-30-00_no-helmet_.jpg
    """
    folder = os.path.join(static_base, category)
    ensure_dirs(folder)
    name = f"[{track_id}]-{timestamp}_{suffix}.jpg"
    return os.path.join(folder, name)


def build_plate_path(
    static_base: str,
    category: str,
    track_id: int,
    timestamp: str,
) -> str:
    """Tạo đường dẫn file ảnh biển số."""
    folder = os.path.join(static_base, f"plat_number_{category}")
    ensure_dirs(folder)
    name = f"{timestamp}_{track_id}.jpg"
    return os.path.join(folder, name)


def build_plate_path_html(category: str, timestamp: str, track_id: int) -> str:
    """Tạo đường dẫn HTML (dấu /) cho ảnh biển số."""
    return f"plat_number_{category}/{timestamp}_{track_id}.jpg"


def build_violation_path_html(category: str, track_id: int, timestamp: str, suffix: str) -> str:
    """Tạo đường dẫn HTML (dấu /) cho ảnh vi phạm."""
    return f"{category}/[{track_id}]-{timestamp}_{suffix}.jpg"


def file_exists(file_path: str) -> bool:
    """Kiểm tra file có tồn tại không."""
    return os.path.isfile(file_path)
