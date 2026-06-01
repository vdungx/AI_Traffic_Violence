"""VideoApp - Ứng dụng chính với Tkinter GUI cho phát hiện vi phạm giao thông."""

import math
import os
import sqlite3
import tkinter as tk
from collections import defaultdict, deque
from pathlib import Path
from queue import Queue
from threading import Thread

# Tên phương tiện (từ YOLO COCO) → Tiếng Việt không dấu (OpenCV ko hỗ trợ font Unicode)
VEHICLE_TRANSLATION = {
    "car": "O to",
    "motorcycle": "Xe may",
    "bus": "Xe buyt",
    "truck": "Xe tai",
    "bicycle": "Xe dap",
}
# Tên phương tiện có dấu (hiển thị trên web)
VEHICLE_VI = {
    "car": "Ô tô",
    "motorcycle": "Xe máy",
    "bus": "Xe buýt",
    "truck": "Xe tải",
    "bicycle": "Xe đạp",
}
from typing import Optional

import cv2
import numpy as np
from PIL import Image, ImageTk
from tkinter import messagebox

from ..config import AppConfig, load_config
from ..database import (
    init_all_databases,
    CONFIG_DB, DATALOG_DB, SAVE_IP_DB,
)
from ..detection.detector import (
    VehicleDetector, HelmetDetector, SeatbeltDetector, LicensePlateDetector,
    ALL_VEHICLES, NON_MOTORCYCLE, MOTORCYCLE,
)
from ..detection.tracker import TrackManager, DirectionAnalyzer, SpeedEstimator
from ..detection.violation import ViolationDetector
from .canvas import CanvasManager
from .widgets import ConfigDialog, AreaDrawer, LineDrawer, check_line_intersection
from ..utils.image import (
    STATIC_BASE, get_current_time, build_violation_path,
    build_plate_path, build_plate_path_html, build_violation_path_html,
    SLASH,
)
from ..utils.speed import euclidean_distance, is_speed_in_range

# Hằng số
CANVAS_W, CANVAS_H = 1600, 900
SLASH_HTML = "/"


class VideoApp:
    """Ứng dụng chính - GUI + detection + tracking."""

    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Bảng Điều Khiển AI YOLO Tương Tác")
        self.root.resizable(True, True)
        self.root.minsize(1600, 950)

        # ── Khởi tạo database ──
        init_all_databases()
        self.cfg: AppConfig = load_config()

        # ── Kết nối DB riêng cho areas/lines (lưu vào memory) ──
        self._conn = sqlite3.connect(CONFIG_DB)
        self._conn_data = sqlite3.connect(DATALOG_DB)
        self._conn_ip = sqlite3.connect(SAVE_IP_DB)
        self._init_db_tables()

        # ── Detectors ──
        self.vehicle_detector = VehicleDetector(self.cfg.model)
        self.helmet_detector = HelmetDetector()
        self.seatbelt_detector = SeatbeltDetector()
        self.plate_detector = LicensePlateDetector()
        self.violation_detector = ViolationDetector(self.cfg)

        # ── Trackers ──
        self.track_mgr = TrackManager()
        self.dir_analyzer = DirectionAnalyzer()
        self.speed_est = SpeedEstimator(self.cfg)

        # ── Trạng thái ──
        self.camera: Optional[cv2.VideoCapture] = None
        self.use_camera = False
        self.use_yolo = False
        self.use_distance = False
        self.status_text = tk.StringVar(value="Sẵn sàng")
        self.mouse_text = tk.StringVar(value="Tọa độ chuột:")

        # ── Areas & Lines (draw trên canvas) ──
        self.areas: list[tuple] = []  # (canvas_id, name, coords_str)
        self.lines: list[tuple] = []  # (canvas_id, name, x1, y1, x2, y2)

        # ── Violation tracking ──
        self._helm_ids: list[int] = []
        self._seatbelt_ids: list[int] = []
        self._overspeed_ids: list[int] = []
        self._overtaking_ids: list[int] = []
        self._wrong_dir_ids: list[int] = []
        self._helm_flags: list[int] = []
        self._seatbelt_flags: list[int] = []
        self._helm_dates: dict[int, str] = {}
        self._seatbelt_dates: dict[int, str] = {}
        self._wrong_dir_dates: dict[int, str] = {}
        self._overtaking_dates: dict[int, str] = {}

        # Lane tracking
        self._left_lane_ids: list[int] = []
        self._right_lane_ids: list[int] = []
        self._left_lane_pos: dict[int, tuple] = {}
        self._right_lane_pos: dict[int, tuple] = {}

        # ── Gọi UI ──
        self._build_ui()
        self._load_areas()
        self._load_lines()
        self._load_ip()

    # ===================================================================
    # UI BUILD
    # ===================================================================

    def _build_ui(self):
        """Xây dựng giao diện."""
        # Status bar
        tk.Label(self.root, textvariable=self.status_text, anchor="w").pack(
            side="top", fill="x", pady=5
        )

        # Canvas
        self.canvas = tk.Canvas(self.root, width=CANVAS_W, height=CANVAS_H, bg="gray20")
        self.canvas.pack()

        self.canvas_mgr = CanvasManager(self.canvas)

        # Control frame
        cf = tk.Frame(self.root)
        cf.pack(side="top", fill="x", pady=5)

        tk.Label(cf, text="Nhập IP:").grid(row=0, column=0, padx=5)

        self.ip_var = tk.StringVar()
        tk.Entry(cf, textvariable=self.ip_var, width=40).grid(row=0, column=1, padx=5)

        buttons = [
            ("Kết nối Camera", self._connect_camera, 2),
            ("Bật/Tắt AI (YOLO)", self._toggle_yolo, 3),
            ("Cảm biến khoảng cách", self._toggle_distance, 4),
            ("Thêm Khu vực", self._start_area_draw, 5),
            ("Vẽ Đường", self._start_line_draw, 6),
            ("Hoàn tác Khu vực", self._undo_area, 7),
            ("Hoàn tác Đường", self._undo_line, 8),
            ("Cấu hình", self._open_config, 9),
            ("Thoát", self.root.quit, 10),
        ]
        for text, cmd, col in buttons:
            tk.Button(cf, text=text, command=cmd, width=15).grid(row=0, column=col, padx=2)

        # Phím tắt F11 để toggle fullscreen
        self.root.bind("<F11>", lambda e: self._toggle_fullscreen())
        # Escape để thoát fullscreen
        self.root.bind("<Escape>", lambda e: self._exit_fullscreen())

        # Mouse coords
        tk.Label(self.root, textvariable=self.mouse_text, anchor="w").pack(side="bottom", fill="x")

        # Events
        self.canvas.bind("<Button-1>", self._on_canvas_click)
        self.canvas.bind("<Motion>", self._on_mouse_move)

    def _toggle_fullscreen(self):
        """Bật/tắt toàn màn hình."""
        self._fullscreen = not getattr(self, "_fullscreen", False)
        self.root.attributes("-fullscreen", self._fullscreen)

    def _exit_fullscreen(self):
        """Thoát toàn màn hình."""
        self._fullscreen = False
        self.root.attributes("-fullscreen", False)

    # ===================================================================
    # DATABASE INIT
    # ===================================================================

    def _init_db_tables(self):
        with self._conn:
            self._conn.execute("""
                CREATE TABLE IF NOT EXISTS areas (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL, coordinates TEXT NOT NULL
                )
            """)
            self._conn.execute("""
                CREATE TABLE IF NOT EXISTS lines (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL, x1 INTEGER, y1 INTEGER, x2 INTEGER, y2 INTEGER
                )
            """)
            self._conn.execute("""
                CREATE TABLE IF NOT EXISTS config (
                    id INTEGER PRIMARY KEY,
                    calibration_factor REAL, max_speed REAL,
                    width_in_pixel REAL, width_in_meter REAL,
                    actual_time REAL, yolo_time REAL,
                    location TEXT NOT NULL, Model TEXT NOT NULL
                )
            """)
        with self._conn_data:
            self._conn_data.execute("""
                CREATE TABLE IF NOT EXISTS datalog (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    track_id TEXT NOT NULL, date TEXT NOT NULL,
                    plat_license TEXT NOT NULL, speed TEXT NOT NULL,
                    max_speed TEXT NOT NULL, violence_category TEXT NOT NULL,
                    vehicle TEXT NOT NULL, location TEXT NOT NULL,
                    open_photo TEXT NOT NULL
                )
            """)
        with self._conn_ip:
            self._conn_ip.execute("""
                CREATE TABLE IF NOT EXISTS save_ip (IP TEXT NOT NULL)
            """)

    def _load_areas(self):
        cursor = self._conn.execute("SELECT name, coordinates FROM areas")
        for name, coords_str in cursor.fetchall():
            coords = list(map(int, coords_str.split(",")))
            area_id = self.canvas.create_polygon(coords, outline="red", fill="")
            self.areas.append((area_id, name, coords_str))

    def _load_lines(self):
        cursor = self._conn.execute("SELECT name, x1, y1, x2, y2 FROM lines")
        for name, x1, y1, x2, y2 in cursor.fetchall():
            line_id = self.canvas.create_line(x1, y1, x2, y2, fill="green", width=2)
            self.lines.append((line_id, name, x1, y1, x2, y2))
            mid = ((x1 + x2) / 2, (y1 + y2) / 2)
            dist = round(math.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2), 1)
            self.canvas.create_text(*mid, text=str(dist), fill="black")

    def _load_ip(self):
        cursor = self._conn_ip.execute("SELECT IP FROM save_ip")
        row = cursor.fetchone()
        if row and row[0]:
            self.ip_var.set(row[0])

    def _save_ip(self, ip: str):
        with self._conn_ip:
            cursor = self._conn_ip.cursor()
            cursor.execute("SELECT COUNT(*) FROM save_ip")
            if cursor.fetchone()[0] == 0:
                cursor.execute("INSERT INTO save_ip (IP) VALUES (?)", (ip,))
            else:
                cursor.execute(
                    "UPDATE save_ip SET IP = ? WHERE ROWID = (SELECT ROWID FROM save_ip LIMIT 1)",
                    (ip,),
                )

    # ===================================================================
    # UI HANDLERS
    # ===================================================================

    def _on_canvas_click(self, event):
        x, y = event.x, event.y
        self.canvas.create_oval(x - 3, y - 3, x + 3, y + 3, fill="blue")
        self.canvas.create_text(x + 10, y, text=f"({x}, {y})", anchor=tk.W, fill="blue")
        self.mouse_text.set(f"Chuột đã nhấp tại: ({x}, {y})")

    def _on_mouse_move(self, event):
        x, y = event.x, event.y
        in_area = False
        for area_id, name, coords_str in self.areas:
            coords = list(self.canvas.coords(area_id))
            if coords and self.canvas_mgr.is_point_in_polygon(x, y, coords):
                self.mouse_text.set(f"Chuột trong khu vực '{name}' tại: ({x}, {y})")
                in_area = True
                break
        if not in_area:
            for _, name, x1, y1, x2, y2 in self.lines:
                if self.canvas_mgr.is_near_line(x1, y1, x2, y2, x, y):
                    self.mouse_text.set(f"Chuột gần đường '{name}' tại: ({x}, {y})")
                    in_area = True
                    break
        if not in_area:
            self.mouse_text.set(f"Tọa độ chuột: ({x}, {y})")

    # ===================================================================
    # AREA DRAWING
    # ===================================================================

    def _start_area_draw(self):
        messagebox.showinfo(
            "Hướng dẫn",
            "Chế độ vẽ khu vực:\n- Chuột trái: Thêm điểm.\n- Chuột phải (hoặc Nhấp đúp): Hoàn tất."
        )
        drawer = AreaDrawer(self.canvas)
        self.canvas.bind("<Button-1>", drawer.on_click)
        self.canvas.bind("<Motion>", drawer.on_motion)
        self.canvas.bind("<Button-3>", lambda e: self._finish_area_draw(drawer))
        self.canvas.bind("<Double-Button-1>", lambda e: self._finish_area_draw(drawer))

    def _finish_area_draw(self, drawer: AreaDrawer):
        coords = drawer.finish()
        if coords:
            name = tk.simpledialog.askstring("Input", "Nhập tên khu vực:")
            if name:
                coords_str = ",".join(map(str, coords))
                area_id = self.canvas.create_polygon(coords, outline="red", fill="")
                self.areas.append((area_id, name, coords_str))
                with self._conn:
                    self._conn.execute(
                        "INSERT INTO areas (name, coordinates) VALUES (?, ?)",
                        (name, coords_str),
                    )
        self.canvas.bind("<Button-1>", self._on_canvas_click)
        self.canvas.bind("<Motion>", self._on_mouse_move)
        self.canvas.unbind("<Button-3>")
        self.canvas.unbind("<Double-Button-1>")

    # ===================================================================
    # LINE DRAWING
    # ===================================================================

    def _start_line_draw(self):
        drawer = LineDrawer(self.canvas)
        self.canvas.bind("<ButtonPress-1>", drawer.on_press)
        self.canvas.bind("<B1-Motion>", drawer.on_drag)
        self.canvas.bind("<ButtonRelease-1>", lambda e: self._finish_line_draw(drawer))

    def _finish_line_draw(self, drawer: LineDrawer):
        # Lấy vị trí chuột thực tế khi release
        # (vì <ButtonRelease-1> binding gọi lambda mà không truyền event)
        lx = self.canvas.winfo_pointerx() - self.canvas.winfo_rootx()
        ly = self.canvas.winfo_pointery() - self.canvas.winfo_rooty()
        # Tạo minimal event object
        _ev = type("_E", (), {"x": lx, "y": ly})()
        result = drawer.on_release(_ev)
        if result:
            x1, y1, x2, y2 = result
            name = tk.simpledialog.askstring("Input", "Nhập tên đường:")
            if name:
                dist = round(math.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2), 1)
                line_id = self.canvas.create_line(x1, y1, x2, y2, fill="green", width=2)
                self.canvas.create_text((x1 + x2) / 2, (y1 + y2) / 2, text=str(dist), fill="black")
                self.lines.append((line_id, name, x1, y1, x2, y2))
                with self._conn:
                    self._conn.execute(
                        "INSERT INTO lines (name, x1, y1, x2, y2) VALUES (?, ?, ?, ?, ?)",
                        (name, x1, y1, x2, y2),
                    )
                # Check intersection
                for existing in self.lines[:-1]:
                    ex, ey = check_line_intersection(
                        (x1, y1, x2, y2),
                        (existing[2], existing[3], existing[4], existing[5]),
                    )
                    if ex is not None:
                        self.canvas.create_text(ex, ey, text=f"x={round(ex,1)}, y={round(ey,1)}",
                                                 fill="black")
        self.canvas.bind("<Button-1>", self._on_canvas_click)
        self.canvas.bind("<Motion>", self._on_mouse_move)
        self.canvas.unbind("<ButtonPress-1>")
        self.canvas.unbind("<B1-Motion>")
        self.canvas.unbind("<ButtonRelease-1>")

    # ===================================================================
    # UNDO
    # ===================================================================

    def _undo_area(self):
        if self.areas:
            aid, name, _ = self.areas.pop()
            self.canvas.delete(aid)
            with self._conn:
                self._conn.execute("DELETE FROM areas WHERE name = ?", (name,))

    def _undo_line(self):
        if self.lines:
            lid, name, *_ = self.lines.pop()
            self.canvas.delete(lid)
            with self._conn:
                self._conn.execute("DELETE FROM lines WHERE name = ?", (name,))

    # ===================================================================
    # CONFIG DIALOG
    # ===================================================================

    def _open_config(self):
        def on_save(cfg):
            self.cfg = cfg
            self.speed_est.cfg = cfg
            self.violation_detector.cfg = cfg
            self.vehicle_detector = VehicleDetector(cfg.model)

        ConfigDialog(self.root, self.cfg, on_save)

    # ===================================================================
    # CAMERA & TOGGLE
    # ===================================================================

    def _connect_camera(self):
        self.use_camera = not self.use_camera
        if self.use_camera:
            self.camera = cv2.VideoCapture(self.ip_var.get())
            self._save_ip(self.ip_var.get())
            if not self.camera.isOpened():
                self.status_text.set(f"Kết nối thất bại: {self.ip_var.get()}")
                self.use_camera = False
                return
            self.status_text.set("Đã kết nối camera")
            self._process_loop()
        else:
            if self.camera:
                self.camera.release()

    def _toggle_yolo(self):
        self.use_yolo = not self.use_yolo
        self._update_status()

    def _toggle_distance(self):
        self.use_distance = not self.use_distance
        self._update_status()

    def _update_status(self):
        self.status_text.set(
            f"Trạng thái YOLO: {self.use_yolo}, "
            f"Cảm biến khoảng cách: {self.use_distance}"
        )

    # ===================================================================
    # MAIN PROCESSING LOOP
    # ===================================================================

    def _process_loop(self):
        """Vòng lặp chính xử lý frame."""
        success, raw_frame = self.camera.read()
        if not success:
            if self.use_camera:
                self.root.after(10, self._process_loop)
            return

        frame = cv2.resize(raw_frame, (CANVAS_W, CANVAS_H), interpolation=cv2.INTER_AREA)
        display = frame.copy()

        if self.use_yolo:
            display = self._process_yolo(display, frame, raw_frame)

        # Vẽ overlays
        display = self.canvas_mgr.draw_region_overlay(display, self.areas)
        display = self.canvas_mgr.draw_line_overlay(display, self.lines)

        # Hiển thị
        imgtk = self.canvas_mgr.draw_frame(display)
        self.canvas.imgtk = imgtk  # Giữ reference

        if self.use_camera:
            self.root.after(10, self._process_loop)

    def _process_yolo(
        self, display: np.ndarray, framedup: np.ndarray, raw_frame: np.ndarray
    ) -> np.ndarray:
        """Xử lý YOLO detection cho 1 frame."""
        detections = self.vehicle_detector.track(framedup)
        active_ids: set[int] = set()

        for det in detections:
            tid = det["track_id"]
            cid = det["class_id"]
            x1, y1, x2, y2 = det["xyxy"]
            active_ids.add(tid)

            cx = int(abs(x2 - x1) / 2) + x1
            cy = int(abs(y2 - y1) / 2) + y1

            self.track_mgr.update(tid, cx, cy)
            dir_info = self.dir_analyzer.update(tid, cx, cy)

            # ── Chỉ xử lý phương tiện giao thông ──
            if cid not in ALL_VEHICLES:
                continue

            vehicle_name = self.vehicle_detector.class_names.get(cid, str(cid))
            is_motorcycle = vehicle_name == "motorcycle"
            vehicle_display = VEHICLE_TRANSLATION.get(vehicle_name, vehicle_name)
            vehicle_vi = VEHICLE_VI.get(vehicle_name, vehicle_name)
            is_motorcycle_cid = (cid == MOTORCYCLE)

            # Vẽ bounding box + track path
            display = self.canvas_mgr.draw_detection_box(
                display, x1, y1, x2, y2, vehicle_display, (255, 0, 0)
            )
            pts = self.track_mgr.get_path_points(tid)
            display = self.canvas_mgr.draw_track_path(display, pts)

            # ── Speed measurement (zones POINT_A / POINT_B) ──
            speed = self._handle_speed_zones(tid, cx, cy, framedup)

            # ── Check A-B transition ──
            crossed = self.speed_est.is_transition(tid, self.speed_est.get_zone(tid))
            prev_zone = self.speed_est.get_zone(tid)

            # Debug: print speed và crossed cho mọi phương tiện
            if self.speed_est.is_measuring(tid):
                print(f"[SPEED DEBUG] tid={tid} vehicle={vehicle_name} "
                      f"zone={prev_zone} crossed={crossed} "
                      f"measuring=True")

            # ── Region checks ──
            for area_id, area_name, coords_str in self.areas:
                coords = list(self.canvas.coords(area_id))
                if not coords:
                    continue
                if not self.canvas_mgr.is_point_in_polygon(cx, cy, coords):
                    continue

                zone_name = area_name

                # SPEED ZONES - logic đã xử lý trong _handle_speed_zones,
                # chỉ cần hiển thị speed và check overspeed ở đây
                if zone_name in ("POINT_A", "POINT_B") and crossed:
                    spd = self.speed_est.get_last_speed(tid)
                    display = self.canvas_mgr.draw_speed_text(display, spd, x1, y2)

                    # OVERSPEED CHECK
                    self._check_overspeed(
                        display, framedup, raw_frame,
                        tid, spd, vehicle_vi, x1, y1, x2, y2, crossed,
                    )

                # WRONG DIRECTION (RIGHT zone)
                if zone_name == "RIGHT":
                    self._handle_right_zone(
                        display, framedup, raw_frame,
                        tid, dir_info, speed, vehicle_vi, x1, y1, x2, y2, crossed,
                    )

                # WRONG DIRECTION (LEFT zone)
                if zone_name == "LEFT":
                    self._handle_left_zone(
                        display, framedup, raw_frame,
                        tid, dir_info, speed, vehicle_vi, x1, y1, x2, y2, crossed,
                    )

                # OVERTAKING
                self._check_overtaking(
                    tid, dir_info, x1, y1, x2, y2,
                )

                # SEATBELT (non-motorcycle vehicles)
                if not is_motorcycle_cid and cid in NON_MOTORCYCLE:
                    self._check_seatbelt(
                        display, framedup, raw_frame,
                        tid, speed, vehicle_vi, x1, y1, x2, y2, crossed,
                    )

                # HELMET (motorcycle)
                if is_motorcycle_cid:
                    self._check_helmet(
                        display, framedup, raw_frame,
                        tid, speed, vehicle_vi, x1, y1, x2, y2, crossed,
                    )

            # ── Safe distance indicator ──
            if self.use_distance:
                self._draw_safe_distances(display, tid, cx, cy, x1, y1, x2, y2, detections)

        # Cleanup
        self._cleanup(active_ids)
        return display

    # ===================================================================
    # VIOLATION CHECKS
    # ===================================================================

    def _check_overspeed(self, display, framedup, raw_frame, tid, speed, vehicle,
                          x1, y1, x2, y2, crossed):
        if speed <= self.cfg.max_speed or tid in self._overspeed_ids or not crossed:
            if crossed and speed > 0:
                print(f"[OVERSPEED DEBUG] tid={tid} vehicle={vehicle} "
                      f"speed={speed:.1f} max={self.cfg.max_speed} "
                      f"crossed={crossed} already_flagged={tid in self._overspeed_ids}")
            return
        last_spd = self.speed_est.get_last_speed(tid)
        if last_spd > 0 and not is_speed_in_range(speed, last_spd):
            if speed > self.cfg.max_speed * 2:
                print(f"[OVERSPEED SKIP] tid={tid} speed={speed:.1f} "
                      f"last={last_spd:.1f} (out of range)")
                return
        print(f"[OVERSPEED DETECTED] tid={tid} vehicle={vehicle} speed={speed:.1f} km/h")

        ts = get_current_time()
        cv2.putText(display, "Qua toc do!!", (x1, y1),
                     cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2, cv2.LINE_AA)
        cv2.rectangle(display, (x1, y1), (x2, y2), (0, 0, 255), 2)

        save_dir = build_violation_path(STATIC_BASE, "Overspeed", tid, ts, "overspeed_")
        cv2.imwrite(save_dir, display)
        self._overspeed_ids.append(tid)

        plate_path = self._save_plate(raw_frame, "Overspeed", tid, x1, y1, x2, y2)
        self._save_datalog(tid, ts, plate_path, speed, "Quá tốc độ", vehicle,
                            "Overspeed", "overspeed_")

    def _check_helmet(self, display, framedup, raw_frame, tid, speed, vehicle,
                       x1, y1, x2, y2, crossed):
        print(f"[HELMET CALLED] tid={tid} vehicle={vehicle} crossed={crossed}")
        if tid in self._helm_flags:
            print(f"[HELMET SKIP] tid={tid} already flagged")
            return
        if not crossed:
            print(f"[HELMET SKIP] tid={tid} crossed={crossed}")
            return

        ts = get_current_time()
        h, w = framedup.shape[:2]
        y1c, y2c = max(0, y1 - 100), min(h, y2 + 50)
        x1c, x2c = max(0, x1 - 50), min(w, x2 + 50)
        cropped = framedup[y1c:y2c, x1c:x2c]
        if cropped.size == 0:
            return

        q: Queue = Queue()
        t_ht = Thread(target=self._thread_helmet, args=(q, cropped, tid))
        t_ht.start()
        t_ht.join()

        if not q.empty():
            img_get, get_id, status = q.get()
            if status == "no-helm":
                cv2.putText(display, "Khong doi mu bao hiem!!", (x1, y1),
                             cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2, cv2.LINE_AA)
                cv2.rectangle(display, (x1, y1), (x2, y2), (0, 0, 255), 2)
                save_dir = build_violation_path(STATIC_BASE, "Helmet", tid, ts, "no-helmet_")
                cv2.imwrite(save_dir, display)
                self._helm_ids.append(tid)
                self._helm_dates[tid] = ts

                plate_path = self._save_plate(raw_frame, "Helmet", tid, x1, y1, x2, y2)
                self._save_datalog(tid, ts, plate_path, speed, "Không mũ bảo hiểm", vehicle,
                                    "Helmet", "no-helmet_")
                print(f"[HELMET VIOLATION SAVED] tid={tid} vehicle={vehicle}")

        self._helm_flags.append(tid)

    def _check_seatbelt(self, display, framedup, raw_frame, tid, speed, vehicle,
                         x1, y1, x2, y2, crossed):
        print(f"[SEATBELT CALLED] tid={tid} vehicle={vehicle} crossed={crossed}")
        if tid in self._seatbelt_flags:
            print(f"[SEATBELT SKIP] tid={tid} already flagged")
            return
        if not crossed:
            print(f"[SEATBELT SKIP] tid={tid} crossed={crossed}")
            return

        ts = get_current_time()
        h, w = framedup.shape[:2]
        y1c, y2c = max(0, y1 - 100), min(h, y2 + 50)
        x1c, x2c = max(0, x1 - 50), min(w, x2 + 50)
        cropped = framedup[y1c:y2c, x1c:x2c]
        if cropped.size == 0:
            return

        q: Queue = Queue()
        t_sb = Thread(target=self._thread_seatbelt, args=(q, cropped, tid))
        t_sb.start()
        t_sb.join()

        if not q.empty():
            img_get, get_id, status = q.get()
            if status == "no-seatbelt":
                cv2.putText(display, "Khong that day an toan!!", (x1, y1),
                             cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2, cv2.LINE_AA)
                cv2.rectangle(display, (x1, y1), (x2, y2), (0, 0, 255), 2)
                save_dir = build_violation_path(STATIC_BASE, "Seatbelt", tid, ts, "no-seatbelt_")
                cv2.imwrite(save_dir, display)
                self._seatbelt_ids.append(tid)
                self._seatbelt_dates[tid] = ts

                plate_path = self._save_plate(raw_frame, "Seatbelt", tid, x1, y1, x2, y2)
                self._save_datalog(tid, ts, plate_path, speed, "Không thắt dây an toàn", vehicle,
                                    "Seatbelt", "no-seatbelt_")
                print(f"[SEATBELT VIOLATION SAVED] tid={tid} vehicle={vehicle}")

        self._seatbelt_flags.append(tid)

    def _handle_right_zone(self, display, framedup, raw_frame, tid, dir_info,
                            speed, vehicle, x1, y1, x2, y2, crossed):
        cnt = dir_info["counter"]
        if cnt >= 5 and dir_info["flag"] == "NONE":
            self.dir_analyzer.set_flag(tid, "RIGHT")

        if (int(dir_info["cum_dir"]) < 0 and cnt >= 20
                and dir_info["flag"] == "RIGHT" and tid not in self._wrong_dir_ids):
            ts = get_current_time()
            cv2.putText(display, "Di nguoc chieu", (x1, y1),
                         cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2, cv2.LINE_AA)
            cv2.rectangle(display, (x1, y1), (x2, y2), (0, 0, 255), 2)
            save_dir = build_violation_path(STATIC_BASE, "Wrong Direction", tid, ts, "_")
            cv2.imwrite(save_dir, display)
            self._wrong_dir_ids.append(tid)
            self._wrong_dir_dates[tid] = ts

            plate_path = self._save_plate(raw_frame, "Wrong Direction", tid, x1, y1, x2, y2)
            self._save_datalog(tid, ts, plate_path, speed, "Đi ngược chiều", vehicle,
                                "Wrong Direction", "_")
            print(f"[WRONG DIR SAVED] tid={tid} vehicle={vehicle}")

    def _handle_left_zone(self, display, framedup, raw_frame, tid, dir_info,
                           speed, vehicle, x1, y1, x2, y2, crossed):
        cnt = dir_info["counter"]
        if cnt >= 5 and dir_info["flag"] == "NONE":
            self.dir_analyzer.set_flag(tid, "LEFT")

        if (int(dir_info["cum_dir"]) > 0 and cnt >= 20
                and dir_info["flag"] == "LEFT" and tid not in self._wrong_dir_ids):
            ts = get_current_time()
            cv2.putText(display, "Di nguoc chieu", (x1, y1),
                         cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2, cv2.LINE_AA)
            cv2.rectangle(display, (x1, y1), (x2, y2), (0, 0, 255), 2)
            save_dir = build_violation_path(STATIC_BASE, "Wrong Direction", tid, ts, "_")
            cv2.imwrite(save_dir, display)
            self._wrong_dir_ids.append(tid)
            self._wrong_dir_dates[tid] = ts

            plate_path = self._save_plate(raw_frame, "Wrong Direction", tid, x1, y1, x2, y2)
            self._save_datalog(tid, ts, plate_path, speed, "Đi ngược chiều", vehicle,
                                "Wrong Direction", "_")
            print(f"[WRONG DIR SAVED] tid={tid} vehicle={vehicle}")

    def _check_overtaking(self, tid, dir_info, x1, y1, x2, y2):
        cnt = dir_info["counter"]
        if cnt < 21:
            return

        if int(dir_info["cum_dir"]) < 0:
            self._left_lane_ids.append(tid)
            self._left_lane_pos[tid] = (int(abs(x2 - x1) / 2) + x1, int(abs(y2 - y1) / 2) + y1)
        if int(dir_info["cum_dir"]) > 0:
            self._right_lane_ids.append(tid)
            self._right_lane_pos[tid] = (int(abs(x2 - x1) / 2) + x1, int(abs(y2 - y1) / 2) + y1)

    def _draw_safe_distances(self, display, tid, cx, cy, x1, y1, x2, y2, detections):
        bw = abs(x2 - x1)
        for other in detections:
            oid = other["track_id"]
            if oid == tid:
                continue
            ox1, oy1, ox2, oy2 = other["xyxy"]
            ocx = int(abs(ox2 - ox1) / 2) + ox1
            ocy = int(abs(oy2 - oy1) / 2) + oy1
            dist = euclidean_distance(cx, cy, ocx, ocy)
            display = self.canvas_mgr.draw_safe_distance_line(display, cx, cy, ocx, ocy, dist, bw)

    # ===================================================================
    # SPEED ZONE HANDLING
    # ===================================================================

    def _handle_speed_zones(self, tid, cx, cy, framedup) -> float:
        """Xử lý zone tốc độ, trả về speed hiện tại.

        Logic:
        - Vào POINT_A hoặc POINT_B lần đầu → start_measuring (lưu first_point, reset counter)
        - Đang đo + vào zone còn lại → compute_speed (tính tốc độ)
        - Đang đo + đi qua frame giữa A-B → tick (đếm thời gian)
        """
        speed = self.speed_est.get_last_speed(tid)
        fps = max(self.camera.get(cv2.CAP_PROP_FPS), 1)

        in_speed_zone = False
        for area_id, area_name, coords_str in self.areas:
            if area_name not in ("POINT_A", "POINT_B"):
                continue
            coords = list(self.canvas.coords(area_id))
            if not coords:
                continue
            if not self.canvas_mgr.is_point_in_polygon(cx, cy, coords):
                continue

            in_speed_zone = True
            prev_zone = self.speed_est.get_zone(tid)
            self.speed_est.set_zone(tid, area_name)

            # Lần đầu vào A hoặc B → bắt đầu đo
            if not self.speed_est.is_measuring(tid):
                self.speed_est.start_measuring(tid, cx, cy)
                break

            # Đang đo + vào zone còn lại → transition → tính tốc độ
            if self.speed_est.is_transition(tid, area_name):
                speed = self.speed_est.compute_speed(tid, cx, cy)
                # Sau khi tính xong, bắt đầo đo lại từ zone mới này
                self.speed_est.start_measuring(tid, cx, cy)
            break

        # Tick nếu đang đo (dù có trong zone hay không)
        if self.speed_est.is_measuring(tid) and not in_speed_zone:
            self.speed_est.tick(tid, fps)

        return speed

    # ===================================================================
    # PLATE & DATALOG
    # ===================================================================

    def _save_plate(self, frame, category, tid, x1, y1, x2, y2) -> str:
        """Cắt và lưu ảnh biển số từ vùng xe (giống logic code cũ).

        Mở rộng bounding box xe thêm 50px mỗi bên (giới hạn khung hình),
        chạy plat_license.pt trên crop đó, nếu detect class '.' thì crop tiếp.
        """
        h, w = frame.shape[:2]
        PAD = 50

        cx1 = max(0, x1 - PAD)
        cy1 = max(0, y1 - PAD)
        cx2 = min(w, x2 + PAD)
        cy2 = min(h, y2 + PAD)

        cropped = frame[cy1:cy2, cx1:cx2]
        if cropped.size == 0:
            return ""

        img, found = self.plate_detector.detect_and_crop(cropped)
        if found and img is not None:
            ts = get_current_time()
            plate_path = build_plate_path(STATIC_BASE, category, tid, ts)
            cv2.imwrite(plate_path, img)
            return build_plate_path_html(category, ts, tid)

        return ""

    def _save_datalog(self, tid, ts, plate_path, speed, vtype, vehicle, category, suffix):
        """Lưu vi phạm vào datalog.db.

        Args:
            category: tên thư mục, ví dụ "Helmet", "Overspeed", "Wrong Direction"
            suffix: suffix của file ảnh, ví dụ "no-helmet_", "overspeed_", "_"
        """
        html_plate = plate_path if plate_path else "Không phát hiện"
        photo_html = build_violation_path_html(category, tid, ts, suffix)
        with self._conn_data:
            self._conn_data.execute(
                "INSERT INTO datalog (track_id, date, plat_license, speed, max_speed, "
                "violence_category, vehicle, location, open_photo) VALUES (?,?,?,?,?,?,?,?,?)",
                (str(tid), ts, html_plate, str(speed), str(self.cfg.max_speed),
                 vtype, vehicle, self.cfg.location, photo_html),
            )

    # ===================================================================
    # THREAD HELPERS
    # ===================================================================

    def _thread_helmet(self, q: Queue, frame: np.ndarray, tid: int):
        try:
            img, status = self.helmet_detector.detect(frame)
            q.put((img, tid, status))
        except Exception as e:
            print(f"[HELMET ERROR] {e}")
            q.put((None, tid, ""))

    def _thread_seatbelt(self, q: Queue, frame: np.ndarray, tid: int):
        try:
            img, status = self.seatbelt_detector.detect(frame)
            q.put((img, tid, status))
        except Exception as e:
            print(f"[SEATBELT ERROR] {e}")
            q.put((None, tid, ""))

    # ===================================================================
    # CLEANUP
    # ===================================================================

    def _cleanup(self, active_ids: set):
        """Dọn dẹp buffer khi quá lớn."""
        self.dir_analyzer.cleanup()
        self.speed_est.cleanup()
        self.violation_detector.cleanup()

        max_buf = 20
        if len(self._helm_ids) > max_buf:
            self._helm_ids = self._helm_ids[-max_buf:]
        if len(self._seatbelt_ids) > max_buf:
            self._seatbelt_ids = self._seatbelt_ids[-max_buf:]
        if len(self._overspeed_ids) > max_buf:
            self._overspeed_ids = self._overspeed_ids[-max_buf:]
        if len(self._overtaking_ids) > max_buf:
            self._overtaking_ids = self._overtaking_ids[-max_buf:]
        if len(self._wrong_dir_ids) > max_buf:
            self._wrong_dir_ids = self._wrong_dir_ids[-max_buf:]
        if len(self._helm_flags) > max_buf:
            self._helm_flags = self._helm_flags[-max_buf:]
        if len(self._seatbelt_flags) > max_buf:
            self._seatbelt_flags = self._seatbelt_flags[-max_buf:]

    # ===================================================================
    # CLOSE
    # ===================================================================

    def close(self):
        if self.camera:
            self.camera.release()
        self._conn.close()
        self._conn_data.close()
        self._conn_ip.close()
        self.root.destroy()
