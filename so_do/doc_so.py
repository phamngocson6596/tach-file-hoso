"""Đọc số viết bằng chữ tiếng Việt thành số: "Hai mươi bảy nghìn ba trăm bốn mươi mốt" -> 27341.

Dùng để kiểm tra chéo diện tích ghi bằng số với diện tích ghi bằng chữ trên giấy chứng nhận.
Chịu được các cách viết khác nhau: lẻ/linh, tư/bốn, nghìn/ngàn, mốt, lăm/nhăm, tỷ/tỉ, phẩy.
"""
from __future__ import annotations

import difflib
import re
import unicodedata
from decimal import Decimal

_SO = {"không": 0, "một": 1, "mốt": 1, "hai": 2, "ba": 3, "bốn": 4, "tư": 4, "năm": 5, "lăm": 5, "nhăm": 5,
       "sáu": 6, "bảy": 7, "bẩy": 7, "tám": 8, "chín": 9}
_HANG = {"nghìn": 1000, "ngàn": 1000, "triệu": 1_000_000}
_BO_QUA = {"lẻ", "linh", "và"}
_DUNG = {"mét", "m2", "m²", "đồng", "vuông"}


_TU_BIET = list(_SO) + ["mười", "mươi", "trăm", "phẩy", "tỷ", "tỉ"] + list(_HANG) + list(_BO_QUA) + list(_DUNG)


def _sua_loi_ocr(t: str) -> str:
    """Từ chỉ số bị OCR đọc sai dấu ("trắm" -> "trăm"): sửa về từ gần nhất nếu rất giống."""
    if t in _TU_BIET or t.isdigit():
        return t
    gan = difflib.get_close_matches(t, _TU_BIET, n=1, cutoff=0.75)
    return gan[0] if gan and abs(len(gan[0]) - len(t)) <= 1 else t


def _tach_tu(chu: str) -> list[str]:
    chu = unicodedata.normalize("NFC", chu).lower()
    return [_sua_loi_ocr(t) for t in re.findall(r"[^\W\d_]+|\d+", chu)]


def _doc_phan_nguyen(tu: list[str]) -> int | None:
    tong, nhom, cho = 0, 0, None
    for t in tu:
        if t in _SO:
            if cho is not None:  # hai chữ số liền nhau mà không có hàng -> không phải cách đọc số
                return None
            cho = _SO[t]
        elif t == "mười":
            nhom += 10
        elif t == "mươi":
            nhom += (cho if cho is not None else 1) * 10
            cho = None
        elif t == "trăm":
            nhom += (cho if cho is not None else 1) * 100
            cho = None
        elif t in _HANG:
            tong += (nhom + (cho or 0)) * _HANG[t]
            nhom, cho = 0, None
        elif t in ("tỷ", "tỉ"):
            tong = (tong + nhom + (cho or 0)) * 1_000_000_000
            nhom, cho = 0, None
        elif t in _BO_QUA:
            continue
        else:
            return None
    return tong + nhom + (cho or 0)


def chu_thanh_so(chu: str) -> Decimal | None:
    """Trả về số, hoặc None nếu không đọc được (gặp từ lạ, hoặc chữ rỗng)."""
    tu = []
    for t in _tach_tu(chu):
        if t in _DUNG:
            break
        tu.append(t)
    if not tu:
        return None
    if "phẩy" in tu:
        k = tu.index("phẩy")
        nguyen, le = tu[:k], tu[k + 1:]
        so_nguyen = _doc_phan_nguyen(nguyen)
        if so_nguyen is None or not le:
            return None
        if all(t in _SO for t in le):  # "phẩy không năm" -> .05
            phan_le = "".join(str(_SO[t]) for t in le)
        else:  # "phẩy hai mươi lăm" -> .25
            n = _doc_phan_nguyen(le)
            if n is None:
                return None
            phan_le = str(n)
        return Decimal(f"{so_nguyen}.{phan_le}")
    n = _doc_phan_nguyen(tu)
    return None if n is None else Decimal(n)


def so_viet(chu: str) -> Decimal | None:
    """Đọc số viết theo kiểu Việt Nam: "27.341,5" hoặc "27341,5" -> 27341.5."""
    m = re.search(r"\d[\d.\s]*(?:,\d+)?", chu)
    if not m:
        return None
    s = re.sub(r"[.\s]", "", m.group(0)).replace(",", ".")
    try:
        return Decimal(s)
    except Exception:
        return None
