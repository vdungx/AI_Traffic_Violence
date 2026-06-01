"""Database layer - Quản lý schema và connection cho tất cả SQLite databases."""

import os
import sqlite3
from typing import Optional

BASE_DIR = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))


def _db_path(filename: str) -> str:
    """Trả về đường dẫn tuyệt đối đến file database."""
    return os.path.join(BASE_DIR, filename)


class Database:
    """Context manager cho SQLite connection."""

    def __init__(self, db_file: str, use_row_factory: bool = True):
        self.db_file = db_file
        self.use_row_factory = use_row_factory
        self.conn: Optional[sqlite3.Connection] = None

    def __enter__(self) -> sqlite3.Connection:
        self.conn = sqlite3.connect(self.db_file)
        if self.use_row_factory:
            self.conn.row_factory = sqlite3.Row
        return self.conn

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.conn:
            if exc_type:
                self.conn.rollback()
            else:
                self.conn.commit()
            self.conn.close()


# ---------------------------------------------------------------------------
# Configuration DB (configuration.db)
# ---------------------------------------------------------------------------

CONFIG_DB = _db_path("database/configuration.db")


def init_config_db():
    """Khởi tạo schema cho configuration.db."""
    with Database(CONFIG_DB, use_row_factory=False) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS areas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                coordinates TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS lines (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                x1 INTEGER,
                y1 INTEGER,
                x2 INTEGER,
                y2 INTEGER
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS config (
                id INTEGER PRIMARY KEY,
                calibration_factor REAL,
                max_speed REAL,
                width_in_pixel REAL,
                width_in_meter REAL,
                actual_time REAL,
                yolo_time REAL,
                location TEXT NOT NULL,
                Model TEXT NOT NULL
            )
        """)


# ---------------------------------------------------------------------------
# Datalog DB (datalog.db)
# ---------------------------------------------------------------------------

DATALOG_DB = _db_path("database/datalog.db")


def init_datalog_db():
    """Khởi tạo schema cho datalog.db."""
    with Database(DATALOG_DB, use_row_factory=False) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS datalog (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                track_id TEXT NOT NULL,
                date TEXT NOT NULL,
                plat_license TEXT NOT NULL,
                speed TEXT NOT NULL,
                max_speed TEXT NOT NULL,
                violence_category TEXT NOT NULL,
                vehicle TEXT NOT NULL,
                location TEXT NOT NULL,
                open_photo TEXT NOT NULL
            )
        """)


# ---------------------------------------------------------------------------
# Login DB (login.db)
# ---------------------------------------------------------------------------

LOGIN_DB = _db_path("database/login.db")


def init_login_db():
    """Khởi tạo schema cho login.db."""
    with Database(LOGIN_DB, use_row_factory=False) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS login (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user TEXT NOT NULL,
                password TEXT NOT NULL,
                token TEXT
            )
        """)


# ---------------------------------------------------------------------------
# Save IP DB (save_ip.db)
# ---------------------------------------------------------------------------

SAVE_IP_DB = _db_path("save_ip.db")


def init_save_ip_db():
    """Khởi tạo schema cho save_ip.db."""
    with Database(SAVE_IP_DB, use_row_factory=False) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS save_ip (
                IP TEXT NOT NULL
            )
        """)


# ---------------------------------------------------------------------------
# Khởi tạo tất cả databases
# ---------------------------------------------------------------------------

def init_all_databases():
    """Khởi tạo schema cho tất cả databases."""
    os.makedirs(_db_path("database"), exist_ok=True)
    init_config_db()
    init_datalog_db()
    init_login_db()
    init_save_ip_db()
