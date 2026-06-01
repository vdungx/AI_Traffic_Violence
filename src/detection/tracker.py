"""Object tracking, direction analysis, và speed estimation."""

import numpy as np
from collections import defaultdict, deque
from typing import Optional

from ..config import AppConfig
from ..utils.speed import euclidean_distance, calculate_speed
from .detector import ALL_VEHICLES, MOTORCYCLE


class TrackManager:
    """Quản lý vòng đời và lịch sử vị trí của các đối tượng được theo dõi."""

    def __init__(self, max_history: int = 30):
        self.track_history: dict[int, deque] = defaultdict(lambda: deque(maxlen=max_history))
        self.max_history = max_history

    def update(self, track_id: int, x: float, y: float):
        """Cập nhật vị trí mới nhất của track."""
        self.track_history[track_id].append((x, y))

    def get_position(self, track_id: int) -> Optional[tuple]:
        """Lấy vị trí hiện tại (x, y) của track."""
        history = self.track_history.get(track_id)
        if history and len(history) > 0:
            return history[-1]
        return None

    def get_history(self, track_id: int) -> list:
        """Lấy toàn bộ lịch sử vị trí."""
        return list(self.track_history.get(track_id, []))

    def get_path_points(self, track_id: int) -> np.ndarray:
        """Lấy lịch sử dạng numpy array để vẽ đường đi."""
        history = self.get_history(track_id)
        if len(history) < 2:
            return np.array([], dtype=np.int32).reshape((-1, 1, 2))
        return np.hstack(history).astype(np.int32).reshape((-1, 1, 2))

    def cleanup(self, active_ids: set):
        """Xóa các track không còn active."""
        stale = [tid for tid in self.track_history if tid not in active_ids]
        for tid in stale:
            del self.track_history[tid]


class DirectionAnalyzer:
    """Phân tích hướng di chuyển của phương tiện."""

    def __init__(self):
        # track_id → {x, y, x_prev, y_prev, cum_dir, counter, flag}
        self._tracks: dict[int, dict] = {}

    def update(self, track_id: int, x: int, y: int) -> dict:
        """Cập nhật vị trí và tính toán hướng."""
        if track_id not in self._tracks:
            self._tracks[track_id] = {
                "x": x, "y": y, "x_prev": x, "y_prev": y,
                "cum_dir": 0, "counter": 0, "flag": "NONE",
            }
        else:
            t = self._tracks[track_id]
            cum_dir = t["cum_dir"] + (y - t["y_prev"])
            self._tracks[track_id] = {
                "x": x, "y": y,
                "x_prev": t["x"], "y_prev": t["y"],
                "cum_dir": cum_dir,
                "counter": t["counter"] + 1,
                "flag": t["flag"],
            }
        return self._tracks[track_id]

    def set_flag(self, track_id: int, flag: str):
        """Đặt flag hướng (LEFT/RIGHT/NONE)."""
        if track_id in self._tracks:
            self._tracks[track_id]["flag"] = flag

    def check_wrong_direction(self, track_id: int, region_name: str) -> bool:
        """Kiểm tra đi ngược chiều.

        region_name = "RIGHT": cum_dir < 0 và counter >= 20 → vi phạm
        region_name = "LEFT":  cum_dir > 0 và counter >= 20 → vi phạm
        """
        t = self._tracks.get(track_id)
        if t is None or t["counter"] < 20:
            return False

        if region_name == "RIGHT" and t["flag"] == "RIGHT":
            return int(t["cum_dir"]) < 0
        if region_name == "LEFT" and t["flag"] == "LEFT":
            return int(t["cum_dir"]) > 0
        return False

    def check_overtaking(self, track_id: int, direction: str) -> bool:
        """Kiểm tra có đang di chuyển ở làn trái/phải không."""
        t = self._tracks.get(track_id)
        if t is None or t["counter"] < 21:
            return False
        if direction == "LEFT":
            return int(t["cum_dir"]) < 0
        if direction == "RIGHT":
            return int(t["cum_dir"]) > 0
        return False

    def cleanup(self, max_size: int = 20):
        """Giới hạn kích thước bộ nhớ."""
        if len(self._tracks) > max_size * 2:
            # Giữ lại max_size track gần nhất
            keys = list(self._tracks.keys())[-max_size:]
            self._tracks = {k: self._tracks[k] for k in keys}


class SpeedEstimator:
    """Ước tính tốc độ dựa trên 2 điểm A-B.

    Logic:
    1. Phương tiện vào POINT_A → lưu first_point, bắt đầu đếm thời gian
    2. Phương tiện đi qua các frame giữa A-B → tiếp tục đếm
    3. Phương tiện vào POINT_B → dừng đếm, tính tốc độ
    """

    def __init__(self, cfg: AppConfig):
        self.cfg = cfg
        self._first_points: dict[int, tuple] = {}
        self._counters: dict[int, float] = {}
        self._last_speed: dict[int, float] = {}
        self._zones: dict[int, str] = {}
        self._prev_zones: dict[int, str] = {}
        # track_id → True khi đang đo tốc độ (đã vào A, chưa vào B)
        self._measuring: dict[int, bool] = {}

    def set_zone(self, track_id: int, zone_name: str):
        """Cập nhật zone hiện tại."""
        self._prev_zones[track_id] = self._zones.get(track_id, "")
        self._zones[track_id] = zone_name

    def get_zone(self, track_id: int) -> str:
        return self._zones.get(track_id, "")

    def start_measuring(self, track_id: int, x: int, y: int):
        """Bắt đầu đo tốc độ - gọi khi vào POINT_A hoặc POINT_B."""
        self._first_points[track_id] = (x, y)
        self._counters[track_id] = 0.0
        self._measuring[track_id] = True

    def stop_measuring(self, track_id: int):
        """Dừng đo tốc độ."""
        self._measuring[track_id] = False

    def is_measuring(self, track_id: int) -> bool:
        return self._measuring.get(track_id, False)

    def tick(self, track_id: int, fps: float):
        """Tăng bộ đếm thời gian - gọi mỗi frame nếu đang đo."""
        if not self.is_measuring(track_id):
            return
        if track_id not in self._counters:
            self._counters[track_id] = 0.0
        self._counters[track_id] += 1.0 / fps if fps > 0 else 1.0

    def is_transition(self, track_id: int, zone: str) -> bool:
        """Kiểm tra có phải đi từ A→B hoặc B→A không."""
        prev_zone = self._prev_zones.get(track_id, "")
        if not prev_zone:
            return False
        return (prev_zone == "POINT_A" and zone == "POINT_B") or \
               (prev_zone == "POINT_B" and zone == "POINT_A")

    def compute_speed(self, track_id: int, current_x: int, current_y: int) -> float:
        """Tính tốc độ từ first_point đến vị trí hiện tại."""
        first = self._first_points.pop(track_id, None)
        if first is None:
            return 0.0
        distance = euclidean_distance(current_x, current_y, first[0], first[1])
        time_s = self._counters.pop(track_id, 1.0)
        self._measuring.pop(track_id, None)

        if time_s <= 0:
            time_s = 1.0

        speed = calculate_speed(
            distance, time_s,
            self.cfg.width_in_meter, self.cfg.width_in_pixel, self.cfg.calibration_factor,
        )
        self._last_speed[track_id] = speed
        return speed

    def get_first_point(self, track_id: int) -> Optional[tuple]:
        return self._first_points.get(track_id)

    def get_last_speed(self, track_id: int) -> float:
        return self._last_speed.get(track_id, 0.0)

    def cleanup(self, max_size: int = 30):
        """Giới hạn kích thước bộ nhớ."""
        if len(self._zones) > max_size:
            keys = list(self._zones.keys())[-max_size:]
            self._zones = {k: self._zones[k] for k in keys}
            self._prev_zones = {k: self._prev_zones[k] for k in keys if k in self._prev_zones}
            self._first_points = {k: self._first_points[k] for k in keys if k in self._first_points}
            self._counters = {k: self._counters[k] for k in keys if k in self._counters}
            self._last_speed = {k: self._last_speed[k] for k in keys if k in self._last_speed}
            self._measuring = {k: self._measuring[k] for k in keys if k in self._measuring}
