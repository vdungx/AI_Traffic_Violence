"""Violation detection orchestrator - Điều phối tất cả các kiểm tra vi phạm."""

from dataclasses import dataclass
from enum import Enum

import cv2
import numpy as np
from queue import Queue
from threading import Thread

from ..config import AppConfig
from ..database import Database, DATALOG_DB
from ..utils.image import (
    STATIC_BASE, get_current_time, build_violation_path,
    build_plate_path, build_plate_path_html, build_violation_path_html,
)
from .detector import (
    VehicleDetector, HelmetDetector, SeatbeltDetector, LicensePlateDetector,
    NON_MOTORCYCLE,
)


class ViolationType(Enum):
    NO_HELMET = "Không mũ bảo hiểm"
    NO_SEATBELT = "Không thắt dây an toàn"
    OVERSPEED = "Quá tốc độ"
    WRONG_DIRECTION = "Đi ngược chiều"
    OVERTAKING = "Vượt ẩu"


@dataclass
class Violation:
    """Thông tin một vi phạm."""
    track_id: int
    vtype: ViolationType
    timestamp: str
    speed: float
    vehicle: str
    image_path: str = ""
    plate_path: str = ""


class ViolationDetector:
    """Điều phối phát hiện vi phạm trên mỗi frame."""

    def __init__(self, cfg: AppConfig):
        self.cfg = cfg
        self.vehicle_detector = VehicleDetector(cfg.model)
        self.helmet_detector = HelmetDetector()
        self.seatbelt_detector = SeatbeltDetector()
        self.plate_detector = LicensePlateDetector()

        # Theo dõi vi phạm đã phát hiện để tránh trùng lặp
        self._flagged_helm: list[int] = []
        self._flagged_seatbelt: list[int] = []
        self._flagged_overspeed: list[int] = []
        self._flagged_overtaking: list[int] = []
        self._flagged_wrong_dir: list[int] = []
        self._helm_dates: dict[int, str] = {}
        self._seatbelt_dates: dict[int, str] = {}
        self._wrong_dir_dates: dict[int, str] = {}
        self._overtaking_dates: dict[int, str] = {}

    def detect_motorcycle_violations(
        self, frame: np.ndarray, clean_frame: np.ndarray,
        x1: int, y1: int, x2: int, y2: int,
        track_id: int, speed: float, vehicle: str,
        crossed_ab: bool,
    ) -> list[Violation]:
        """Phát hiện vi phạm cho xe máy (mũ bảo hiểm + vượt xe)."""
        violations = []
        if not crossed_ab:
            return violations

        ts = get_current_time()
        h, w = frame.shape[:2]
        pad = 50

        y1c = max(0, y1 - 100)
        y2c = min(h, y2 + 50)
        x1c = max(0, x1 - pad)
        x2c = min(w, x2 + pad)
        cropped = clean_frame[y1c:y2c, x1c:x2c]
        if cropped.size == 0:
            return violations

        # --- Helmet check ---
        if track_id not in self._flagged_helm:
            q: Queue = Queue()
            t = Thread(target=self._thread_detect_helmet, args=(q, cropped, track_id))
            t.start()
            t.join()
            if not q.empty():
                img_get, get_id, status = q.get()
                if status == "no-helm":
                    save_dir = build_violation_path(
                        STATIC_BASE, "Helmet", track_id, ts, "no-helmet_"
                    )
                    cv2.imwrite(save_dir, frame)
                    self._flagged_helm.append(track_id)
                    self._helm_dates[track_id] = ts
                    violations.append(Violation(
                        track_id=track_id,
                        vtype=ViolationType.NO_HELMET,
                        timestamp=ts,
                        speed=speed,
                        vehicle=vehicle,
                        image_path=save_dir,
                    ))

        # --- Overtaking check (left/right lane movement) ---
        if track_id not in self._flagged_overtaking:
            # Logic vượt xe đã nằm trong main loop
            pass

        return violations

    def detect_car_violations(
        self, frame: np.ndarray, clean_frame: np.ndarray,
        x1: int, y1: int, x2: int, y2: int,
        track_id: int, speed: float, vehicle: str,
        crossed_ab: bool,
    ) -> list[Violation]:
        """Phát hiện vi phạm cho ô tô (dây an toàn + quá tốc độ + vượt xe)."""
        violations = []
        if not crossed_ab:
            return violations

        ts = get_current_time()
        h, w = frame.shape[:2]
        pad = 50

        y1c = max(0, y1 - 100)
        y2c = min(h, y2 + 50)
        x1c = max(0, x1 - pad)
        x2c = min(w, x2 + pad)
        cropped = clean_frame[y1c:y2c, x1c:x2c]
        if cropped.size == 0:
            return violations

        # --- Seatbelt check ---
        if track_id not in self._flagged_seatbelt:
            q: Queue = Queue()
            t = Thread(target=self._thread_detect_seatbelt, args=(q, cropped, track_id))
            t.start()
            t.join()
            if not q.empty():
                img_get, get_id, status = q.get()
                if status == "no-seatbelt":
                    save_dir = build_violation_path(
                        STATIC_BASE, "Seatbelt", track_id, ts, "no-seatbelt_"
                    )
                    cv2.imwrite(save_dir, frame)
                    self._flagged_seatbelt.append(track_id)
                    self._seatbelt_dates[track_id] = ts
                    violations.append(Violation(
                        track_id=track_id,
                        vtype=ViolationType.NO_SEATBELT,
                        timestamp=ts,
                        speed=speed,
                        vehicle=vehicle,
                        image_path=save_dir,
                    ))

        # --- Overspeed check ---
        if speed > self.cfg.max_speed and track_id not in self._flagged_overspeed:
            last_spd = speed  # Sẽ validate range ở caller
            if speed <= self.cfg.max_speed * 4:  # phạm vi hợp lệ
                save_dir = build_violation_path(
                    STATIC_BASE, "Overspeed", track_id, ts, "overspeed_"
                )
                cv2.imwrite(save_dir, frame)
                self._flagged_overspeed.append(track_id)
                violations.append(Violation(
                    track_id=track_id,
                    vtype=ViolationType.OVERSPEED,
                    timestamp=ts,
                    speed=speed,
                    vehicle=vehicle,
                    image_path=save_dir,
                ))

        return violations

    def detect_wrong_direction(
        self, frame: np.ndarray, clean_frame: np.ndarray,
        x1: int, y1: int, x2: int, y2: int,
        track_id: int, speed: float, vehicle: str,
        crossed_ab: bool,
    ) -> list[Violation]:
        """Phát hiện đi ngược chiều."""
        violations = []
        if not crossed_ab or track_id in self._flagged_wrong_dir:
            return violations

        ts = get_current_time()
        h, w = frame.shape[:2]
        pad = 50
        y1c = max(0, y1 - 50)
        y2c = min(h, y2 + 50)
        x1c = max(0, x1 - pad)
        x2c = min(w, x2 + pad)
        cropped = clean_frame[y1c:y2c, x1c:x2c]
        if cropped.size == 0:
            return violations

        save_dir = build_violation_path(
            STATIC_BASE, "Wrong Direction", track_id, ts, "_"
        )
        cv2.imwrite(save_dir, frame)
        self._flagged_wrong_dir.append(track_id)
        self._wrong_dir_dates[track_id] = ts
        violations.append(Violation(
            track_id=track_id,
            vtype=ViolationType.WRONG_DIRECTION,
            timestamp=ts,
            speed=speed,
            vehicle=vehicle,
            image_path=save_dir,
        ))
        return violations

    def save_datalog(self, v: Violation, plate_path: str = ""):
        """Lưu vi phạm vào datalog.db."""
        html_plate = plate_path.replace("\\", "/") if plate_path else "Không phát hiện"
        photo_html = build_violation_path_html(
            v.vtype.value, v.track_id, v.timestamp,
            v.vtype.value.lower().replace(" ", "") + "_",
        )
        with Database(DATALOG_DB, use_row_factory=False) as conn:
            conn.execute(
                "INSERT INTO datalog (track_id, date, plat_license, speed, max_speed, "
                "violence_category, vehicle, location, open_photo) VALUES (?,?,?,?,?,?,?,?,?)",
                (str(v.track_id), v.timestamp, html_plate, str(v.speed),
                 str(self.cfg.max_speed), v.vtype.value, v.vehicle,
                 self.cfg.location, photo_html),
            )

    def crop_and_save_plate(
        self, frame: np.ndarray, x1: int, y1: int, x2: int, y2: int,
        track_id: int, category: str,
    ) -> str:
        """Crop biển số từ frame và lưu file. Trả về đường dẫn HTML hoặc rỗng."""
        h, w = frame.shape[:2]
        pad = 50
        y1c = max(0, y1 - 50)
        y2c = min(h, y2 + 50)
        x1c = max(0, x1 - pad)
        x2c = min(w, x2 + pad)
        cropped = frame[y1c:y2c, x1c:x2c]
        if cropped.size == 0:
            return ""

        ts = get_current_time()
        img, found = self.plate_detector.detect_and_crop(cropped)
        if found and img is not None:
            plate_path = build_plate_path(STATIC_BASE, category, track_id, ts)
            cv2.imwrite(plate_path, img)
            return build_plate_path_html(category, ts, track_id)
        return ""

    # --- Thread helpers ---

    @staticmethod
    def _thread_detect_helmet(q: Queue, frame: np.ndarray, track_id: int):
        try:
            d = HelmetDetector()
            img, status = d.detect(frame)
            q.put((img, track_id, status))
        except Exception as e:
            q.put((None, track_id, ""))

    @staticmethod
    def _thread_detect_seatbelt(q: Queue, frame: np.ndarray, track_id: int):
        try:
            d = SeatbeltDetector()
            img, status = d.detect(frame)
            q.put((img, track_id, status))
        except Exception as e:
            q.put((None, track_id, ""))

    # --- Memory cleanup ---

    def cleanup(self):
        """Dọn dẹp buffer khi quá lớn."""
        max_buf = 20
        if len(self._flagged_helm) > max_buf:
            self._flagged_helm = self._flagged_helm[-max_buf:]
        if len(self._flagged_seatbelt) > max_buf:
            self._flagged_seatbelt = self._flagged_seatbelt[-max_buf:]
        if len(self._flagged_overspeed) > max_buf:
            self._flagged_overspeed = self._flagged_overspeed[-max_buf:]
        if len(self._flagged_overtaking) > max_buf:
            self._flagged_overtaking = self._flagged_overtaking[-max_buf:]
        if len(self._flagged_wrong_dir) > max_buf:
            self._flagged_wrong_dir = self._flagged_wrong_dir[-max_buf:]
        # Sync dates dicts
        for d in [self._helm_dates, self._seatbelt_dates,
                  self._wrong_dir_dates, self._overtaking_dates]:
            stale = [k for k in d if k not in self._flagged_helm
                     and k not in self._flagged_seatbelt
                     and k not in self._flagged_wrong_dir
                     and k not in self._flagged_overtaking]
            for k in stale:
                d.pop(k, None)

    # --- Properties ---

    @property
    def flagged_helm(self) -> list:
        return self._flagged_helm

    @property
    def flagged_seatbelt(self) -> list:
        return self._flagged_seatbelt

    @property
    def flagged_overspeed(self) -> list:
        return self._flagged_overspeed

    @property
    def flagged_overtaking(self) -> list:
        return self._flagged_overtaking

    @property
    def flagged_wrong_dir(self) -> list:
        return self._flagged_wrong_dir

    @property
    def helm_dates(self) -> dict:
        return self._helm_dates

    @property
    def seatbelt_dates(self) -> dict:
        return self._seatbelt_dates

    @property
    def wrong_dir_dates(self) -> dict:
        return self._wrong_dir_dates

    @property
    def overtaking_dates(self) -> dict:
        return self._overtaking_dates
