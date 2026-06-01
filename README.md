# 🚦 AI Traffic Violence Detection System

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue)](https://www.python.org/)
[![YOLOv8](https://img.shields.io/badge/YOLOv8-Ultralytics-green)](https://github.com/ultralytics/ultralytics)
[![OpenCV](https://img.shields.io/badge/OpenCV-4.10-red)](https://opencv.org/)

Hệ thống phát hiện vi phạm giao thông thông minh sử dụng AI, xử lý real-time từ camera IP/RTSP, hỗ trợ cả giao diện Desktop và Web Dashboard.

> **Đồ án tốt nghiệp - AI Traffic Violence Detection**
>
> Phát hiện các hành vi vi phạm: không đội mũ bảo hiểm, không thắt dây an toàn, quá tốc độ, đi ngược chiều, vượt ẩu.

---

## 📋 Mục lục

- [Tính năng](#-tính-năng)
- [Kiến trúc hệ thống](#-kiến-trúc-hệ-thống)
- [Công nghệ sử dụng](#-công-nghệ-sử-dụng)
- [Cài đặt](#-cài-đặt)
- [Hướng dẫn sử dụng](#-hướng-dẫn-sử-dụng)
- [Cấu hình](#-cấu-hình)
- [API & Web Dashboard](#-api--web-dashboard)
- [Pipeline xử lý](#-pipeline-xử-lý)
- [Cấu trúc thư mục](#-cấu-trúc-thư-mục)
- [Đóng góp](#-đóng-góp)
- [Giấy phép](#-giấy-phép)

---

## ✨ Tính năng

### 🚗 Phát hiện phương tiện
- Phát hiện 5 loại phương tiện: **xe máy, ô tô, xe buýt, xe tải, xe đạp**
- Sử dụng **YOLOv8** pre-trained trên COCO dataset
- Hỗ trợ nhiều model size: nano → super (yolov8n → yolov8x)

### 📍 Theo dõi đối tượng (Tracking)
- Theo dõi từng phương tiện với **Track ID** duy nhất
- Lưu lịch sử di chuyển (30 frame gần nhất)
- Phân tích hướng di chuyển
- Ước tính tốc độ (A → B zone)

### 🛑 Phát hiện vi phạm

| Vi phạm | Mô tả |
|---------|-------|
| 🪖 **Không mũ bảo hiểm** | Phát hiện người đi xe máy không đội mũ bảo hiểm |
| 🔗 **Không thắt dây an toàn** | Phát hiện tài xế ô tô không thắt dây an toàn |
| ⚡ **Quá tốc độ** | Phát hiện phương tiện vượt quá tốc độ cho phép |
| 🔄 **Đi ngược chiều** | Phát hiện phương tiện di chuyển sai làn/ngược chiều |
| 🏎️ **Vượt ẩu** | Phát hiện hành vi vượt xe không an toàn |

### 🪪 Phát hiện biển số
- Phát hiện và crop biển số xe tự động
- OCR tích hợp (EasyOCR) để đọc ký tự biển số

### 🖥️ Giao diện
- **Desktop GUI**: Tkinter canvas real-time, vẽ khu vực/đường thẳng trực tiếp trên video
- **Web Dashboard**: Flask web app xem dữ liệu, lọc theo ngày, xóa vi phạm
- Hiển thị bounding box, track path, cảnh báo vi phạm trên video

### 💾 Lưu trữ
- Lưu ảnh vi phạm (JPEG) kèm thông tin thời gian, loại vi phạm
- Lưu ảnh biển số riêng biệt
- SQLite database: cấu hình, dữ liệu vi phạm, tài khoản đăng nhập

---

## 🏗️ Kiến trúc hệ thống

```
┌─────────────────────────────────────────────────────────────┐
│                        INPUT                                │
│              Camera IP (RTSP) / File video                  │
│                    OpenCV → Resize 640×640                  │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                   VEHICLE DETECTION                         │
│              YOLOv8x (COCO pretrained)                      │
│         5 classes: motorcycle, car, bus, truck, bike        │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                      TRACKING                               │
│            Ultralytics tracker + TrackManager               │
│            + DirectionAnalyzer + SpeedEstimator             │
└────────────┬──────────────────────────────┬─────────────────┘
             │                              │
             ▼                              ▼
┌─────────────────────────┐  ┌───────────────────────────────┐
│   VIOLATION DETECTION   │  │        LICENSE PLATE          │
│  • Helmet detection     │  │  • plat_license.pt detect     │
│  • Seatbelt detection   │  │  • Crop ảnh biển số           │
│  • Wrong direction      │  │  • EasyOCR (optional)         │
│  • Overspeed            │  │                               │
└────────────┬────────────┘  └──────────────┬────────────────┘
             │                              │
             └──────────────┬───────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                        STORAGE                              │
│    SQLite (datalog.db / login.db / config.db)               │
│    + Ảnh vi phạm / biển số (JPEG)                          │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                       DISPLAY                               │
│   Desktop GUI (Tkinter): canvas real-time + ConfigDialog    │
│   Web Dashboard (Flask): /dashboard, /photo, filter/delete  │
└─────────────────────────────────────────────────────────────┘
```

---

## 🛠️ Công nghệ sử dụng

| Công nghệ | Phiên bản | Mục đích |
|-----------|-----------|----------|
| **Python** | 3.10+ | Ngôn ngữ lập trình |
| **Ultralytics YOLOv8** | 8.2.74 | Phát hiện & theo dõi đối tượng |
| **OpenCV** | 4.10.0 | Xử lý ảnh & video |
| **PyTorch** | 2.4.1 | Deep learning framework |
| **Tkinter** | - | Giao diện Desktop |
| **Flask** | 3.0.3 | Web Dashboard |
| **SQLite3** | - | Cơ sở dữ liệu |
| **EasyOCR** | - | Đọc biển số xe |
| **NumPy** | 1.26.4 | Xử lý ma trận |
| **Pillow** | 10.3.0 | Xử lý ảnh |
| **Matplotlib** | 3.9.2 | Vẽ biểu đồ |

---

## 📦 Cài đặt

### Yêu cầu
- Python 3.10+
- CUDA 12.1 (khuyến nghị cho GPU)
- Webcam hoặc Camera IP/RTSP

### Các bước cài đặt

```bash
# 1. Clone repository
git clone https://github.com/your-username/ai-traffic-violence.git
cd ai-traffic-violence

# 2. Tạo virtual environment (khuyến nghị)
python -m venv venv
# Windows
venv\Scripts\activate
# Linux/Mac
source venv/bin/activate

# 3. Cài đặt dependencies
pip install -r requirements.txt

# 4. Tải models (đặt vào thư mục models/)
# YOLO models: https://github.com/ultralytics/assets/releases
# Custom models (đặt vào thư mục gốc models/):
#   - helmet_9.pt        (phát hiện mũ bảo hiểm)
#   - seat_belt_5.pt     (phát hiện dây an toàn)
#   - plat_license.pt    (phát hiện biển số)

# 5. Khởi chạy ứng dụng Desktop
python main.py

# 6. (Tùy chọn) Khởi chạy Web Dashboard riêng
python server.py
```

### File models cần có

```
models/
├── yolo/
│   ├── yolov8n.pt    # Nano - nhanh nhất
│   ├── yolov8s.pt    # Small
│   ├── yolov8m.pt    # Medium (cân bằng)
│   ├── yolov8l.pt    # Large
│   └── yolov8x.pt    # Super - chính xác nhất (mặc định)
├── helmet_9.pt           # Phát hiện mũ bảo hiểm
├── seat_belt_5.pt        # Phát hiện dây an toàn
├── plat_license.pt       # Phát hiện biển số
└── license_plate_detector.pt
```

---

## 🎮 Hướng dẫn sử dụng

### Ứng dụng Desktop

1. **Kết nối Camera**: Nhập IP camera (RTSP) hoặc đường dẫn file video, nhấn "Kết nối Camera"
2. **Bật AI**: Nhấn "Bật/Tắt AI (YOLO)" để bắt đầu phát hiện
3. **Vẽ khu vực**: Nhấn "Thêm Khu vực" để vùng giám sát (POINT_A, POINT_B, LEFT, RIGHT)
4. **Vẽ đường**: Nhấn "Vẽ Đường" để đo khoảng cách
5. **Cấu hình**: Nhấn "Cấu hình" để điều chỉnh tham số

### Khu vực đặc biệt

| Tên khu vực | Chức năng |
|-------------|-----------|
| `POINT_A` | Điểm đầu đo tốc độ |
| `POINT_B` | Điểm cuối đo tốc độ |
| `LEFT` | Giám sát đi ngược chiều (trái) |
| `RIGHT` | Giám sát đi ngược chiều (phải) |

### Web Dashboard

- Truy cập: `http://localhost:5000`
- Đăng nhập để xem danh sách vi phạm
- Lọc theo ngày, xem ảnh vi phạm, xóa dữ liệu

---

## ⚙️ Cấu hình

Cấu hình được lưu trong `database/configuration.db`, có thể điều chỉnh qua dialog Cấu hình trong ứng dụng:

| Tham số | Mô tả | Mặc định |
|---------|-------|----------|
| `calibration_factor` | Hệ số hiệu chuẩn tốc độ | 2.0 |
| `max_speed` | Tốc độ tối đa (km/h) | 80.0 |
| `width_in_pixel` | Chiều rộng khu vực (pixel) | 900.0 |
| `width_in_meter` | Chiều rộng thực tế (mét) | 7.0 |
| `actual_time` | Thời gian thực (giây) | 5.0 |
| `yolo_time` | Thời gian xử lý YOLO | 15.0 |
| `location` | Địa điểm triển khai | Indonesia |
| `Model` | Model YOLO sử dụng | yolov8x.pt |

---

## 🌐 API & Web Dashboard

### Routes chính

| Route | Method | Mô tả |
|-------|--------|-------|
| `/` | GET | Trang đăng nhập |
| `/login` | POST | Xác thực đăng nhập |
| `/dashboard` | GET | Dashboard xem vi phạm |
| `/photo/<id>` | GET | Xem chi tiết vi phạm |
| `/delete/<id>` | DELETE | Xóa vi phạm |
| `/logout` | POST | Đăng xuất |
| `/change-user` | GET/POST | Đổi mật khẩu |

---

## 🔄 Pipeline xử lý

### Luồng xử lý chính (main loop trong `src/gui/app.py`)

1. **Đọc frame** từ camera/file
2. **Resize** về 1600×900
3. **YOLO Detection**: Phát hiện phương tiện + tracking
4. **Track Manager**: Cập nhật lịch sử vị trí
5. **Direction Analyzer**: Phân tích hướng di chuyển
6. **Speed Estimator**: Tính tốc độ A→B
7. **Violation Detection**:
   - Xe máy → Kiểm tra mũ bảo hiểm
   - Ô tô → Kiểm tra dây an toàn
   - Mọi xe → Quá tốc độ, đi ngược chiều
8. **License Plate**: Crop biển số xe
9. **Save**: Lưu ảnh + database
10. **Display**: Vẽ lên canvas + web

---

## 📁 Cấu trúc thư mục

```
ai_traffic_violence/
├── main.py                      # Entry point - ứng dụng Desktop
├── server.py                    # Flask Web Dashboard
├── ocr_library.py               # EasyOCR utility
├── draw_pipeline.py             # Vẽ pipeline diagram
├── create_slides.py             # Tạo slide thuyết trình
├── test_seatbelt.py             # Test seatbelt detection
├── reset.py / resetdb.py        # Reset dữ liệu
├── requirements.txt             # Dependencies
├── icon.ico                     # App icon
│
├── src/
│   ├── __init__.py
│   ├── config.py                # Quản lý cấu hình
│   ├── database.py              # SQLite layer
│   │
│   ├── detection/
│   │   ├── __init__.py
│   │   ├── detector.py          # YOLO model wrappers
│   │   ├── tracker.py           # TrackManager, DirectionAnalyzer, SpeedEstimator
│   │   └── violation.py         # ViolationDetector orchestrator
│   │
│   ├── gui/
│   │   ├── __init__.py
│   │   ├── app.py               # VideoApp - GUI chính
│   │   ├── canvas.py            # Canvas drawing helpers
│   │   └── widgets.py           # ConfigDialog, AreaDrawer, LineDrawer
│   │
│   └── utils/
│       ├── __init__.py
│       ├── image.py             # File path helpers
│       └── speed.py             # Speed calculation
│
├── models/
│   ├── yolo/
│   │   ├── yolov8n.pt
│   │   ├── yolov8s.pt
│   │   ├── yolov8m.pt
│   │   ├── yolov8l.pt
│   │   └── yolov8x.pt
│   ├── helmet_9.pt
│   ├── seat_belt_5.pt
│   ├── plat_license.pt
│   └── license_plate_detector.pt
│
├── database/
│   ├── configuration.db         # Config + areas + lines
│   ├── datalog.db               # Dữ liệu vi phạm
│   ├── login.db                 # Tài khoản
│   └── static/                  # Ảnh vi phạm & biển số
│       ├── Helmet/
│       ├── Seatbelt/
│       ├── Overspeed/
│       ├── Wrong Direction/
│       └── plat_number_*/
│
├── templates/                   # Flask HTML templates
│   ├── login.html
│   ├── dashboard.html
│   ├── photo.html
│   └── change_user.html
│
└── docs/
    └── pipeline_diagram.png     # Sơ đồ pipeline
```

---

## 🤝 Đóng góp

Mọi đóng góp đều được hoan nghênh! Vui lòng:

1. Fork repository
2. Tạo branch feature mới (`git checkout -b feature/AmazingFeature`)
3. Commit changes (`git commit -m 'Add some AmazingFeature'`)
4. Push lên branch (`git push origin feature/AmazingFeature`)
5. Mở Pull Request

---

## 📄 Giấy phép

Dự án này được phát triển cho mục đích **Đồ án tốt nghiệp** và nghiên cứu học thuật.

---

## 📬 Liên hệ

**Tác giả:** Trần Văn Dũng

---

<p align="center">
  <b>AI Traffic Violence Detection</b><br>
  Đồ án tốt nghiệp - Phát hiện vi phạm giao thông thông minh
</p>
