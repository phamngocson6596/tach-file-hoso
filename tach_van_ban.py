#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tach_van_ban.py  —  Tách VĂN BẢN CÔNG CHỨNG ra khỏi file PDF scan gộp chung với HỒ SƠ LƯU.

Chạy:
    python tach_van_ban.py  <thư mục PDF scan>  <thư mục kết quả>
Cắt lại theo bảng đã sửa tay (không OCR lại):
    python tach_van_ban.py  <thư mục PDF scan>  <thư mục kết quả>  --theo-bang <thư mục kết quả>/bao_cao.xlsx

Xem HUONG_DAN.md để biết chi tiết. Mọi xử lý đều chạy trên máy, không gửi dữ liệu ra ngoài.
"""
from __future__ import annotations

import os
os.environ.setdefault("OMP_THREAD_LIMIT", "1")  # tránh Tesseract tự mở nhiều luồng khi đã chạy song song

import argparse
import csv
import multiprocessing
import hashlib
import html
import json
import re
import shutil
import sys
import time
import traceback
import unicodedata
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

try:
    import pymupdf
except ImportError:  # PyMuPDF bản cũ
    import fitz as pymupdf
from PIL import Image

PHIEN_BAN = "0.3.0"

# =====================================================================
# 1. CHUẨN HOÁ CHỮ & TỪ KHOÁ
#    Toàn bộ so khớp làm trên chữ đã bỏ dấu, viết hoa -> OCR sai dấu vẫn khớp.
#    Muốn thêm/bớt loại giấy tờ: sửa các danh sách bên dưới.
# =====================================================================

def bo_dau(s: str) -> str:
    s = s.replace("đ", "d").replace("Đ", "D").replace("Ð", "D").replace("ð", "d")
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    s = re.sub(r"[^A-Z0-9]+", " ", s.upper())
    return s.strip()


_NHAM = {"O": "[O0Q]", "I": "[I1L]", "L": "[L1I]", "S": "[S5]", "B": "[B8]"}


def mau(cum: str) -> re.Pattern:
    """'LOI CHUNG' -> regex chịu lỗi OCR hay gặp (O/0, I/1/L, hai chữ bị dính nhau)."""
    tu = ["".join(_NHAM.get(c, c) for c in w) for w in cum.split()]
    return re.compile(r"\b" + r" ?".join(tu) + r"\b")


def ds_mau(ds):
    return [(c, mau(c)) for c in ds]


# Tiêu đề VĂN BẢN CÔNG CHỨNG (dòng viết hoa ở đầu trang, bắt đầu bằng ...)
TIEU_DE_VAN_BAN = ds_mau([
    "HOP DONG", "PHU LUC HOP DONG", "PHU LUC", "VAN BAN", "GIAY UY QUYEN", "DI CHUC",
    "THOA THUAN", "BAN THOA THUAN", "CAM KET", "BAN CAM KET",
])

# Tiêu đề GIẤY TỜ TRONG HỒ SƠ (dòng viết hoa ở đầu trang, bắt đầu bằng ...)
TIEU_DE_HO_SO = ds_mau([
    "PHIEU YEU CAU", "PHIEU THU", "PHIEU CHUYEN", "BIEN LAI", "HOA DON",
    "GIAY CHUNG NHAN", "GIAY XAC NHAN", "GIAY DE NGHI", "GIAY KHAI SINH", "GIAY CHUNG TU",
    "GIAY PHEP", "GIAY BAO TU", "GIAY DANG KY", "TRICH LUC", "TRICH SAO", "TRICH DO",
    "CAN CUOC", "CHUNG MINH NHAN DAN", "HO CHIEU", "PASSPORT", "SO HO KHAU", "SO DANG KY",
    "XAC NHAN THONG TIN", "THONG TIN VE CU TRU", "THONG BAO", "TO KHAI", "TO TRINH",
    "DON ", "BIEN BAN", "QUYET DINH", "BAN AN", "SO DO", "BAN VE", "BAN SAO", "SAO Y",
    "DANH SACH", "BAO CAO", "CONG VAN",
])

# Dấu hiệu HỒ SƠ ở bất kỳ đâu trên trang (đủ mạnh để loại trang khỏi văn bản)
DAU_HIEU_HO_SO = ds_mau([
    "CHUNG THUC BAN SAO DUNG VOI BAN CHINH", "BAN SAO DUNG VOI BAN CHINH", "SAO Y BAN CHINH",
    "CITIZEN IDENTITY", "IDENTITY CARD", "SOCIALIST REPUBLIC", "PERSONAL IDENTIFICATION",
])

M_LOI_CHUNG = mau("LOI CHUNG")
M_QUOC_HIEU = [mau("CONG HOA XA HOI CHU NGHIA"), mau("DOC LAP TU DO HANH PHUC")]
M_SO_CONG_CHUNG = [mau("SO CONG CHUNG"), mau("QUYEN SO"), re.compile(r"\bTP ?/ ?CC\b")]
M_CCV = mau("CONG CHUNG VIEN")
M_DIEU = re.compile(r"\bD[I1L]EU ?\d{1,2}\b")
M_KY = [
    re.compile(r"\bBEN ?(A|B|C|BAN|MUA|CHO|NHAN|THUE|VAY|TANG|DUOC|UY|THE|GOP|CHUYEN)\b"),
    mau("NGUOI LAP DI CHUC"), mau("NGUOI UY QUYEN"), mau("NGUOI DUOC UY QUYEN"),
    re.compile(r"\bKY\b.{0,12}\bHO TEN\b"), mau("DIEM CHI"), mau("NHUNG NGUOI THUA KE"),
]

MUC_BO_QUA_OCR = 0.0003     # tỉ lệ mực dưới mức này thì không OCR
SO_DONG_DAU_TRANG = 15     # số dòng đầu trang được coi là "phần tiêu đề"
CHU_NHIEU = 700            # trang dày chữ -> coi là thân văn bản (nếu không có dấu hiệu hồ sơ)
CHU_IT = 150               # dưới mức này -> trang ít chữ (ảnh, CCCD, sơ đồ...)

NHAN_TEN = {
    "MD": "Mở đầu", "TH": "Thân", "LC": "Lời chứng", "HS": "Hồ sơ",
    "TT": "Trang trắng", "KR": "Không rõ",
}


def ty_le_hoa(dong: str) -> float:
    chu = [c for c in dong if c.isalpha()]
    if len(chu) < 4:
        return 0.0
    return sum(c.isupper() for c in chu) / len(chu)


def khop(ds, s):
    for ten, m in ds:
        if m.search(s):
            return ten
    return None


def khop_dau(ds, s):
    for ten, m in ds:
        if m.match(s):
            return ten
    return None


def phan_tich_trang(text: str, muc_muc: float, nguong_trang: float) -> dict:
    """Gắn nhãn 1 trang. Trả về dict: nhan, manh, ly_do, quoc_hieu, co_ket, dieu, so_chu."""
    dong = [d.strip() for d in text.splitlines() if d.strip()]
    dong_bd = [bo_dau(d) for d in dong]
    toan = " ".join(dong_bd)
    so_chu = sum(c.isalpha() for c in text)
    dieu = len(M_DIEU.findall(toan))
    dau = list(zip(dong[:SO_DONG_DAU_TRANG], dong_bd[:SO_DONG_DAU_TRANG]))
    quoc_hieu = any(m.search(" ".join(b for _, b in dau)) for m in M_QUOC_HIEU)

    # dấu hiệu kết thúc lời chứng: số công chứng/quyển số, hoặc dòng chữ ký "CÔNG CHỨNG VIÊN"
    co_ket = any(m.search(toan) for m in M_SO_CONG_CHUNG) or any(
        M_CCV.search(b) and not M_LOI_CHUNG.search(b) and len(b) <= 30 and ty_le_hoa(d) >= 0.7
        for d, b in zip(dong, dong_bd)
    )
    kq = dict(nhan="KR", manh=False, ly_do="", quoc_hieu=quoc_hieu, co_ket=co_ket,
              dieu=dieu, so_chu=so_chu)

    def gan(nhan, ly_do, manh=False):
        kq.update(nhan=nhan, ly_do=ly_do, manh=manh)
        return kq

    if so_chu < 20:
        if muc_muc < nguong_trang:
            return gan("TT", "trang trắng")
        return gan("HS", "không đọc được chữ (ảnh/hình?)")
    k = khop(DAU_HIEU_HO_SO, toan)
    if k:
        return gan("HS", f"có '{k}'", True)
    for d, b in zip(dong, dong_bd):
        if M_LOI_CHUNG.search(b) and ty_le_hoa(d) >= 0.6:
            return gan("LC", "có tiêu đề LỜI CHỨNG")
    # tiêu đề: dòng viết hoa đầu tiên khớp danh sách nào thì theo danh sách đó
    for d, b in dau:
        if ty_le_hoa(d) < 0.7:
            continue
        k = khop_dau(TIEU_DE_HO_SO, b)
        if k:
            return gan("HS", f"tiêu đề '{k.strip()}…'", True)
        k = khop_dau(TIEU_DE_VAN_BAN, b)
        if k:
            return gan("MD", f"tiêu đề '{d[:60]}'")
    if dieu >= 1:
        return gan("TH", f"có {dieu} 'Điều …'")
    if so_chu >= CHU_NHIEU:
        return gan("TH", "nhiều chữ")
    if any(m.search(toan) for m in M_KY):
        return gan("TH", "trang ký tên các bên")
    if so_chu < CHU_IT:
        return gan("HS", "ít chữ (ảnh/giấy tờ?)")
    return gan("KR", "không có dấu hiệu rõ")


# =====================================================================
# 2. GHÉP TRANG THÀNH VĂN BẢN
# =====================================================================

def chia_van_ban(trang: list[dict], can_quoc_hieu: bool = True) -> tuple[list[dict], list[str]]:
    """Trả về (danh sách văn bản tìm được, cảnh báo cấp file).
    Mỗi văn bản: dict(trang=[chỉ số 0-based], co_md, co_lc, quoc_hieu, canh_bao=[])."""
    n = len(trang)
    doan, da_dung = [], set()
    hien = None

    def moi(ds, co_md, qh, canh_bao=None):
        return dict(trang=list(ds), co_md=co_md, co_lc=False, quoc_hieu=qh, canh_bao=canh_bao or [])

    def chot(d):
        doan.append(d)
        da_dung.update(d["trang"])

    def dong_loi_chung(d, i):
        d["trang"].append(i)
        d["co_lc"] = True
        if trang[i]["co_ket"]:
            return i + 1
        # lời chứng tràn sang trang sau: lấy thêm tối đa 2 trang, tới trang có số công chứng/chữ ký CCV
        tam, k = [], i + 1
        while k < n and sum(trang[c]["nhan"] != "TT" for c in tam) < 2:
            t = trang[k]
            if t["nhan"] == "MD" or (t["nhan"] == "HS" and t["manh"]):
                break
            tam.append(k)
            if t["co_ket"] and t["nhan"] != "TT":
                for c in tam:
                    if trang[c]["nhan"] != "TT":
                        d["trang"].append(c)
                        trang[c].update(nhan="LC", ly_do="phần tiếp của lời chứng")
                return k + 1
            k += 1
        d["canh_bao"].append(f"tr.{i+1}: không thấy số công chứng/chữ ký CCV sau lời chứng")
        return i + 1

    i = 0
    while i < n:
        t = trang[i]
        nh = t["nhan"]
        if nh == "MD":
            if hien is not None:
                hien["canh_bao"].append(f"tr.{i+1}: gặp tiêu đề mới khi văn bản trước chưa có lời chứng")
                chot(hien)
            hien = moi([i], True, t["quoc_hieu"])
            if not t["quoc_hieu"] and can_quoc_hieu:
                hien["canh_bao"].append(f"tr.{i+1}: tiêu đề không kèm Quốc hiệu")
            i += 1
            continue
        if nh == "LC":
            if hien is None:
                j = i - 1
                while j >= 0 and j not in da_dung and trang[j]["nhan"] in ("TH", "KR", "TT"):
                    j -= 1
                ds = [k for k in range(j + 1, i) if trang[k]["nhan"] != "TT"]
                hien = moi(ds, False, False, [
                    f"không thấy trang tiêu đề; đoán văn bản bắt đầu từ tr.{(ds[0] if ds else i)+1}"])
            i = dong_loi_chung(hien, i)
            chot(hien)
            hien = None
            continue
        if hien is not None:
            if nh in ("TH", "KR"):
                hien["trang"].append(i)
            elif nh == "HS" and not t["manh"]:
                hien["trang"].append(i)
                hien["canh_bao"].append(f"tr.{i+1}: trang ít chữ nằm giữa văn bản (đã giữ)")
            elif nh == "HS":
                hien["canh_bao"].append(f"tr.{i+1}: giống hồ sơ ({t['ly_do']}) nằm giữa văn bản (đã bỏ)")
        i += 1
    if hien is not None:
        hien["canh_bao"].append("không tìm thấy trang LỜI CHỨNG")
        chot(hien)

    canh_bao_file = []
    ngoai = [k + 1 for k in range(n) if k not in da_dung and trang[k]["nhan"] == "TH" and trang[k]["dieu"] >= 2]
    if ngoai:
        canh_bao_file.append(f"trang có nhiều 'Điều…' nằm ngoài văn bản: {', '.join(map(str, ngoai))}")
    return doan, canh_bao_file


# ---------- Chọn VĂN BẢN CHÍNH khi 1 file có nhiều văn bản (vd hồ sơ lưu kèm bản sao HĐ cũ) ----------
M_SO_CC_SO = [
    re.compile(r"\bS[O0] C[O0]NG CHUNG(?: S[O0])? (\d{1,6})\b"),
    re.compile(r"\bC[O0]NG CHUNG S[O0] (\d{1,6})\b"),
    re.compile(r"\bS[O0] (\d{1,6}) QUYEN S[O0]\b"),
]
M_QUYEN_NAM = re.compile(r"\bQUYEN S[O0] \d{1,4} ((?:19|20)\d{2})\b")
M_NGAY_CHU = re.compile(r"\bNGAY (\d{1,2}) THANG (\d{1,2}) NAM ((?:19|20)\d{2})\b")
M_NGAY_SO = re.compile(r"\b(\d{1,2}) (\d{1,2}) ((?:19|20)\d{2})\b")
TIEN_TO_TO_CHUC = ("VAN PHONG CONG CHUNG", "PHONG CONG CHUNG", "VPCC", "PCC")


def loi_ten_to_chuc(ten: str) -> str:
    """'Văn phòng công chứng Hòa An' -> 'HOA AN' (phần riêng của tên)."""
    b = bo_dau(ten or "")
    for tt in TIEN_TO_TO_CHUC:
        if b.startswith(tt + " "):
            return b[len(tt) + 1:].strip()
    return b


def so_trong_ten(rel: str) -> set[int]:
    goc = rel.rsplit(".", 1)[0]
    return {int(x) for x in re.findall(r"\d+", goc) if len(x) <= 6}


def thong_tin_doan(d: dict, trang: list[dict], texts: list[str]) -> dict:
    """Đọc số công chứng, ngày công chứng từ trang lời chứng của 1 văn bản."""
    lc = [i for i in d["trang"] if trang[i]["nhan"] == "LC"]  # chỉ tin số/ngày/tên tổ chức ghi trong lời chứng
    t = " ".join(bo_dau(texts[i]) for i in lc)
    so = set()
    for m in M_SO_CC_SO:
        so.update(int(x) for x in m.findall(t))
    ngay = None
    m = M_NGAY_CHU.search(t) or M_NGAY_SO.search(t)
    if m:
        dd, mm, yy = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if 1 <= dd <= 31 and 1 <= mm <= 12:
            ngay = (yy, mm, dd)
    if not ngay:
        m = M_QUYEN_NAM.search(t)
        if m:
            ngay = (int(m.group(1)), 0, 0)
    return dict(so_cc=so, ngay=ngay, chu=t)


def mo_ta_doan(x: dict) -> str:
    s = []
    if x["so_cc"]:
        s.append("số CC " + "/".join(map(str, sorted(x["so_cc"]))))
    if x["ngay"]:
        y, m, d = x["ngay"]
        s.append(f"{d:02d}/{m:02d}/{y}" if m else f"năm {y}")
    return " ".join(s)


NGAY_LECH_TOI_DA = 30   # văn bản có ngày công chứng cũ hơn văn bản mới nhất quá số ngày này -> nghi là bản sao trong hồ sơ
M_TO_CHUC_BAT_KY = mau("PHONG CONG CHUNG")


def _ngay_so(ngay) -> int:
    y, m, d = ngay
    return y * 372 + (m or 7) * 31 + (d or 1)   # đủ để so sánh xa gần theo ngày


def cham_diem_doan(doan: list[dict], info: list[dict], trang: list[dict], rel: str, cfg: dict):
    """Tìm dấu hiệu 'văn bản của đơn vị' (+) hay 'bản sao văn bản cũ lưu trong hồ sơ' (−) cho từng văn bản.
    Trả về [(điểm, [lý do])...]; điểm KHÔNG gồm phần thưởng 'đủ tiêu đề + lời chứng'."""
    n = len(doan)
    nhieu = not cfg.get("mot_van_ban", True)
    so_ten = so_trong_ten(rel) if cfg.get("so_cc_trong_ten") else set()
    loi = loi_ten_to_chuc(cfg.get("ten_to_chuc", ""))
    m_tc = mau("CONG CHUNG " + loi) if len(loi) >= 2 else None
    ngay_ds = [x["ngay"] for x in info if x["ngay"]]
    ngay_max = max(ngay_ds) if cfg.get("uu_tien_ngay_moi", True) and len(set(ngay_ds)) > 1 else None
    # "khối" văn bản liền nhau (giữa chúng không có trang hồ sơ) — dùng cho vị trí đầu/cuối ở chế độ nhiều văn bản
    lien = [True] + [not any(trang[i]["nhan"] == "HS" for i in range(max(doan[k - 1]["trang"]) + 1, min(doan[k]["trang"])))
                     for k in range(1, n)]
    khoi_dau = set()
    for k in range(n):
        if k == 0 or (lien[k] and k - 1 in khoi_dau):
            khoi_dau.add(k)
    khoi_cuoi = set()
    for k in range(n - 1, -1, -1):
        if k == n - 1 or (lien[k + 1] and k + 1 in khoi_cuoi):
            khoi_cuoi.add(k)
    kq = []
    for k, x in enumerate(info):
        s, ly = 0, []
        if so_ten and x["so_cc"]:
            if x["so_cc"] & so_ten:
                s += 6; ly.append(f"số CC {min(x['so_cc'] & so_ten)} khớp tên file")
            else:
                s -= 6; ly.append(f"số CC {min(x['so_cc'])} không có trong tên file")
        if m_tc:
            if m_tc.search(x["chu"]):
                s += 3; ly.append("lời chứng đúng tên tổ chức")
            elif M_TO_CHUC_BAT_KY.search(x["chu"]):
                s -= 3; ly.append("lời chứng ghi tổ chức khác")
        if ngay_max and x["ngay"]:
            lech = _ngay_so(ngay_max) - _ngay_so(x["ngay"])
            if lech <= NGAY_LECH_TOI_DA:
                s += 2; ly.append("ngày CC mới nhất" if lech == 0 else "ngày CC gần văn bản mới nhất")
            else:
                s -= 2; ly.append("ngày CC cũ hơn")
        vt = cfg.get("vi_tri")
        if vt in ("dau", "cuoi"):
            dung_cho = (k in khoi_dau) if vt == "dau" else (k in khoi_cuoi)
            if nhieu:
                s += 2 if dung_cho else -2
                ly.append(("nằm" if dung_cho else "không nằm") + (" ở khối đầu file" if vt == "dau" else " ở khối cuối file"))
            elif (vt == "dau" and k == 0) or (vt == "cuoi" and k == n - 1):
                s += 2; ly.append("nằm đầu file" if vt == "dau" else "nằm cuối file")
        kq.append((s, ly))
    return kq


def chon_van_ban_chinh(doan, diem):
    """Chế độ 1 văn bản/file: văn bản dẫn trước văn bản thứ hai từ 2 điểm trở lên là văn bản chính."""
    tong = [d + (2 if v["co_md"] and v["co_lc"] else 0) for v, (d, _) in zip(doan, diem)]
    xep = sorted(range(len(doan)), key=lambda k: -tong[k])
    return (xep[0] if tong[xep[0]] - tong[xep[1]] >= 2 else None), tong


def khoang(ds: list[int]) -> str:
    """[2,3,4,7] (0-based) -> '3-5,8' (1-based)"""
    ds = sorted(ds)
    out, a = [], None
    for k, x in enumerate(ds):
        if a is None:
            a = x
        if k + 1 == len(ds) or ds[k + 1] != x + 1:
            out.append(f"{a+1}" if a == x else f"{a+1}-{x+1}")
            a = None
    return ",".join(out)


def doc_khoang(s: str, so_trang: int) -> list[list[int]]:
    """'3-5,8;10-12' -> [[2,3,4,7],[9,10,11]] (0-based). Mỗi phần cách nhau ';' là 1 văn bản."""
    kq = []
    for phan in str(s).split(";"):
        ds = []
        for m in phan.replace(" ", "").split(","):
            if not m:
                continue
            if "-" in m:
                a, b = m.split("-", 1)
                ds += list(range(int(a) - 1, int(b)))
            else:
                ds.append(int(m) - 1)
        ds = [x for x in ds if 0 <= x < so_trang]
        if ds:
            kq.append(ds)
    return kq


# =====================================================================
# 3. ĐỌC CHỮ (lớp chữ có sẵn / Tesseract / Screen AI)
# =====================================================================

_SCREEN_AI = None


def ocr_anh(img: Image.Image, cfg: dict) -> str:
    if cfg["engine"] == "screenai":
        global _SCREEN_AI
        if _SCREEN_AI is None:
            from locro import ScreenAI  # pip install từ github.com/sergiocorreia/clv-locro
            _SCREEN_AI = ScreenAI()
        return _SCREEN_AI.ocr_pil_image(img.convert("RGB")).text
    import pytesseract
    if cfg.get("tesseract"):
        pytesseract.pytesseract.tesseract_cmd = cfg["tesseract"]
    if cfg.get("tessdata"):
        os.environ["TESSDATA_PREFIX"] = cfg["tessdata"]
    return pytesseract.image_to_string(img, lang=cfg["lang"], config="--oem 1 --psm 3")


def muc_muc(img: Image.Image) -> float:
    """Tỉ lệ điểm ảnh tối (bỏ 6% lề để tránh bóng mép giấy khi scan)."""
    w, h = img.size
    c = img.crop((int(w * .06), int(h * .06), int(w * .94), int(h * .94)))
    hist = c.histogram()
    tong = sum(hist) or 1
    return sum(hist[:128]) / tong


def doc_trang(page, cfg) -> dict:
    lop_chu = "" if cfg["luon_ocr"] else page.get_text("text")
    pix = page.get_pixmap(dpi=cfg["dpi"], colorspace=pymupdf.csGRAY, alpha=False)
    img = Image.frombuffer("L", (pix.width, pix.height), pix.samples, "raw", "L", pix.stride, 1)
    muc = muc_muc(img)
    if sum(c.isalpha() for c in lop_chu) >= 50:
        return dict(text=lop_chu, muc=muc, nguon="lop_chu")
    if muc < MUC_BO_QUA_OCR:  # gần như không có điểm mực nào -> khỏi OCR cho nhanh
        return dict(text="", muc=muc, nguon="trang")
    return dict(text=ocr_anh(img, cfg), muc=muc, nguon=cfg["engine"])


def khoa_cache(p: Path, cfg) -> str:
    st = p.stat()
    s = f"{p.resolve()}|{st.st_size}|{st.st_mtime_ns}|{cfg['engine']}|{cfg['dpi']}|{cfg['lang']}|{cfg['luon_ocr']}"
    return hashlib.sha1(s.encode()).hexdigest()


# =====================================================================
# 4. XỬ LÝ 1 FILE (chạy trong tiến trình con)
# =====================================================================

def ghi_pdf(src, ds: list[int], dich: Path):
    dich.parent.mkdir(parents=True, exist_ok=True)
    out = pymupdf.open()
    ds = sorted(ds)
    a = None
    for k, x in enumerate(ds):
        if a is None:
            a = x
        if k + 1 == len(ds) or ds[k + 1] != x + 1:
            out.insert_pdf(src, from_page=a, to_page=x)
            a = None
    out.save(str(dich), garbage=3, deflate=True)
    out.close()


def ten_dau_ra(rel: str, so_vb: int, k: int) -> str:
    goc = rel[:-4] if rel.lower().endswith(".pdf") else rel
    return f"{goc}.pdf" if so_vb == 1 else f"{goc}__vb{k+1}.pdf"


def xu_ly_file(duong_dan: str, rel: str, cfg: dict) -> dict:
    t0 = time.time()
    p = Path(duong_dan)
    ra = Path(cfg["ra"])
    kq = dict(duong_dan=rel, goc=p.resolve().as_uri(), so_trang=0, trang_van_ban="", trang_thai="LOI", canh_bao="", thong_tin="",
              nhan_trang="", thoi_gian=0.0, chi_tiet=[], anh=[], van_ban=[])
    try:
        src = pymupdf.open(str(p))
        n = src.page_count
        kq["so_trang"] = n
        # --- đọc chữ (có cache) ---
        khoa = khoa_cache(p, cfg)
        f_cache = ra / ".cache" / f"{khoa}.json"
        if f_cache.exists():
            doc = json.loads(f_cache.read_text(encoding="utf-8"))
        else:
            doc = [doc_trang(src[i], cfg) for i in range(n)]
            f_cache.parent.mkdir(parents=True, exist_ok=True)
            f_cache.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
        if cfg["luu_chu"]:
            f_txt = ra / "chu_ocr" / (rel + ".txt")
            f_txt.parent.mkdir(parents=True, exist_ok=True)
            f_txt.write_text("".join(f"\n===== TRANG {i+1} ({d['nguon']}) =====\n{d['text']}"
                                     for i, d in enumerate(doc)), encoding="utf-8")
        # --- gắn nhãn & ghép ---
        trang = [phan_tich_trang(d["text"], d["muc"], cfg["nguong_trang"]) for d in doc]
        doan, cb_file = chia_van_ban(trang, cfg["can_quoc_hieu"])
        info = [thong_tin_doan(d, trang, [x["text"] for x in doc]) for d in doan]
        canh_bao, thong_tin = list(cb_file), []
        if len(doan) > 1:
            diem = cham_diem_doan(doan, info, trang, rel, cfg)

            def ten(k):
                m = mo_ta_doan(info[k])
                return f"VB{k+1} tr.{khoang(doan[k]['trang'])}" + (f" {m}" if m else "")

            if cfg["mot_van_ban"]:
                chon, tong = chon_van_ban_chinh(doan, diem)
                tom = "; ".join(f"{ten(k)} = {tong[k]}đ" for k in range(len(doan)))
                if chon is not None:
                    ly = (["đủ tiêu đề + lời chứng"] if doan[chon]["co_md"] and doan[chon]["co_lc"] else []) + diem[chon][1]
                    thong_tin.append(f"chọn VB{chon+1} là văn bản chính ({', '.join(ly)}); văn bản khác coi là hồ sơ [{tom}]")
                    doan, info = [doan[chon]], [info[chon]]
                else:
                    canh_bao.append(f"có {len(doan)} văn bản, chưa phân định được văn bản chính [{tom}]")
            else:
                giu = [k for k in range(len(doan)) if diem[k][0] >= 0]
                bo = [k for k in range(len(doan)) if diem[k][0] < 0]
                if not giu:
                    canh_bao.append("mọi văn bản đều có dấu hiệu là bản sao trong hồ sơ — đã giữ cả, cần xem lại: "
                                    + "; ".join(f"{ten(k)} ({', '.join(diem[k][1])})" for k in bo))
                    giu, bo = bo, []
                for k in bo:
                    thong_tin.append(f"bỏ {ten(k)} vào hồ sơ ({', '.join(diem[k][1])})")
                if any(diem[k][0] != 0 for k in range(len(doan))):
                    for k in giu:
                        if diem[k][0] == 0:
                            canh_bao.append(f"{ten(k)}: không có dấu hiệu xác minh là văn bản của đơn vị")
                thong_tin.append(f"giữ {len(giu)} văn bản: " + "; ".join(
                    ten(k) + (f" ({', '.join(diem[k][1])})" if diem[k][1] else "") for k in giu))
                doan, info = [doan[k] for k in giu], [info[k] for k in giu]
        if len(doan) == 1 and mo_ta_doan(info[0]):
            thong_tin.append(mo_ta_doan(info[0]))
        for k, d in enumerate(doan):
            tien_to = f"VB{k+1}: " if len(doan) > 1 else ""
            canh_bao += [tien_to + c for c in d["canh_bao"]]
        if cfg["giu_trang_trang"]:
            for d in doan:
                a, b = min(d["trang"]), max(d["trang"])
                d["trang"] = sorted(set(d["trang"]) | {i for i in range(a, b + 1) if trang[i]["nhan"] == "TT"})
        so_trang_trang = sum(t["nhan"] == "TT" for t in trang)
        if so_trang_trang:
            thong_tin.append(f"{so_trang_trang} trang trắng")
        ocr_n = sum(d["nguon"] not in ("lop_chu", "trang") for d in doc)
        thong_tin.append(f"OCR {ocr_n}/{n} trang")

        def du(d):
            return d["co_md"] and d["co_lc"] and (d["quoc_hieu"] or not cfg["can_quoc_hieu"])

        if not doan:
            trang_thai = "KHONG_THAY"
        elif all(du(d) for d in doan) and not canh_bao and (len(doan) == 1 or not cfg["mot_van_ban"]):
            trang_thai = "DAT"
        else:
            trang_thai = "CAN_KIEM_TRA"

        trong_vb = {}
        for k, d in enumerate(doan):
            for x in d["trang"]:
                trong_vb[x] = k + 1
        kq.update(
            trang_van_ban=";".join(khoang(d["trang"]) for d in doan),
            trang_thai=trang_thai,
            canh_bao=" | ".join(canh_bao),
            thong_tin=" · ".join(thong_tin),
            nhan_trang=" ".join(f"{i+1}:{t['nhan']}" for i, t in enumerate(trang)),
            chi_tiet=[dict(nhan=t["nhan"], ly_do=t["ly_do"], vb=trong_vb.get(i, 0)) for i, t in enumerate(trang)],
        )
        # --- xuất PDF ---
        thu_muc = "dat" if trang_thai == "DAT" else "can_kiem_tra"
        for k, d in enumerate(doan):
            dich = ra / thu_muc / ten_dau_ra(rel, len(doan), k)
            ghi_pdf(src, d["trang"], dich)
            kq["van_ban"].append(str(dich.relative_to(ra)))
        if cfg["xuat_ho_so"]:
            con_lai = [i for i in range(n) if i not in trong_vb]
            if con_lai:
                ghi_pdf(src, con_lai, ra / "ho_so" / rel)
        # --- ảnh thu nhỏ cho trang xem lại ---
        if cfg["xem_tat_ca"] or trang_thai != "DAT":
            th = ra / "anh" / khoa[:16]
            th.mkdir(parents=True, exist_ok=True)
            for i in range(n):
                f = th / f"{i+1}.jpg"
                if not f.exists():
                    pix = src[i].get_pixmap(dpi=cfg["dpi_anh"], alpha=False)
                    Image.frombuffer("RGB", (pix.width, pix.height), pix.samples, "raw", "RGB", pix.stride, 1) \
                        .save(f, quality=60)
                kq["anh"].append(str(f.relative_to(ra)).replace("\\", "/"))
        src.close()
    except Exception as e:  # file hỏng, có mật khẩu...
        kq["canh_bao"] = f"{type(e).__name__}: {e}"
        if cfg.get("debug"):
            traceback.print_exc()
    kq["thoi_gian"] = round(time.time() - t0, 1)
    return kq


# =====================================================================
# 5. BÁO CÁO
# =====================================================================

COT_CSV = ["duong_dan", "so_trang", "trang_van_ban", "trang_thai", "canh_bao", "thong_tin", "nhan_trang", "thoi_gian"]
THU_TU = {"LOI": 0, "KHONG_THAY": 1, "CAN_KIEM_TRA": 2, "DAT": 3}
MAU_NHAN = {"MD": "#2563eb", "TH": "#60a5fa", "LC": "#16a34a", "HS": "#9ca3af", "TT": "#e5e7eb", "KR": "#f59e0b"}
MAU_TT = {"DAT": "#16a34a", "CAN_KIEM_TRA": "#d97706", "KHONG_THAY": "#dc2626", "LOI": "#7f1d1d"}


def ghi_csv(ds: list[dict], f: Path):
    with open(f, "w", newline="", encoding="utf-8-sig") as fh:  # utf-8-sig để Excel đọc đúng tiếng Việt
        w = csv.DictWriter(fh, fieldnames=COT_CSV, extrasaction="ignore")
        w.writeheader()
        for r in sorted(ds, key=lambda r: (THU_TU.get(r["trang_thai"], 9), r["duong_dan"])):
            w.writerow(r)


def ghi_xlsx(ds: list[dict], f: Path):
    """Bảng Excel để sửa tay. Cột trang_van_ban để dạng Text để Excel không tự đổi '3-7' thành ngày tháng."""
    try:
        from openpyxl import Workbook
        from openpyxl.styles import Font, PatternFill
    except ImportError:
        print("(Chưa cài openpyxl nên không tạo bao_cao.xlsx — vẫn có bao_cao.csv)")
        return
    wb = Workbook()
    ws = wb.active
    ws.title = "bao_cao"
    ws.append(COT_CSV)
    for c in ws[1]:
        c.font = Font(bold=True)
    nen = {"DAT": "DCFCE7", "CAN_KIEM_TRA": "FEF3C7", "KHONG_THAY": "FEE2E2", "LOI": "FECACA"}
    for r in sorted(ds, key=lambda r: (THU_TU.get(r["trang_thai"], 9), r["duong_dan"])):
        ws.append([r.get(k, "") for k in COT_CSV])
        hang = ws.max_row
        ws.cell(hang, 3).number_format = "@"
        ws.cell(hang, 4).fill = PatternFill("solid", fgColor=nen.get(r["trang_thai"], "FFFFFF"))
    for hang in range(ws.max_row + 1, ws.max_row + 200):
        ws.cell(hang, 3).number_format = "@"
    for cot, rong in zip("ABCDEFGH", (45, 9, 18, 15, 70, 22, 60, 9)):
        ws.column_dimensions[cot].width = rong
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = ws.dimensions
    wb.save(f)


def doc_bang(f: Path) -> list[dict]:
    if f.suffix.lower() in (".xlsx", ".xlsm"):
        from openpyxl import load_workbook
        ws = load_workbook(f, read_only=True, data_only=True).active
        hang = list(ws.iter_rows(values_only=True))
        cot = [str(c or "").strip() for c in hang[0]]
        return [{k: ("" if v is None else str(v)) for k, v in zip(cot, h)} for h in hang[1:] if any(h)]
    with open(f, encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def ghi_html(ds: list[dict], f: Path):
    e = html.escape
    dem = {k: sum(r["trang_thai"] == k for r in ds) for k in THU_TU}
    the = []
    for r in sorted(ds, key=lambda r: (THU_TU.get(r["trang_thai"], 9), r["duong_dan"])):
        o = []
        for i, ct in enumerate(r["chi_tiet"]):
            anh = f'<img loading="lazy" src="{e(r["anh"][i])}">' if i < len(r["anh"]) else '<div class="trong"></div>'
            vien = "vb" if ct["vb"] else "ngoai"
            nhan_vb = f' · VB{ct["vb"]}' if ct["vb"] and r["trang_van_ban"].count(";") else ""
            anh = f'<a href="{e(r["goc"])}#page={i+1}" target="_blank">{anh}</a>'
            o.append(f'<figure class="{vien}" title="{e(ct["ly_do"])}">{anh}<figcaption>'
                     f'<b>{i+1}</b> <span style="background:{MAU_NHAN[ct["nhan"]]}">{NHAN_TEN[ct["nhan"]]}</span>{nhan_vb}'
                     f'</figcaption></figure>')
        the.append(f'''<section data-tt="{r["trang_thai"]}">
<h3><span class="tt" style="background:{MAU_TT.get(r["trang_thai"], "#000")}">{r["trang_thai"]}</span> {e(r["duong_dan"])}</h3>
<p>Trang văn bản: <b>{e(r["trang_van_ban"] or "—")}</b> / {r["so_trang"]} trang · {e(r["thong_tin"])}</p>
{f'<p class="cb">⚠ {e(r["canh_bao"])}</p>' if r["canh_bao"] else ""}
<div class="luoi">{"".join(o)}</div></section>''')
    nut = "".join(f'<button onclick="loc(\'{k}\')">{k} ({v})</button>' for k, v in dem.items() if v)
    f.write_text(f'''<!DOCTYPE html><html lang="vi"><head><meta charset="utf-8"><title>Xem lại tách văn bản</title>
<style>
body{{font:14px system-ui,sans-serif;margin:20px;color:#111;background:#fafafa}}
section{{background:#fff;border:1px solid #ddd;border-radius:8px;padding:12px 16px;margin:14px 0}}
h3{{margin:0 0 6px;font-size:15px}} p{{margin:4px 0}} .cb{{color:#b45309}}
.tt{{color:#fff;padding:2px 8px;border-radius:4px;font-size:12px}}
.luoi{{display:flex;flex-wrap:wrap;gap:8px;margin-top:8px}}
figure{{margin:0;width:130px;border:3px solid #ddd;border-radius:4px;background:#fff}}
figure.vb{{border-color:#16a34a}} figure.ngoai{{opacity:.55}}
figure img,.trong{{width:100%;display:block;aspect-ratio:1/1.414;object-fit:contain;background:#f3f4f6}}
figcaption{{font-size:11px;padding:3px}} figcaption span{{color:#fff;padding:1px 4px;border-radius:3px}}
button{{margin-right:6px;padding:4px 10px}}
</style></head><body>
<h2>Kết quả tách văn bản công chứng ({len(ds)} file)</h2>
<p>Viền <b style="color:#16a34a">xanh</b> = trang được đưa vào văn bản; trang mờ = để lại hồ sơ. Rê chuột lên trang để xem lý do gắn nhãn; bấm vào trang để mở bản gốc đúng trang đó.
Sửa sai: mở <code>bao_cao.xlsx</code>, sửa cột <code>trang_van_ban</code> (vd <code>3-7</code>, nhiều văn bản: <code>3-7;12-15</code>, bỏ qua: <code>BO</code>), lưu lại rồi chạy với <code>--theo-bang</code>.
File DAT không có ảnh thu nhỏ trừ khi chạy với <code>--xem-tat-ca</code>.</p>
<p>Lọc: <button onclick="loc('')">Tất cả</button>{nut}</p>
{"".join(the)}
<script>function loc(t){{document.querySelectorAll('section').forEach(s=>s.style.display=(!t||s.dataset.tt==t)?'':'none')}}</script>
</body></html>''', encoding="utf-8")


# =====================================================================
# 6. CHẾ ĐỘ CẮT LẠI THEO CSV ĐÃ SỬA
# =====================================================================

def cat_theo_bang(vao, ra, f_bang, log=print) -> int:
    """Cắt PDF theo cột trang_van_ban của bảng đã sửa tay. Trả về số file đã cắt."""
    vao, ra, f_bang = Path(vao), Path(ra), Path(f_bang)
    dich_goc = ra / "chot"
    if dich_goc.exists() and any(dich_goc.rglob("*.pdf")):
        log(f"Lưu ý: {dich_goc} đã có file từ lần trước; file trùng tên sẽ bị ghi đè, file khác giữ nguyên.")
    n_ok = n_bo = 0
    for r in doc_bang(f_bang):
        rel = (r.get("duong_dan") or "").strip()
        s = (r.get("trang_van_ban") or "").strip()
        if not rel or not s or s.upper() in ("BO", "BỎ", "-"):
            n_bo += 1
            continue
        src_p = vao / rel if vao.is_dir() else vao
        try:
            src = pymupdf.open(str(src_p))
            ds = doc_khoang(s, src.page_count)
            if not ds:
                raise ValueError(f"không hiểu '{s}'")
            for k, d in enumerate(ds):
                ghi_pdf(src, d, dich_goc / ten_dau_ra(rel, len(ds), k))
            src.close()
            n_ok += 1
        except Exception as e:
            log(f"  LỖI {rel}: {e}")
    log(f"Đã cắt {n_ok} file vào {dich_goc} (bỏ qua {n_bo} dòng trống/BO).")
    return n_ok


# =====================================================================
# 7. CHẠY (dùng chung cho dòng lệnh và giao diện)
# =====================================================================

def cfg_mac_dinh() -> dict:
    return dict(
        # cấu trúc hồ sơ
        mot_van_ban=True,          # mỗi file chỉ có 1 văn bản công chứng chính
        vi_tri="tu_dong",          # tu_dong | dau | cuoi : văn bản chính thường nằm ở đâu
        so_cc_trong_ten=False,     # tên file/thư mục có chứa số công chứng
        ten_to_chuc="",            # tên tổ chức hành nghề công chứng của mình
        uu_tien_ngay_moi=True,     # văn bản có ngày công chứng mới nhất là văn bản chính
        can_quoc_hieu=True,        # văn bản luôn có Quốc hiệu
        giu_trang_trang=False,     # giữ trang trắng nằm giữa văn bản
        # đọc chữ
        engine="tesseract", dpi=200, lang="vie", tesseract=None, tessdata=None, luon_ocr=False, nguong_trang=0.002,
        # đầu ra
        xem_tat_ca=False, xuat_ho_so=False, luu_chu=False, dpi_anh=40, debug=False,
    )


def thu_muc_ung_dung() -> Path:
    """Thư mục chứa chương trình (cạnh file .exe khi đã đóng gói, cạnh file .py khi chạy mã nguồn)."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def tim_tesseract():
    for c in ("tesseract.exe", "tesseract"):  # Tesseract đóng gói kèm (bản phát hành cho Windows)
        f = thu_muc_ung_dung() / "tesseract" / c
        if f.is_file():
            return str(f)
    if shutil.which("tesseract"):
        return None
    for c in (r"C:\Program Files\Tesseract-OCR\tesseract.exe", r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
              os.path.expandvars(r"%LOCALAPPDATA%\Programs\Tesseract-OCR\tesseract.exe"),
              os.path.expandvars(r"%LOCALAPPDATA%\Tesseract-OCR\tesseract.exe"),
              "/opt/homebrew/bin/tesseract", "/usr/local/bin/tesseract"):
        if os.path.exists(c):
            return c
    return None


URL_TESSERACT = "https://github.com/UB-Mannheim/tesseract/wiki"
URL_GOI_VIE = "https://github.com/tesseract-ocr/tessdata/raw/main/vie.traineddata"
URL_TRANG_GOI = "https://github.com/tesseract-ocr/tessdata"
URL_PYTHON = "https://www.python.org/downloads/windows/"


def thu_muc_goi_rieng() -> Path:
    """Thư mục riêng của người dùng để chứa gói ngôn ngữ tải về (không cần quyền admin)."""
    if sys.platform == "win32":
        return Path(os.environ.get("LOCALAPPDATA") or Path.home()) / "TachVanBan" / "tessdata"
    return Path.home() / ".local" / "share" / "tach_van_ban" / "tessdata"


def tai_goi_tieng_viet(log=print, url: str = URL_GOI_VIE) -> Path:
    """Tải vie.traineddata về thư mục riêng của người dùng. Trả về đường dẫn file."""
    import urllib.request
    dich = thu_muc_goi_rieng()
    dich.mkdir(parents=True, exist_ok=True)
    tam = dich / "vie.traineddata.dang_tai"
    log(f"Đang tải gói tiếng Việt từ {url} …")
    with urllib.request.urlopen(url, timeout=60) as r, open(tam, "wb") as f:
        tong = int(r.headers.get("Content-Length") or 0)
        da = 0
        while True:
            khoi = r.read(256 * 1024)
            if not khoi:
                break
            f.write(khoi)
            da += len(khoi)
            log(f"  {da // 1024} KB" + (f" / {tong // 1024} KB" if tong else ""))
    if da < 200_000:
        tam.unlink(missing_ok=True)
        raise ValueError(f"file tải về quá nhỏ ({da} byte) — có thể mạng chặn GitHub")
    f_vie = dich / "vie.traineddata"
    tam.replace(f_vie)
    log(f"Đã lưu gói tiếng Việt vào {f_vie}")
    return f_vie


def kiem_tra_ocr(cfg: dict) -> tuple[bool, str]:
    """Kiểm tra engine OCR dùng được chưa. Trả về (được/không, thông báo).
    Nếu Tesseract thiếu gói tiếng Việt nhưng đã tải gói riêng thì ghi cfg['tessdata'] để dùng gói đó."""
    if cfg["engine"] == "screenai":
        import importlib.util
        if importlib.util.find_spec("locro"):
            return True, "Đã có thư viện locro (Screen AI của Chrome)."
        return False, "Chưa cài thư viện locro cho Screen AI (xem HUONG_DAN.md mục 7)."
    try:
        import pytesseract
    except ImportError:
        return False, "Chưa cài thư viện Python (chạy cai_dat.bat hoặc pip install -r requirements.txt)."
    duong_dan = cfg.get("tesseract") or tim_tesseract()
    if duong_dan:
        pytesseract.pytesseract.tesseract_cmd = duong_dan
    cu = os.environ.pop("TESSDATA_PREFIX", None)
    try:
        ver = pytesseract.get_tesseract_version()
        langs = pytesseract.get_languages()
    except pytesseract.TesseractNotFoundError:
        return False, "Không tìm thấy Tesseract. Bấm 'Tải Tesseract' để cài, hoặc chỉ đường dẫn tới tesseract.exe."
    except Exception as e:
        return False, f"Lỗi khi gọi Tesseract: {e}"
    finally:
        if cu is not None:
            os.environ["TESSDATA_PREFIX"] = cu
    if cfg["lang"] in langs:
        cfg["tessdata"] = None
        return True, f"Tesseract {ver} · có gói tiếng Việt."
    ung_vien = [thu_muc_goi_rieng()]
    if duong_dan:
        ung_vien.insert(0, Path(duong_dan).parent / "tessdata")
    for rieng in ung_vien:
        if not (rieng / f"{cfg['lang']}.traineddata").exists():
            continue
        os.environ["TESSDATA_PREFIX"] = str(rieng)
        try:
            ok = cfg["lang"] in pytesseract.get_languages()
        except Exception:
            ok = False
        if ok:
            cfg["tessdata"] = str(rieng)
            return True, f"Tesseract {ver} · dùng gói tiếng Việt ở {rieng}."
    return False, (f"Tesseract {ver} chưa có gói tiếng Việt. Bấm 'Tải gói tiếng Việt' "
                   "(hoặc cài lại Tesseract và tick Vietnamese).")


def liet_ke_pdf(vao, ra, gioi_han: int = 0) -> list[tuple[Path, str]]:
    vao, ra = Path(vao), Path(ra)
    if vao.is_file():
        ds = [(vao, vao.name)]
    else:
        ra_abs = ra.resolve()
        ds = sorted((p, p.relative_to(vao).as_posix()) for p in vao.rglob("*")
                    if p.is_file() and p.suffix.lower() == ".pdf" and ra_abs not in p.resolve().parents)
    return ds[:gioi_han] if gioi_han else ds


def dem_trang_thai(kq: list[dict]) -> dict:
    return {k: sum(r["trang_thai"] == k for r in kq) for k in THU_TU}


def chay_tach(vao, ra, cfg: dict, so_luong: int = 1, gioi_han: int = 0,
              log=print, tien_do=None, dung=None) -> list[dict]:
    """Chạy toàn bộ. tien_do(k, tong, ket_qua_file) được gọi sau mỗi file; dung là threading.Event để dừng giữa chừng."""
    vao, ra = Path(vao), Path(ra)
    ra.mkdir(parents=True, exist_ok=True)
    ds = liet_ke_pdf(vao, ra, gioi_han)
    if not ds:
        log(f"Không thấy file PDF nào trong {vao}")
        return []
    cfg = dict(cfg, ra=str(ra))
    if cfg["engine"] == "tesseract":
        if not cfg.get("tesseract"):
            cfg["tesseract"] = tim_tesseract()
        kiem_tra_ocr(cfg)  # chọn gói tiếng Việt: của Tesseract hay gói đã tải riêng
    so_luong = 1 if cfg["engine"] == "screenai" else max(1, int(so_luong))
    log(f"tach_van_ban {PHIEN_BAN} · {len(ds)} file · engine={cfg['engine']} · song song={so_luong}")
    t0 = time.time()
    kq = []

    def nhan(r):
        kq.append(r)
        if tien_do:
            tien_do(len(kq), len(ds), r)
        vb = r["trang_van_ban"] or "—"
        log(f"[{len(kq)}/{len(ds)}] {r['trang_thai']:<12} {vb:<14} {r['duong_dan']}  ({r['thoi_gian']}s)")

    if so_luong == 1:
        for p, rel in ds:
            if dung is not None and dung.is_set():
                break
            nhan(xu_ly_file(str(p), rel, cfg))
    else:
        # luôn dùng "spawn": an toàn khi gọi từ giao diện (đa luồng) và giống hệt cách chạy trên Windows
        ex = ProcessPoolExecutor(max_workers=so_luong, mp_context=multiprocessing.get_context("spawn"))
        try:
            fut = [ex.submit(xu_ly_file, str(p), rel, cfg) for p, rel in ds]
            for f in as_completed(fut):
                nhan(f.result())
                if dung is not None and dung.is_set():
                    for x in fut:
                        x.cancel()
                    break
        finally:
            ex.shutdown(wait=True, cancel_futures=True)

    if len(kq) < len(ds):
        log(f"Đã dừng: xử lý xong {len(kq)}/{len(ds)} file; báo cáo dưới đây chỉ gồm các file này.")
    if kq:
        ghi_csv(kq, ra / "bao_cao.csv")
        ghi_xlsx(kq, ra / "bao_cao.xlsx")
        ghi_html(kq, ra / "xem_lai.html")
        dem = dem_trang_thai(kq)
        log(f"Xong {len(kq)} file trong {time.time()-t0:.0f}s · " + " · ".join(f"{k}: {v}" for k, v in dem.items()))
        log(f"→ Xem lại: {ra / 'xem_lai.html'} · sửa tay: {ra / 'bao_cao.xlsx'}")
    return kq


def main():
    for luong in (sys.stdout, sys.stderr):  # tránh lỗi in tiếng Việt khi chuyển hướng ra file trên Windows
        try:
            luong.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    md = cfg_mac_dinh()
    ap = argparse.ArgumentParser(description="Tách văn bản công chứng khỏi hồ sơ lưu trong PDF scan gộp.")
    ap.add_argument("vao", help="thư mục chứa PDF (quét cả thư mục con) hoặc 1 file PDF")
    ap.add_argument("ra", help="thư mục ghi kết quả")
    g = ap.add_argument_group("cấu trúc hồ sơ")
    g.add_argument("--nhieu-van-ban", action="store_true",
                   help="1 file có thể chứa nhiều văn bản công chứng (mặc định: chỉ 1, văn bản khác coi là hồ sơ)")
    g.add_argument("--vi-tri", choices=["tu_dong", "dau", "cuoi"], default="tu_dong",
                   help="văn bản chính thường nằm ở đầu/cuối file")
    g.add_argument("--so-cc-trong-ten", action="store_true", help="tên file/thư mục chứa số công chứng")
    g.add_argument("--ten-to-chuc", default="", help="tên tổ chức hành nghề công chứng của mình")
    g.add_argument("--khong-uu-tien-ngay", action="store_true", help="không dùng ngày công chứng để chọn văn bản chính")
    g.add_argument("--khong-can-quoc-hieu", action="store_true", help="văn bản không có Quốc hiệu vẫn được coi là đạt")
    g.add_argument("--giu-trang-trang", action="store_true", help="giữ trang trắng nằm giữa văn bản")
    g = ap.add_argument_group("đọc chữ")
    g.add_argument("--engine", choices=["tesseract", "screenai"], default="tesseract")
    g.add_argument("--dpi", type=int, default=md["dpi"], help="độ phân giải khi OCR (mặc định 200)")
    g.add_argument("--lang", default=md["lang"], help="ngôn ngữ Tesseract (mặc định vie)")
    g.add_argument("--tesseract", help="đường dẫn tesseract.exe nếu không tự tìm thấy")
    g.add_argument("--luon-ocr", action="store_true", help="OCR cả trang đã có lớp chữ")
    g.add_argument("--nguong-trang", type=float, default=md["nguong_trang"], help="tỉ lệ mực dưới mức này coi là trang trắng")
    g = ap.add_argument_group("chạy & đầu ra")
    g.add_argument("--so-luong", type=int, default=max(1, (os.cpu_count() or 2) - 1), help="số file xử lý song song")
    g.add_argument("--gioi-han", type=int, default=0, help="chỉ chạy N file đầu (để thử)")
    g.add_argument("--xem-tat-ca", action="store_true", help="tạo ảnh thu nhỏ cho cả file DAT")
    g.add_argument("--xuat-ho-so", action="store_true", help="xuất thêm phần hồ sơ còn lại vào ho_so/")
    g.add_argument("--luu-chu", action="store_true", help="lưu chữ OCR từng file vào chu_ocr/ (để dò lỗi)")
    g.add_argument("--theo-bang", "--theo-csv", dest="theo_bang",
                   help="bỏ qua OCR, cắt PDF theo cột trang_van_ban trong bao_cao.xlsx/.csv đã sửa")
    g.add_argument("--debug", action="store_true")
    a = ap.parse_args()

    if a.theo_bang:
        cat_theo_bang(a.vao, a.ra, a.theo_bang)
        return
    cfg = dict(md, mot_van_ban=not a.nhieu_van_ban, vi_tri=a.vi_tri, so_cc_trong_ten=a.so_cc_trong_ten,
               ten_to_chuc=a.ten_to_chuc, uu_tien_ngay_moi=not a.khong_uu_tien_ngay,
               can_quoc_hieu=not a.khong_can_quoc_hieu, giu_trang_trang=a.giu_trang_trang,
               engine=a.engine, dpi=a.dpi, lang=a.lang, tesseract=a.tesseract, luon_ocr=a.luon_ocr,
               nguong_trang=a.nguong_trang, xem_tat_ca=a.xem_tat_ca, xuat_ho_so=a.xuat_ho_so,
               luu_chu=a.luu_chu, debug=a.debug)
    ok, tb = kiem_tra_ocr(cfg)
    if not ok:
        sys.exit(tb)
    chay_tach(a.vao, a.ra, cfg, so_luong=a.so_luong, gioi_han=a.gioi_han)


if __name__ == "__main__":
    main()
