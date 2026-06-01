"""Configuration management - Đọc/ghi cấu hình hệ thống từ configuration.db."""

from dataclasses import dataclass, field
from typing import Optional
from .database import Database, CONFIG_DB


@dataclass
class AppConfig:
    """Cấu hình ứng dụng, tương ứng với bảng config trong configuration.db."""

    calibration_factor: float = 2.0
    max_speed: float = 80.0
    width_in_pixel: float = 900.0
    width_in_meter: float = 7.0
    actual_time: float = 5.0
    yolo_time: float = 15.0
    location: str = "Indonesia"
    model: str = "models/yolo/yolov8x.pt"

    # Giá trị mặc định khi chưa có trong DB
    _defaults: dict = field(default_factory=dict, repr=False, init=False)

    # Mapping tên model → index cho dropdown
    MODEL_OPTIONS = {
        0: "models/yolo/yolov8x.pt",
        1: "models/yolo/yolov8l.pt",
        2: "models/yolo/yolov8m.pt",
        3: "models/yolo/yolov8s.pt",
        4: "models/yolo/yolov8n.pt",
    }
    MODEL_LABELS = {v: k for k, v in {
        "super": "models/yolo/yolov8x.pt",
        "large": "models/yolo/yolov8l.pt",
        "medium": "models/yolo/yolov8m.pt",
        "small": "models/yolo/yolov8s.pt",
        "nano": "models/yolo/yolov8n.pt",
    }.items()}

    @staticmethod
    def model_to_row(model_name: str) -> int:
        """Chuyển tên model sang index (cho dropdown)."""
        mapping = {"models/yolo/yolov8x.pt": 0, "models/yolo/yolov8l.pt": 1,
                   "models/yolo/yolov8m.pt": 2, "models/yolo/yolov8s.pt": 3,
                   "models/yolo/yolov8n.pt": 4}
        return mapping.get(model_name, 0)

    @staticmethod
    def row_to_model(row: int) -> str:
        """Chuyển index sang tên model."""
        mapping = {0: "models/yolo/yolov8x.pt", 1: "models/yolo/yolov8l.pt",
                   2: "models/yolo/yolov8m.pt", 3: "models/yolo/yolov8s.pt",
                   4: "models/yolo/yolov8n.pt"}
        return mapping.get(row, "models/yolo/yolov8x.pt")

    @staticmethod
    def label_to_model(label: str) -> str:
        """Chuyển label (super/large/medium/small/nano) sang tên file."""
        mapping = {"super": "models/yolo/yolov8x.pt", "large": "models/yolo/yolov8l.pt",
                   "medium": "models/yolo/yolov8m.pt", "small": "models/yolo/yolov8s.pt",
                   "nano": "models/yolo/yolov8n.pt"}
        return mapping.get(label, "models/yolo/yolov8x.pt")


def load_config() -> AppConfig:
    """Đọc cấu hình từ DB. Nếu chưa có, tạo bản mặc định."""
    with Database(CONFIG_DB) as conn:
        row = conn.execute("SELECT * FROM config WHERE id=1").fetchone()
        if row is None:
            cfg = AppConfig()
            conn.execute(
                "INSERT INTO config (id, calibration_factor, max_speed, width_in_pixel, "
                "width_in_meter, actual_time, yolo_time, location, Model) "
                "VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?)",
                (cfg.calibration_factor, cfg.max_speed, cfg.width_in_pixel,
                 cfg.width_in_meter, cfg.actual_time, cfg.yolo_time,
                 cfg.location, cfg.model),
            )
            return cfg

        model = row["Model"]
        # Migrate đường dẫn model cũ (VD: "yolov8x.pt" → "models/yolo/yolov8x.pt")
        if model and "/" not in model and "\\" not in model:
            model = f"models/yolo/{model}"
            conn.execute("UPDATE config SET Model=? WHERE id=1", (model,))

        return AppConfig(
            calibration_factor=row["calibration_factor"],
            max_speed=row["max_speed"],
            width_in_pixel=row["width_in_pixel"],
            width_in_meter=row["width_in_meter"],
            actual_time=row["actual_time"],
            yolo_time=row["yolo_time"],
            location=row["location"],
            model=model,
        )


def save_config(cfg: AppConfig):
    """Lưu cấu hình vào DB."""
    with Database(CONFIG_DB) as conn:
        conn.execute(
            "UPDATE config SET calibration_factor=?, max_speed=?, width_in_pixel=?, "
            "width_in_meter=?, actual_time=?, yolo_time=?, location=?, Model=? WHERE id=1",
            (cfg.calibration_factor, cfg.max_speed, cfg.width_in_pixel,
             cfg.width_in_meter, cfg.actual_time, cfg.yolo_time,
             cfg.location, cfg.model),
        )
