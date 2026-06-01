"""Custom widgets và dialogs cho ứng dụng."""

import tkinter as tk
from tkinter import messagebox, simpledialog
from typing import Callable

from ..config import AppConfig, save_config


class ConfigDialog(tk.Toplevel):
    """Dialog cấu hình hệ thống."""

    def __init__(self, parent, cfg: AppConfig, on_save: Callable):
        super().__init__(parent)
        self.title("Cấu hình")
        self.cfg = cfg
        self.on_save = on_save
        self._build_ui()

    def _build_ui(self):
        row = 0

        # Hệ số hiệu chuẩn
        tk.Label(self, text="Hệ số hiệu chuẩn (VD: 2.0):").grid(row=row, column=0, sticky="e", padx=5, pady=3)
        self.cal_entry = tk.Entry(self)
        self.cal_entry.grid(row=row, column=1, padx=5, pady=3)
        self.cal_entry.insert(0, str(self.cfg.calibration_factor))
        row += 1

        # Tốc độ tối đa
        tk.Label(self, text="Tốc độ tối đa (VD: 80.0):").grid(row=row, column=0, sticky="e", padx=5, pady=3)
        self.speed_entry = tk.Entry(self)
        self.speed_entry.grid(row=row, column=1, padx=5, pady=3)
        self.speed_entry.insert(0, str(self.cfg.max_speed))
        row += 1

        # Chiều rộng pixel
        tk.Label(self, text="Chiều rộng tính bằng Pixel:").grid(row=row, column=0, sticky="e", padx=5, pady=3)
        self.pix_entry = tk.Entry(self)
        self.pix_entry.grid(row=row, column=1, padx=5, pady=3)
        self.pix_entry.insert(0, str(self.cfg.width_in_pixel))
        row += 1

        # Chiều rộng mét
        tk.Label(self, text="Chiều rộng tính bằng Mét:").grid(row=row, column=0, sticky="e", padx=5, pady=3)
        self.meter_entry = tk.Entry(self)
        self.meter_entry.grid(row=row, column=1, padx=5, pady=3)
        self.meter_entry.insert(0, str(self.cfg.width_in_meter))
        row += 1

        # Thời gian thực
        tk.Label(self, text="Thời gian thực:").grid(row=row, column=0, sticky="e", padx=5, pady=3)
        self.actual_entry = tk.Entry(self)
        self.actual_entry.grid(row=row, column=1, padx=5, pady=3)
        self.actual_entry.insert(0, str(self.cfg.actual_time))
        row += 1

        # Thời gian YOLO
        tk.Label(self, text="Thời gian Yolo:").grid(row=row, column=0, sticky="e", padx=5, pady=3)
        self.yolo_entry = tk.Entry(self)
        self.yolo_entry.grid(row=row, column=1, padx=5, pady=3)
        self.yolo_entry.insert(0, str(self.cfg.yolo_time))
        row += 1

        # Vị trí
        tk.Label(self, text="Vị trí:").grid(row=row, column=0, sticky="e", padx=5, pady=3)
        self.loc_entry = tk.Entry(self)
        self.loc_entry.grid(row=row, column=1, padx=5, pady=3)
        self.loc_entry.insert(0, self.cfg.location)
        row += 1

        # Mô hình AI
        tk.Label(self, text="Mô hình AI:").grid(row=row, column=0, sticky="e", padx=5, pady=3)
        options = ["super", "large", "medium", "small", "nano"]
        self.model_var = tk.StringVar(self)
        current_label = self._model_to_label(self.cfg.model)
        self.model_var.set(current_label)
        model_menu = tk.OptionMenu(self, self.model_var, *options)
        model_menu.grid(row=row, column=1, padx=5, pady=3, sticky="w")
        row += 1

        # Nút Lưu
        tk.Button(self, text="Lưu", command=self._save, width=20).grid(
            row=row, column=0, columnspan=2, pady=10
        )

    def _model_to_label(self, model: str) -> str:
        mapping = {
            "models/yolo/yolov8x.pt": "super", "models/yolo/yolov8l.pt": "large",
            "models/yolo/yolov8m.pt": "medium", "models/yolo/yolov8s.pt": "small",
            "models/yolo/yolov8n.pt": "nano",
        }
        return mapping.get(model, "super")

    def _save(self):
        from ..config import AppConfig
        self.cfg.calibration_factor = float(self.cal_entry.get())
        self.cfg.max_speed = float(self.speed_entry.get())
        self.cfg.width_in_pixel = float(self.pix_entry.get())
        self.cfg.width_in_meter = float(self.meter_entry.get())
        self.cfg.actual_time = float(self.actual_entry.get())
        self.cfg.yolo_time = float(self.yolo_entry.get())
        self.cfg.location = str(self.loc_entry.get())
        self.cfg.model = AppConfig.label_to_model(str(self.model_var.get()))

        save_config(self.cfg)
        self.on_save(self.cfg)
        self.destroy()


class AreaDrawer:
    """Helper vẽ polygon area trên canvas."""

    def __init__(self, canvas: tk.Canvas):
        self.canvas = canvas
        self.points: list[int] = []
        self._temp_items: list[int] = []

    def on_click(self, event):
        self.points.extend([event.x, event.y])
        oid = self.canvas.create_oval(event.x - 3, event.y - 3, event.x + 3, event.y + 3,
                                        fill="red", tags="poly_temp")
        self._temp_items.append(oid)
        if len(self.points) >= 4:
            self.canvas.delete("poly_line")
            self.canvas.create_line(self.points, tag="poly_line", fill="red", width=2)

    def on_motion(self, event):
        if len(self.points) >= 2:
            self.canvas.delete("poly_motion")
            pts = self.points[-2:] + [event.x, event.y]
            self.canvas.create_line(pts, tag="poly_motion", fill="red", dash=(4, 4))

    def finish(self, event=None) -> list[int] | None:
        """Hoàn tất vẽ polygon, trả về danh sách tọa độ hoặc None."""
        self.canvas.delete("poly_temp", "poly_line", "poly_motion")

        # Xóa điểm trùng
        clean: list[int] = []
        for i in range(0, len(self.points), 2):
            x, y = self.points[i], self.points[i + 1]
            if not clean or clean[-2:] != [x, y]:
                clean.extend([x, y])

        if len(clean) >= 6:
            return clean
        return None


class LineDrawer:
    """Helper vẽ đường thẳng trên canvas."""

    def __init__(self, canvas: tk.Canvas):
        self.canvas = canvas
        self.start_x: int | None = None
        self.start_y: int | None = None

    def on_press(self, event):
        self.start_x = event.x
        self.start_y = event.y

    def on_drag(self, event):
        if self.start_x and self.start_y:
            self.canvas.delete("current_line")
            self.canvas.create_line(self.start_x, self.start_y, event.x, event.y,
                                     fill="green", width=2, tag="current_line")

    def on_release(self, event) -> tuple | None:
        """Hoàn tất vẽ đường, trả về (x1, y1, x2, y2) hoặc None."""
        self.canvas.delete("current_line")
        if self.start_x and self.start_y:
            result = (self.start_x, self.start_y, event.x, event.y)
            self.start_x = None
            self.start_y = None
            return result
        return None


def check_line_intersection(line1: tuple, line2: tuple) -> tuple:
    """Kiểm tra 2 đường có giao nhau không. Trả về (x, y) giao điểm hoặc (None, None)."""
    x1, y1, x2, y2 = line1
    x3, y3, x4, y4 = line2

    def det(a, b, c, d):
        return a * d - b * c

    denom = det(x1 - x2, y1 - y2, x3 - x4, y3 - y4)
    if denom == 0:
        return None, None
    t = det(x1 - x3, y1 - y3, x3 - x4, y3 - y4) / denom
    u = det(x1 - x3, y1 - y3, x1 - x2, y1 - y2) / denom
    if 0 <= t <= 1 and 0 <= u <= 1:
        ix = x1 + t * (x2 - x1)
        iy = y1 + t * (y2 - y1)
        return ix, iy
    return None, None
