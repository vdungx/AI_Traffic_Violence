"""OCR utility - Doc bien so xe bang EasyOCR.

Luu y: Hien khong duoc su dung truc tiep trong main flow.
OCR duoc thuc hien qua JavaScript phia client hoac trong violation detection.
"""

import cv2
import easyocr


class OCRProcessor:
    """Trình xử lý OCR đọc văn bản từ hình ảnh."""

    def __init__(self, languages: list[str] = None):
        if languages is None:
            languages = ["en"]
        self.reader = easyocr.Reader(languages)

    def read_text(self, image_path: str) -> list[str]:
        """Đọc văn bản từ file ảnh, trả về danh sách chuỗi."""
        image = cv2.imread(image_path)
        if image is None:
            raise ValueError(f"Không tìm thấy hình ảnh: {image_path}")
        result = self.reader.readtext(image)
        return [text for (_, text, _) in result]

    def process_image(self, image_path: str):
        """Xử lý ảnh và trả về văn bản tìm thấy."""
        texts = self.read_text(image_path)
        if not texts:
            return ""
        if len(texts) == 1:
            return texts[0]
        return texts


def process_image(image_path: str):
    """Hàm tiện ích xử lý ảnh OCR."""
    return OCRProcessor().process_image(image_path)
