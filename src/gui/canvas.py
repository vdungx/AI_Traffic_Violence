"""Canvas drawing helpers - Vẽ areas, lines, video overlay lên Tkinter Canvas."""

from typing import Optional

import cv2
import numpy as np
from PIL import Image, ImageTk
import tkinter as tk


class CanvasManager:
    """Quản lý vẽ lên Tkinter Canvas."""

    def __init__(self, canvas: tk.Canvas):
        self.canvas = canvas
        self._areas: list[tuple] = []  # (canvas_id, name, coords_str)
        self._lines: list[tuple] = []  # (canvas_id, name, x1, y1, x2, y2)

    def draw_frame(self, frame: np.ndarray) -> ImageTk.PhotoImage:
        """Vẽ frame video lên canvas."""
        img = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        pil_image = Image.fromarray(img)
        imgtk = ImageTk.PhotoImage(image=pil_image)
        self.canvas.create_image(0, 0, anchor=tk.NW, image=imgtk)
        return imgtk

    def draw_regions(self, areas: list[tuple]):
        """Vẽ các khu vực (polygon) lên frame."""
        for area_id, name, coords_str in areas:
            coords = list(map(int, coords_str.split(",")))
            pts = np.array(coords, dtype=np.int32).reshape((-1, 1, 2))
            # Vẽ trên canvas (không phải frame)
            self.canvas.create_polygon(coords, outline="red", fill="")

    def draw_region_overlay(self, frame: np.ndarray, areas: list[tuple]) -> np.ndarray:
        """Vẽ overlay khu vực lên frame OpenCV."""
        for _, name, coords_str in areas:
            coords = list(map(int, coords_str.split(",")))
            pts = np.array(coords, dtype=np.int32).reshape((-1, 1, 2))
            cv2.polylines(frame, [pts], isClosed=True, color=(0, 0, 255), thickness=1)
        return frame

    def draw_line_overlay(self, frame: np.ndarray, lines: list[tuple]) -> np.ndarray:
        """Vẽ overlay đường kẻ lên frame OpenCV."""
        for _, name, x1, y1, x2, y2 in lines:
            cv2.line(frame, (x1, y1), (x2, y2), (255, 0, 0), 1)
        return frame

    def draw_detection_box(
        self, frame: np.ndarray,
        x1: int, y1: int, x2: int, y2: int,
        label: str, color: tuple = (255, 0, 0),
    ) -> np.ndarray:
        """Vẽ bounding box + label lên frame."""
        cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
        cv2.putText(frame, label, (x1, y2 + 20),
                     cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 1, cv2.LINE_AA)
        return frame

    def draw_violation_text(
        self, frame: np.ndarray,
        text: str, x: int, y: int,
        color: tuple = (0, 0, 255),
    ) -> np.ndarray:
        """Vẽ text cảnh báo vi phạm."""
        cv2.putText(frame, text, (x, y),
                     cv2.FONT_HERSHEY_SIMPLEX, 1, color, 2, cv2.LINE_AA)
        return frame

    def draw_speed_text(
        self, frame: np.ndarray,
        speed: float, x1: int, y2: int,
    ) -> np.ndarray:
        """Vẽ text tốc độ."""
        text = f"{round(speed, 2)} km/h"
        cv2.putText(frame, text, (x1, y2 + 50),
                     cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 0, 0), 1, cv2.LINE_AA)
        return frame

    def draw_safe_distance_line(
        self, frame: np.ndarray,
        x1: int, y1: int, x2: int, y2: int,
        distance: float, box_width: int,
    ) -> np.ndarray:
        """Vẽ đường chỉ khoảng cách an toàn giữa 2 phương tiện."""
        if distance >= box_width * 2 and distance < box_width * 5:
            color = (0, 255, 0)
            label = "An toan"
        elif distance >= box_width * 1 and distance < box_width * 2:
            color = (0, 165, 255)
            label = "Kha an toan"
        elif distance < box_width / 2:
            color = (0, 0, 255)
            label = "Khong an toan!!"
        else:
            return frame

        mid = ((x1 + x2) // 2, (y1 + y2) // 2)
        cv2.line(frame, (x1, y1), (x2, y2), color, 1)
        cv2.putText(frame, label, (mid[0], mid[1]),
                     cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1, cv2.LINE_AA)
        return frame

    def draw_track_path(self, frame: np.ndarray, points: np.ndarray) -> np.ndarray:
        """Vẽ đường đi của track."""
        if len(points) >= 2:
            cv2.polylines(frame, [points], isClosed=False, color=(0, 255, 255), thickness=1)
        return frame

    @staticmethod
    def is_point_in_polygon(x: int, y: int, coords: list) -> bool:
        """Kiểm tra điểm có nằm trong polygon không (ray casting)."""
        n = len(coords) // 2
        inside = False
        p1x, p1y = coords[0], coords[1]
        for i in range(n + 1):
            p2x, p2y = coords[2 * (i % n)], coords[2 * (i % n) + 1]
            if y > min(p1y, p2y):
                if y <= max(p1y, p2y):
                    if x <= max(p1x, p2x):
                        if p1y != p2y:
                            xinters = (y - p1y) * (p2x - p1x) / (p2y - p1y) + p1x
                        if p1x == p2x or x <= xinters:
                            inside = not inside
            p1x, p1y = p2x, p2y
        return inside

    @staticmethod
    def is_near_line(x1: int, y1: int, x2: int, y2: int, px: int, py: int, tolerance: int = 5) -> bool:
        """Kiểm tra điểm có gần đường thẳng không."""
        denom = ((y2 - y1) ** 2 + (x2 - x1) ** 2) ** 0.5
        if denom == 0:
            denom = 1
        distance = abs((y2 - y1) * px - (x2 - x1) * py + x2 * y1 - y2 * x1) / denom
        return distance < tolerance
