"""YOLO model wrappers cho các bài toán phát hiện khác nhau."""

import numpy as np
from ultralytics import YOLO

# COCO class IDs cho phương tiện giao thông
# YOLOv8 COCO: person=0, bicycle=1, car=2, motorcycle=3, bus=5, truck=7
MOTORCYCLE = 3
BICYCLE = 1
CAR = 2
BUS = 5
TRUCK = 7

# Tập phương tiện cần theo dõi
ALL_VEHICLES = {BICYCLE, CAR, MOTORCYCLE, BUS, TRUCK}
NON_MOTORCYCLE = {CAR, BUS, TRUCK}


class VehicleDetector:
    """Phát hiện và theo dõi phương tiện bằng YOLOv8 COCO pretrained."""

    def __init__(self, model_path: str = "models/yolo/yolov8x.pt"):
        self.model = YOLO(model_path)

    def track(self, frame: np.ndarray) -> list[dict]:
        """Chạy tracking trả về danh sách đối tượng phát hiện.

        Returns list của dict: {track_id, class_id, xyxy, xywh}
        """
        results = self.model.track(frame, persist=True, verbose=False)
        detections = []
        if results[0].boxes is not None and results[0].boxes.id is not None:
            boxes = results[0].boxes.xyxy.cpu().numpy()
            track_ids = results[0].boxes.id.cpu().numpy().astype(int)
            class_ids = results[0].boxes.cls.cpu().numpy().astype(int)
            for box, tid, cid in zip(boxes, track_ids, class_ids):
                detections.append({
                    "track_id": tid,
                    "class_id": cid,
                    "xyxy": box.astype(int),
                })
        return detections

    @property
    def class_names(self) -> dict:
        """dict tên class theo ID."""
        return self.model.names


class HelmetDetector:
    """Phát hiện không đội mũ bảo hiểm cho xe máy."""

    def __init__(self, model_path: str = "models/helmet_9.pt"):
        self.model = YOLO(model_path)
        self.target_class = "no-helm"

    def detect(self, frame: np.ndarray, retries: int = 5) -> tuple:
        """Phát hiện vi phạm mũ bảo hiểm.

        Returns: (cropped_image or None, status: str)
        status = "no-helm" nếu vi phạm, "" nếu không
        """
        for attempt in range(retries):
            results = self.model.predict(source=frame, verbose=False)
            if len(results[0].boxes) > 0:
                class_ids = results[0].boxes.cls.cpu().numpy().astype(int)
                for i, result in enumerate(results[0].boxes):
                    if self.model.names[int(class_ids[i])] == self.target_class:
                        x1, y1, x2, y2 = map(int, result.xyxy[0])
                        return frame[y1:y2, x1:x2], self.target_class
                return None, ""
        return None, ""


class SeatbeltDetector:
    """Phát hiện không thắt dây an toàn cho ô tô."""

    def __init__(self, model_path: str = "models/seat_belt_5.pt"):
        self.model = YOLO(model_path)
        self.target_class = "NoSeatBelt"

    def detect(self, frame: np.ndarray, retries: int = 5) -> tuple:
        """Phát hiện vi phạm dây an toàn.

        Returns: (cropped_image or None, status: str)
        status = "no-seatbelt" nếu vi phạm, "" nếu không
        """
        for attempt in range(retries):
            results = self.model.predict(source=frame, verbose=False)
            if len(results[0].boxes) > 0:
                class_ids = results[0].boxes.cls.cpu().numpy().astype(int)
                for i, result in enumerate(results[0].boxes):
                    if self.model.names[int(class_ids[i])] == self.target_class:
                        x1, y1, x2, y2 = map(int, result.xyxy[0])
                        return frame[y1:y2, x1:x2], "no-seatbelt"
                return None, ""
        return None, ""


class LicensePlateDetector:
    """Phát hiện và crop biển số xe."""

    def __init__(self, model_path: str = "models/plat_license.pt"):
        self.model = YOLO(model_path)

    def detect_and_crop(self, frame: np.ndarray, retries: int = 4, conf: float = 0.1) -> tuple:
        """Phát hiện biển số và crop.

        Args:
            conf: ngưỡng confidence (thấp hơn để detect được nhiều hơn)

        Returns: (cropped_image or None, found: bool)
        """
        for attempt in range(retries):
            results = self.model.predict(source=frame, conf=conf)
            if len(results[0].boxes) > 0:
                class_ids = results[0].boxes.cls.cpu().numpy().astype(int)
                for i, result in enumerate(results[0].boxes):
                    if self.model.names[int(class_ids[i])] == ".":
                        x1, y1, x2, y2 = map(int, result.xyxy[0])
                        return frame[y1:y2, x1:x2], True
                return None, False
        return None, False
