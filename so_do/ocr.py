"""Đọc chữ từng trang PDF / ảnh bằng engine OCR của tach_van_ban (Tesseract hoặc Screen AI), kèm mã vạch/QR."""
from __future__ import annotations

import hashlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import tach_van_ban as tvb  # noqa: E402
from tach_van_ban import pymupdf  # noqa: E402
from PIL import Image  # noqa: E402

# Kết quả thử trên sổ đỏ thật: Screen AI tốt nhất với ảnh màu; Tesseract tốt hơn chút với kênh đỏ
# (nền hồng và dấu đỏ gần như biến mất). Cùng 200 dpi; 300 dpi không cải thiện mà chậm gấp đôi.
_KIEU_ANH = {"screenai": "mau", "tesseract": "do"}
DPI = 200


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for khoi in iter(lambda: f.read(1 << 20), b""):
            h.update(khoi)
    return h.hexdigest()


def _anh(page, dpi: int, kieu: str) -> Image.Image:
    pix = page.get_pixmap(dpi=dpi, colorspace=pymupdf.csRGB, alpha=False)
    rgb = Image.frombuffer("RGB", (pix.width, pix.height), pix.samples, "raw", "RGB", pix.stride, 1)
    return rgb if kieu == "mau" else rgb.split()[0]


def doc_tep(p: Path, engine: str = "screenai", log=print) -> tuple[list[str], list[str]]:
    """(chữ từng trang, các mã vạch/QR đọc được). PDF có lớp chữ thì dùng luôn lớp chữ."""
    cfg = dict(tvb.cfg_mac_dinh(), engine=engine)
    ok, tb = tvb.kiem_tra_ocr(cfg)
    if not ok:
        raise RuntimeError(tb)
    doc = pymupdf.open(str(p))  # PyMuPDF mở được cả ảnh JPG/PNG như một tài liệu 1 trang
    cac_trang, ma = [], []
    for i, page in enumerate(doc, start=1):
        lop_chu = page.get_text("text") if doc.is_pdf else ""
        if sum(c.isalpha() for c in lop_chu) >= 50:
            cac_trang.append(lop_chu)
        else:
            anh = _anh(page, DPI, _KIEU_ANH.get(engine, "mau"))
            chu, _ = tvb.ocr_anh(anh, cfg)
            cac_trang.append(chu)
        ma.extend(_ma_vach(page))
        log(f"  trang {i}/{doc.page_count}")
    return cac_trang, ma


def _ma_vach(page) -> list[str]:
    try:
        import zxingcpp
    except ImportError:
        return []
    return [r.text for r in zxingcpp.read_barcodes(_anh(page, 300, "mau"))]


def anh_thu_nho(p: Path, dpi: int = 60) -> list[bytes]:
    """Ảnh PNG nhỏ từng trang, để đặt cạnh dữ liệu trên trang duyệt."""
    doc = pymupdf.open(str(p))
    return [page.get_pixmap(dpi=dpi).tobytes("png") for page in doc]
