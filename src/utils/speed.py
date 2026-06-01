"""Speed calculation helpers."""

import math
from typing import Tuple


def euclidean_distance(x1: float, y1: float, x2: float, y2: float) -> float:
    """Tính khoảng cách Euclid giữa 2 điểm."""
    return math.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2)


def calculate_speed(
    distance_pixels: float,
    time_seconds: float,
    width_in_meter: float,
    width_in_pixel: float,
    calibration_factor: float,
) -> float:
    """Tính tốc độ (km/h) từ khoảng cách pixel và thời gian.

    Công thức: speed = (distance / time) * (meter/pixel) * calibration * 3.6
    """
    if time_seconds <= 0:
        time_seconds = 1.0
    return round(
        (distance_pixels / time_seconds)
        * (width_in_meter / width_in_pixel)
        * calibration_factor
        * 3.6,
        2,
    )


def is_speed_in_range(speed: float, last_speed: float) -> bool:
    """Kiểm tra tốc độ có nằm trong phạm vi hợp lệ so với lần đo trước."""
    window_limit = last_speed * 2
    return (window_limit / 4) <= speed <= window_limit


def format_speed(speed: float, max_speed: float) -> str:
    """Format tốc độ để hiển thị."""
    if speed <= 5:
        return "không phát hiện"
    elif speed >= max_speed * 2:
        return "ngoài phạm vi"
    return f"{speed} km/h"
