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

PHIEN_BAN = "0.3.4"

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
M_SO_CONG_CHUNG = [mau("SO CONG CHUNG"), re.compile(r"\bQUYEN S[O0] \d"), re.compile(r"\bTP ?/ ?CC\b")]
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
    "TT": "Trang trắng", "KR": "Không rõ", "TR": "Trùng",
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
            r = gan("MD", f"tiêu đề '{d[:60]}'")
            r["tieu_de"] = d
            return r
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
    re.compile(r"\bS[O0] C[O0]NG CHUNG(?: S[O0])? ((?:\d ?){3,8})"),
    re.compile(r"\bC[O0]NG CHUNG S[O0] ((?:\d ?){3,8})"),
    re.compile(r"\bS[O0] ((?:\d ?){3,8}) QUYEN S[O0]\b"),
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


def _chuan_so(x: str) -> str:
    return x.replace(" ", "").lstrip("0") or "0"


def so_trong_ten(rel: str) -> set[str]:
    goc = rel.rsplit(".", 1)[0]
    return {_chuan_so(x) for x in re.findall(r"\d+", goc) if 3 <= len(x) <= 8}


def _gan_giong(a: str, b: str) -> bool:
    """Bằng nhau, hoặc (số từ 4 chữ số) lệch đúng 1 chữ số do OCR đọc sai/thiếu/thừa."""
    if a == b:
        return True
    if min(len(a), len(b)) < 4 or abs(len(a) - len(b)) > 1:
        return False
    if len(a) == len(b):
        return sum(x != y for x, y in zip(a, b)) == 1
    dai, ngan = (a, b) if len(a) > len(b) else (b, a)
    return any(dai[:k] + dai[k + 1:] == ngan for k in range(len(dai)))


def khop_so(so_cc: set[str], so_ten: set[str]):
    """Số công chứng đọc được có khớp số trong tên file không. Trả về số khớp hoặc None."""
    for a in sorted(so_cc):
        for b in sorted(so_ten):
            if _gan_giong(a, b):
                return b
    return None


def thong_tin_doan(d: dict, trang: list[dict], texts: list[str]) -> dict:
    """Đọc số công chứng, ngày công chứng từ trang lời chứng của 1 văn bản."""
    lc = [i for i in d["trang"] if trang[i]["nhan"] == "LC"]  # chỉ tin số/ngày/tên tổ chức ghi trong lời chứng
    t = " ".join(bo_dau(texts[i]) for i in lc)
    so, so_tho = set(), []
    for m in M_SO_CC_SO:
        for x in m.findall(t):
            x = x.replace(" ", "")
            if len(x) >= 3:
                so.add(_chuan_so(x))
                so_tho.append(x)
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
    loai = next((trang[i].get("tieu_de", "") for i in d["trang"] if trang[i]["nhan"] == "MD"), "")
    return dict(so_cc=so, so_tho=so_tho, ngay=ngay, loai=loai, chu=t)


def mo_ta_doan(x: dict) -> str:
    s = []
    if x["so_cc"]:
        s.append("số CC " + "/".join(sorted(x["so_cc"])))
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
            khop = khop_so(x["so_cc"], so_ten)
            if khop:
                s += 6; ly.append(f"số CC {khop} khớp tên file")
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


def ocr_anh(img: Image.Image, cfg: dict):
    """Trả về (chữ, danh sách từ kèm vị trí [chữ, x0, y0, x1, y1, mã dòng] theo tỉ lệ 0..1 hoặc None)."""
    if cfg["engine"] == "screenai":
        global _SCREEN_AI
        if _SCREEN_AI is None:
            from locro import ScreenAI  # pip install từ github.com/sergiocorreia/clv-locro
            _SCREEN_AI = ScreenAI()
        return _SCREEN_AI.ocr_pil_image(img.convert("RGB")).text, None
    import pytesseract
    if cfg.get("tesseract"):
        pytesseract.pytesseract.tesseract_cmd = cfg["tesseract"]
    if cfg.get("tessdata"):
        os.environ["TESSDATA_PREFIX"] = cfg["tessdata"]
    d = pytesseract.image_to_data(img, lang=cfg["lang"], config="--oem 1 --psm 3",
                                  output_type=pytesseract.Output.DICT)
    w, h = img.size
    dong, tu, truoc, khoi_truoc = [], [], None, None
    cac_dong = []
    for k, chu in enumerate(d["text"]):
        if not chu or not chu.strip():
            continue
        ma = (d["block_num"][k], d["par_num"][k], d["line_num"][k])
        if ma != truoc:
            if dong:
                cac_dong.append(" ".join(dong))
            if khoi_truoc is not None and ma[0] != khoi_truoc:
                cac_dong.append("")
            dong, truoc, khoi_truoc = [], ma, ma[0]
        dong.append(chu)
        x, y, ww, hh = d["left"][k], d["top"][k], d["width"][k], d["height"][k]
        tu.append([chu, x / w, y / h, (x + ww) / w, (y + hh) / h, "%d.%d.%d" % ma])
    if dong:
        cac_dong.append(" ".join(dong))
    return "\n".join(cac_dong), tu


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
        r = page.rect
        tu = [[w[4], w[0] / r.width, w[1] / r.height, w[2] / r.width, w[3] / r.height, "%d.%d" % (w[5], w[6])]
              for w in page.get_text("words")]
        return dict(text=lop_chu, muc=muc, nguon="lop_chu", so_in=tim_so_trang_in(tu), ma_anh=ma_anh(page))
    if muc < MUC_BO_QUA_OCR:  # gần như không có điểm mực nào -> khỏi OCR cho nhanh
        return dict(text="", muc=muc, nguon="trang", so_in=None, ma_anh=None)
    text, tu = ocr_anh(img, cfg)
    return dict(text=text, muc=muc, nguon=cfg["engine"], so_in=tim_so_trang_in(tu) if tu else None,
                ma_anh=ma_anh(page))


# ---------- Số trang in trên trang ("1", "- 2 -", "Trang 3/5") ----------
_GIONG_SO = str.maketrans({"l": "1", "I": "1", "|": "1", "i": "1", "O": "0", "o": "0"})


def tim_so_trang_in(tu) -> list | None:
    """Tìm số trang in ở lề phải hoặc giữa, phần dưới (hoặc mép trên) của trang. Trả về [số, tổng hoặc None]."""
    if not tu:
        return None
    theo_dong = {}
    for t in tu:
        theo_dong.setdefault(t[5], []).append(t)
    ung_vien = []
    for chu, x0, y0, x1, y1, ma in tu:
        s = chu.strip().strip("-–—.,:;()[]{}'\"_~").translate(_GIONG_SO)
        m = re.fullmatch(r"(\d{1,3})(?:/(\d{1,3}))?", s)
        if not m:
            continue
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        if not (cy > 0.55 or cy < 0.08) or not (cx > 0.80 or 0.38 < cx < 0.62):
            continue
        cung = [t for t in theo_dong[ma] if t[1] != x0 and any(c.isalnum() for c in t[0])]
        if cung:
            # cho phép "Trang 2", hoặc số đứng tách hẳn ở mép phải dòng (vd chân trang có email bên trái)
            truoc = max((t for t in cung if t[3] <= x0 + 1e-6), key=lambda t: t[3], default=None)
            la_chu_trang = len(cung) == 1 and bo_dau(cung[0][0]) == "TRANG"
            tach_xa = cx > 0.85 and (truoc is None or x0 - truoc[3] > 0.12) and not any(t[1] > x1 for t in cung)
            if not (la_chu_trang or tach_xa):
                continue
        so = int(m.group(1))
        tong = int(m.group(2)) if m.group(2) else None
        if 1 <= so <= 300 and (tong is None or so <= tong):
            ung_vien.append((cy, so, tong))
    if not ung_vien:
        return None
    _, so, tong = max(ung_vien)  # lấy số nằm thấp nhất trên trang
    return [so, tong]


# ---------- Kiểm tra thiếu trang / trùng trang trong 1 văn bản ----------
_SO_DON = {"KHONG": 0, "MOT": 1, "MOTT": 1, "HAI": 2, "BA": 3, "BON": 4, "TU": 4, "NAM": 5, "LAM": 5,
           "SAU": 6, "BAY": 7, "TAM": 8, "CHIN": 9}
M_DIEU_DAU_DONG = re.compile(r"^D[I1L]EU ?(\d{1,2})\b")


def _so_tu_chu(tu: list[str]):
    """['HAI','MUOI','MOT'] -> 21; ['MUOI','HAI'] -> 12; ['BA'] -> 3; không hiểu -> None."""
    tu = [x for x in tu if x not in ("LINH", "LE")]
    if not tu:
        return None
    if "MUOI" not in tu:
        return _SO_DON.get(tu[-1]) if len(tu) == 1 else None
    k = tu.index("MUOI")
    chuc = _SO_DON.get(tu[k - 1]) if k > 0 else 1
    dv = _SO_DON.get(tu[k + 1]) if k + 1 < len(tu) else 0
    return None if chuc is None or dv is None else chuc * 10 + dv


def _so_dung_truoc(tu: list[str]):
    """Con số đứng ngay trước chữ 'tờ'/'trang': '02 (hai)' / '02' / 'hai mươi mốt'."""
    chu = []
    for x in reversed(tu[-5:]):
        if re.fullmatch(r"[0-9O]{1,3}", x) and any(c.isdigit() for c in x):
            return int(x.replace("O", "0"))
        if x in _SO_DON or x in ("MUOI", "LINH", "LE"):
            chu.insert(0, x)
            continue
        break
    return _so_tu_chu(chu)


def so_trang_theo_loi_chung(chu_lc: str):
    """'…mỗi bản chính gồm 02 (hai) tờ, 02 (hai) trang' -> (số tờ, số trang); thiếu thì None.
    Nhận cả 'bao gồm', 'gồm có', số viết bằng chữ, chữ số 0 bị OCR đọc thành O."""
    tu = chu_lc.split()
    for k, w in enumerate(tu):
        if w not in ("GOM", "G0M"):
            continue
        so_to = so_tr = None
        cua_so = tu[k + 1:k + 18]
        for j, x in enumerate(cua_so):
            if x in ("TO", "T0") and so_to is None:
                so_to = _so_dung_truoc(cua_so[:j])
            elif x == "TRANG" and so_tr is None:
                so_tr = _so_dung_truoc(cua_so[:j])
                break
        if so_to or so_tr:
            return so_to, so_tr
    return None, None


# ---------- Trang scan trùng ----------
def ma_anh(page) -> str:
    """Mã hình ảnh 256 bit (dHash) của trang, để so trang ít chữ (trang ký, lời chứng ngắn)."""
    pix = page.get_pixmap(dpi=24, colorspace=pymupdf.csGRAY, alpha=False)
    img = Image.frombuffer("L", (pix.width, pix.height), pix.samples, "raw", "L", pix.stride, 1).resize((17, 16))
    px = img.tobytes()  # ảnh xám: mỗi điểm 1 byte
    bit = "".join("1" if px[r * 17 + c] > px[r * 17 + c + 1] else "0" for r in range(16) for c in range(16))
    return "%064x" % int(bit, 2)


def _cac_dieu(text: str) -> list[int]:
    return [int(m.group(1)) for dong in text.splitlines() for m in [M_DIEU_DAU_DONG.match(bo_dau(dong))] if m]


def _giong_het(a: dict, b: dict) -> bool:
    import difflib
    ta, tb = bo_dau(a.get("text", "")), bo_dau(b.get("text", ""))
    if min(len(ta), len(tb)) > 200:
        sm = difflib.SequenceMatcher(None, ta, tb, autojunk=False)
        return sm.quick_ratio() > 0.95 and sm.ratio() > 0.93
    ha, hb = a.get("ma_anh"), b.get("ma_anh")
    if not ha or not hb or bin(int(ha, 16) ^ int(hb, 16)).count("1") > 12:
        return False
    if max(len(ta), len(tb)) > 30:  # trang có ít chữ thì chữ cũng phải gần như giống
        return difflib.SequenceMatcher(None, ta, tb, autojunk=False).ratio() > 0.85
    return True


def tim_trang_trung(doc: list[dict], trang: list[dict]) -> dict[int, int]:
    """Trang bị scan 2 lần liền nhau (bỏ qua trang trắng ở giữa), chỉ xét trang thuộc văn bản (không xét giấy tờ
    hồ sơ: hai bản CCCD giống bố cục là chuyện bình thường). Trả {trang lặp: trang gốc}."""
    trung, truoc = {}, None
    for i, t in enumerate(trang):
        if t["nhan"] == "TT":
            continue
        if truoc is not None and t["nhan"] != "HS" and trang[truoc]["nhan"] != "HS":
            sa, sb = doc[truoc].get("so_in"), doc[i].get("so_in")
            khac = (sa and sb and sa != sb) or _cac_dieu(doc[truoc]["text"]) != _cac_dieu(doc[i]["text"])
            if not khac and _giong_het(doc[truoc], doc[i]):
                trung[i] = trung.get(truoc, truoc)
                continue  # giữ "truoc" là bản gốc nếu bị scan 3 lần
        truoc = i
    return trung


def kiem_tra_trang(d: dict, trang: list[dict], doc: list[dict]) -> tuple[list[str], list[str]]:
    """Trả về (các dấu hiệu nghi thiếu/thừa/trùng trang, các xác nhận đủ trang)."""
    ds = [i for i in sorted(d["trang"]) if trang[i]["nhan"] != "TT"]
    n = len(ds)
    nghi, dat = [], []
    if not ds:
        return nghi, dat

    # 1. Số trang ghi trong lời chứng — dấu hiệu chắc nhất
    chu_lc = " ".join(bo_dau(doc[i]["text"]) for i in ds if trang[i]["nhan"] == "LC")
    so_to, so_tr = so_trang_theo_loi_chung(chu_lc)
    khop_loi_chung = False
    if so_tr:
        if n < so_tr:
            nghi.append(f"lời chứng ghi {so_tr} trang nhưng chỉ tách được {n} trang (thiếu {so_tr - n})")
        elif n > so_tr:
            nghi.append(f"lời chứng ghi {so_tr} trang nhưng tách ra {n} trang (thừa {n - so_tr}: trang trùng hoặc lẫn hồ sơ?)")
        else:
            khop_loi_chung = True
            dat.append(f"đủ {n}/{so_tr} trang theo lời chứng")
    elif so_to:
        if n < so_to:
            nghi.append(f"lời chứng ghi {so_to} tờ nhưng chỉ tách được {n} trang")
        elif n > 2 * so_to:
            nghi.append(f"lời chứng ghi {so_to} tờ nhưng tách ra {n} trang")

    # 2. Số trang in trên từng trang
    biet = [(k, doc[i]["so_in"][0], doc[i]["so_in"][1]) for k, i in enumerate(ds) if doc[i].get("so_in")]
    nhay = []
    for (k1, a, _), (k2, b, _) in zip(biet, biet[1:]):
        if b > a and b - a > k2 - k1:
            mat = [str(x) for x in range(a + 1, b)][: (b - a) - (k2 - k1)] if k2 - k1 == 1 else []
            nhay.append(f"số trang in nhảy từ {a} (tr.{ds[k1]+1}) sang {b} (tr.{ds[k2]+1})"
                        + (f": thiếu trang {', '.join(mat)}" if mat else ""))
    if biet and biet[0][1] > biet[0][0] + 1:
        k, a, _ = biet[0]
        nhay.append(f"trang đầu có số in là {a}: có thể thiếu trang {', '.join(map(str, range(k + 1, a)))} ở đầu văn bản")
    tong = next((t for _, _, t in biet if t), None)
    if tong and not so_tr:
        if n < tong:
            nhay.append(f"số trang in ghi tổng {tong} trang nhưng chỉ tách được {n}")
        elif n == tong:
            dat.append(f"đủ {n}/{tong} trang theo số trang in")

    # 3. Số Điều nhảy cóc giữa hai trang liền nhau
    def cac_dieu(i):
        return [int(m.group(1)) for dong in doc[i]["text"].splitlines()
                for m in [M_DIEU_DAU_DONG.match(bo_dau(dong))] if m]

    truoc_max, truoc_k = None, None
    for k, i in enumerate(ds):
        so_dieu = cac_dieu(i)
        if so_dieu and truoc_max is not None and min(so_dieu) > truoc_max + 1 and min(so_dieu) < 60:
            nhay.append(f"Điều nhảy từ {truoc_max} (tr.{ds[truoc_k]+1}) sang {min(so_dieu)} (tr.{i+1})")
        if so_dieu:
            truoc_max, truoc_k = max(truoc_max or 0, max(so_dieu)), k

    # Lời chứng ghi số trang khớp đúng thì không thể thiếu: bỏ qua các dấu hiệu yếu (có thể do OCR đọc sai số)
    if not khop_loi_chung:
        nghi += nhay

    # 4. Hai trang KHÔNG liền nhau trong văn bản giống hệt (trùng liền nhau đã được bỏ trước khi ghép trang)
    for x in range(n):
        for y in range(x + 2, n):
            if _giong_het(doc[ds[x]], doc[ds[y]]):
                nghi.append(f"tr.{ds[x]+1} và tr.{ds[y]+1} gần như giống hệt (scan trùng?)")
    return nghi, dat


def khoa_cache(p: Path, cfg) -> str:
    st = p.stat()
    s = f"v2|{p.resolve()}|{st.st_size}|{st.st_mtime_ns}|{cfg['engine']}|{cfg['dpi']}|{cfg['lang']}|{cfg['luon_ocr']}"
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


# ---------- Đặt tên file kết quả theo mẫu ----------
TRUONG_TEN = {
    "ten": "tên file gốc",
    "so_cc": "số công chứng",
    "nam": "năm công chứng",
    "ngay": "ngày công chứng (năm-tháng-ngày)",
    "loai": "loại văn bản (tiêu đề, không dấu)",
    "stt": "số thứ tự văn bản trong file",
}
_KY_TU_CAM = re.compile(r'[<>:"/\\|?*\x00-\x1f]+')


def so_cc_de_dat_ten(so_tho: list[str], so_cc: set[str], rel: str) -> str:
    """Ưu tiên con số trong tên file nếu khớp số đọc được (OCR hay sai 1 chữ số), không thì lấy số OCR."""
    trong_ten = re.findall(r"\d{3,8}", rel.rsplit(".", 1)[0])
    for tho in trong_ten:  # khớp đúng trước (file có 1234_1235: văn bản số 1235 phải ra 1235, không phải 1234)
        if _chuan_so(tho) in so_cc:
            return tho
    for tho in trong_ten:  # rồi mới tới khớp lệch 1 chữ số
        if any(_gan_giong(_chuan_so(tho), x) for x in so_cc):
            return tho
    return min(so_tho, key=len) if so_tho else ""


def gia_tri_ten(rel: str, so_cc: str = "", ngay=None, loai: str = "", stt: int = 1) -> dict:
    y, m, d = ngay if ngay else (0, 0, 0)
    loai = re.sub(r"\s+", "_", bo_dau(loai))
    if len(loai) > 40:
        loai = loai[:40].rsplit("_", 1)[0]
    return dict(ten=Path(rel).stem, so_cc=so_cc or "", nam=str(y) if y else "",
                ngay=f"{y:04d}-{m:02d}-{d:02d}" if (y and m and d) else "", loai=loai, stt=str(stt))


def kiem_tra_mau_ten(mau: str) -> str | None:
    """Trả về thông báo lỗi nếu mẫu tên không hợp lệ, None nếu hợp lệ."""
    if not mau or not mau.strip():
        return "Mẫu tên đang để trống."
    la = [t for t in re.findall(r"\{(\w+)\}", mau) if t not in TRUONG_TEN]
    if la:
        return "Không hiểu: " + ", ".join("{" + t + "}" for t in la)
    if re.search(r"[{}]", re.sub(r"\{\w+\}", "", mau)):
        return "Dấu ngoặc { } chưa đóng/mở đúng."
    if not re.search(r"\{\w+\}", mau):
        return "Mẫu cần có ít nhất một trường, vd {ten} hoặc {so_cc}."
    return None


def dat_ten(mau: str, gt: dict, so_vb: int = 1) -> str | None:
    """Áp mẫu tên. Trả None nếu mẫu dùng trường không có giá trị (vd chưa đọc được số CC)."""
    if kiem_tra_mau_ten(mau):
        return None
    truong = re.findall(r"\{(\w+)\}", mau)
    if any(not gt.get(t) for t in truong):
        return None
    ten = re.sub(r"\{(\w+)\}", lambda m: gt[m.group(1)], mau)
    if so_vb > 1 and "stt" not in truong:
        ten += f"__vb{gt['stt']}"
    ten = _KY_TU_CAM.sub("_", ten).strip(" ._-")
    ten = re.sub(r"_{2,}(?!vb)", "_", ten)
    return ten or None


def duong_dan_theo_mau(rel: str, mau: str, gt: dict, so_vb: int) -> tuple[str, bool]:
    """Đường dẫn tương đối (giữ thư mục con của file gốc). Trả (đường dẫn, có_phải_quay_về_tên_gốc)."""
    thu_muc = rel.rsplit("/", 1)[0] + "/" if "/" in rel else ""
    ten = dat_ten(mau, gt, so_vb)
    quay_ve = ten is None
    if quay_ve:
        ten = dat_ten("{ten}", gt, so_vb)
    return f"{thu_muc}{ten}.pdf", quay_ve


class BoTenDuyNhat:
    """Tránh hai file kết quả trùng tên trong cùng một lần chạy: thêm (2), (3)…"""

    def __init__(self):
        self.da_dung = set()

    def lay(self, duong_dan: str) -> str:
        goc, duoi = duong_dan.rsplit(".", 1)
        ung_vien, k = duong_dan, 1
        while ung_vien.lower() in self.da_dung:
            k += 1
            ung_vien = f"{goc} ({k}).{duoi}"
        self.da_dung.add(ung_vien.lower())
        return ung_vien


def ten_dau_ra(rel: str, so_vb: int, k: int) -> str:
    goc = rel[:-4] if rel.lower().endswith(".pdf") else rel
    return f"{goc}.pdf" if so_vb == 1 else f"{goc}__vb{k+1}.pdf"


def xu_ly_file(duong_dan: str, rel: str, cfg: dict) -> dict:
    t0 = time.time()
    p = Path(duong_dan)
    ra = Path(cfg["ra"])
    kq = dict(duong_dan=rel, goc=p.resolve().as_uri(), so_trang=0, trang_van_ban="", trang_thai="LOI", canh_bao="",
              nghi_thieu_trang="", so_cong_chung="", ngay_cong_chung="", loai_van_ban="", file_van_ban="",
              thong_tin="", doi_ten=[],
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
        if any("ma_anh" not in d for d in doc):  # cache cũ chưa có mã ảnh: tính bổ sung (nhanh) rồi lưu lại
            for i, d in enumerate(doc):
                if "ma_anh" not in d:
                    d["ma_anh"] = ma_anh(src[i]) if d["nguon"] != "trang" else None
            f_cache.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
        trang = [phan_tich_trang(d["text"], d["muc"], cfg["nguong_trang"]) for d in doc]
        trung = tim_trang_trung(doc, trang)
        for j, i in trung.items():  # trang scan lặp: coi như trang trắng khi ghép văn bản
            trang[j].update(nhan="TT", trung=i, ly_do=f"trùng tr.{i+1} (scan 2 lần)")
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
                d["trang"] = sorted(set(d["trang"]) | {i for i in range(a, b + 1)
                                                       if trang[i]["nhan"] == "TT" and "trung" not in trang[i]})
        # kiểm tra thiếu / thừa / trùng trang trong từng văn bản đã tách
        trong_doan = {x for d in doan if d["trang"] for x in range(min(d["trang"]), max(d["trang"]) + 1)}
        nghi_thieu = [f"tr.{j+1} trùng tr.{i+1} (scan 2 lần), đã bỏ khỏi văn bản"
                      for j, i in sorted(trung.items()) if i in trong_doan or j in trong_doan]
        for k, d in enumerate(doan):
            tien_to = f"VB{k+1}: " if len(doan) > 1 else ""
            nghi, dat = kiem_tra_trang(d, trang, doc)
            nghi_thieu += [tien_to + x for x in nghi]
            thong_tin += [tien_to + x for x in dat]
        canh_bao += ["số trang: " + x for x in nghi_thieu]
        so_trang_trang = sum(t["nhan"] == "TT" and "trung" not in t for t in trang)
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
            nghi_thieu_trang=" | ".join(nghi_thieu),
            so_cong_chung="; ".join(so_cc_de_dat_ten(x["so_tho"], x["so_cc"], rel) for x in info).strip("; "),
            ngay_cong_chung="; ".join((f"{x['ngay'][2]:02d}/{x['ngay'][1]:02d}/{x['ngay'][0]}" if x["ngay"] and x["ngay"][1]
                                       else (str(x["ngay"][0]) if x["ngay"] else "")) for x in info).strip("; "),
            loai_van_ban="; ".join(x["loai"] for x in info).strip("; "),
            thong_tin=" · ".join(thong_tin),
            nhan_trang=" ".join(f"{i+1}:{t['nhan']}" for i, t in enumerate(trang)),
            chi_tiet=[dict(nhan="TR" if "trung" in t else t["nhan"], ly_do=t["ly_do"], vb=trong_vb.get(i, 0))
                      for i, t in enumerate(trang)],
        )
        # --- xuất PDF (tên theo mẫu được đặt ở tiến trình chính, để tránh trùng tên giữa các file) ---
        thu_muc = "dat" if trang_thai == "DAT" else "can_kiem_tra"
        mau_vb, mau_hs = cfg.get("mau_ten_vb") or "{ten}", cfg.get("mau_ten_hs") or "{ten}"
        ten_ra, quay_ve = [], False
        for k, (d, x) in enumerate(zip(doan, info)):
            dich = ra / thu_muc / ten_dau_ra(rel, len(doan), k)
            ghi_pdf(src, d["trang"], dich)
            gt = gia_tri_ten(rel, so_cc_de_dat_ten(x["so_tho"], x["so_cc"], rel), x["ngay"], x["loai"], k + 1)
            moi, qv = duong_dan_theo_mau(rel, mau_vb, gt, len(doan))
            quay_ve |= qv
            kq["doi_ten"].append([dich.relative_to(ra).as_posix(), f"{thu_muc}/{moi}"])
            ten_ra.append(moi.rsplit("/", 1)[-1])
        if cfg["xuat_ho_so"]:
            con_lai = [i for i in range(n) if i not in trong_vb]
            if cfg.get("bo_trang_trang_ho_so", True):
                trang_trang = [i for i in con_lai if trang[i]["nhan"] == "TT" and "trung" not in trang[i]]
                con_lai = [i for i in con_lai if i not in trang_trang]
                if trang_trang:
                    thong_tin.append(f"bỏ {len(trang_trang)} trang trắng khỏi hồ sơ")
                    kq["thong_tin"] = " · ".join(thong_tin)
            if con_lai:
                ghi_pdf(src, con_lai, ra / "ho_so" / rel)
                x = info[0] if info else dict(so_tho=[], so_cc=set(), ngay=None, loai="")
                gt = gia_tri_ten(rel, so_cc_de_dat_ten(x["so_tho"], x["so_cc"], rel), x["ngay"], x["loai"], 1)
                moi, _ = duong_dan_theo_mau(rel, mau_hs, gt, 1)
                kq["doi_ten"].append([f"ho_so/{rel}", f"ho_so/{moi}"])
        if quay_ve and mau_vb != "{ten}":
            thong_tin.append("thiếu số/ngày/loại để đặt tên theo mẫu: giữ tên gốc")
            kq["thong_tin"] = " · ".join(thong_tin)
        kq["file_van_ban"] = "; ".join(ten_ra)
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

COT_CSV = ["duong_dan", "so_trang", "trang_van_ban", "trang_thai", "nghi_thieu_trang", "so_cong_chung",
           "ngay_cong_chung", "loai_van_ban", "file_van_ban", "canh_bao", "thong_tin", "nhan_trang", "thoi_gian"]
COT_CHU = {"trang_van_ban", "so_cong_chung", "ngay_cong_chung"}   # để dạng Text trong Excel (giữ số 0 đầu, không thành ngày)
RONG_COT = {"duong_dan": 42, "so_trang": 8, "trang_van_ban": 16, "trang_thai": 15, "nghi_thieu_trang": 40,
            "so_cong_chung": 14, "ngay_cong_chung": 14, "loai_van_ban": 34, "file_van_ban": 34, "canh_bao": 60,
            "thong_tin": 40, "nhan_trang": 50, "thoi_gian": 8}
THU_TU = {"LOI": 0, "KHONG_THAY": 1, "CAN_KIEM_TRA": 2, "DAT": 3}
MAU_NHAN = {"MD": "#2563eb", "TH": "#60a5fa", "LC": "#16a34a", "HS": "#9ca3af", "TT": "#e5e7eb", "KR": "#f59e0b",
            "TR": "#a855f7"}
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
    from openpyxl.utils import get_column_letter
    nen = {"DAT": "DCFCE7", "CAN_KIEM_TRA": "FEF3C7", "KHONG_THAY": "FEE2E2", "LOI": "FECACA"}
    cot_chu = [COT_CSV.index(c) + 1 for c in COT_CHU]
    cot_tt = COT_CSV.index("trang_thai") + 1
    for r in sorted(ds, key=lambda r: (THU_TU.get(r["trang_thai"], 9), r["duong_dan"])):
        ws.append([r.get(k, "") for k in COT_CSV])
        hang = ws.max_row
        for c in cot_chu:
            ws.cell(hang, c).number_format = "@"
        ws.cell(hang, cot_tt).fill = PatternFill("solid", fgColor=nen.get(r["trang_thai"], "FFFFFF"))
    for hang in range(ws.max_row + 1, ws.max_row + 200):
        for c in cot_chu:
            ws.cell(hang, c).number_format = "@"
    for k, ten in enumerate(COT_CSV, 1):
        ws.column_dimensions[get_column_letter(k)].width = RONG_COT.get(ten, 15)
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
        the.append(f'''<section data-tt="{r["trang_thai"]}" data-thieu="{1 if r.get("nghi_thieu_trang") else 0}">
<h3><span class="tt" style="background:{MAU_TT.get(r["trang_thai"], "#000")}">{r["trang_thai"]}</span> {e(r["duong_dan"])}</h3>
<p>Trang văn bản: <b>{e(r["trang_van_ban"] or "—")}</b> / {r["so_trang"]} trang · {e(r["thong_tin"])}</p>
{f'<p class="thieu">📄 Số trang: {e(r["nghi_thieu_trang"])}</p>' if r.get("nghi_thieu_trang") else ""}
{f'<p class="cb">⚠ {e(r["canh_bao"])}</p>' if r["canh_bao"] else ""}
<div class="luoi">{"".join(o)}</div></section>''')
    nut = "".join(f'<button onclick="loc(\'{k}\')">{k} ({v})</button>' for k, v in dem.items() if v)
    so_thieu = sum(1 for r in ds if r.get("nghi_thieu_trang"))
    if so_thieu:
        nut += f'<button onclick="loc(\'THIEU\')">Nghi thiếu/thừa trang ({so_thieu})</button>'

    f.write_text(f'''<!DOCTYPE html><html lang="vi"><head><meta charset="utf-8"><title>Xem lại tách văn bản</title>
<style>
body{{font:14px system-ui,sans-serif;margin:20px;color:#111;background:#fafafa}}
section{{background:#fff;border:1px solid #ddd;border-radius:8px;padding:12px 16px;margin:14px 0}}
h3{{margin:0 0 6px;font-size:15px}} p{{margin:4px 0}} .cb{{color:#b45309}} .thieu{{color:#b91c1c;font-weight:600}}
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
<script>function loc(t){{document.querySelectorAll('section').forEach(s=>s.style.display=(!t||s.dataset.tt==t||(t=='THIEU'&&s.dataset.thieu=='1'))?'':'none')}}</script>
</body></html>''', encoding="utf-8")


# =====================================================================
# 6. CHẾ ĐỘ CẮT LẠI THEO CSV ĐÃ SỬA
# =====================================================================

def trang_trang_cua_file(src, p: Path, ra: Path, cfg: dict) -> set[int]:
    """Các trang trắng của 1 file khi cắt bản chốt (không OCR lại): ưu tiên kết quả đã lưu trong .cache,
    không có thì đo lượng mực trên trang."""
    nguong = cfg.get("nguong_trang", 0.002)
    try:
        f_cache = ra / ".cache" / f"{khoa_cache(p, dict(cfg_mac_dinh(), **cfg))}.json"
        doc = json.loads(f_cache.read_text(encoding="utf-8"))
        if len(doc) == src.page_count:
            return {i for i, d in enumerate(doc)
                    if phan_tich_trang(d["text"], d["muc"], nguong)["nhan"] == "TT"}
    except (OSError, ValueError, KeyError):
        pass
    kq = set()
    for i in range(src.page_count):
        pix = src[i].get_pixmap(dpi=cfg.get("dpi", 200), colorspace=pymupdf.csGRAY, alpha=False)
        img = Image.frombuffer("L", (pix.width, pix.height), pix.samples, "raw", "L", pix.stride, 1)
        if muc_muc(img) < nguong:
            kq.add(i)
    return kq


def _doc_ngay_bang(s: str):
    s = (s or "").strip()
    m = re.fullmatch(r"(\d{1,2})[/.-](\d{1,2})[/.-](\d{4})", s)
    if m:
        return int(m.group(3)), int(m.group(2)), int(m.group(1))
    m = re.search(r"(19|20)\d{2}", s)
    return (int(m.group(0)), 0, 0) if m else None


def cat_theo_bang(vao, ra, f_bang, log=print, cfg: dict | None = None) -> int:
    """Cắt PDF theo cột trang_van_ban của bảng đã sửa tay, đặt tên theo mẫu (dùng số CC/ngày/loại trong bảng,
    kể cả khi đã sửa tay). Văn bản vào thư mục chot/, phần hồ sơ còn lại (nếu chọn) vào chot_ho_so/."""
    cfg = cfg or {}
    mau_vb, mau_hs = cfg.get("mau_ten_vb") or "{ten}", cfg.get("mau_ten_hs") or "{ten}"
    vao, ra, f_bang = Path(vao), Path(ra), Path(f_bang)
    dich_goc, dich_hs = ra / "chot", ra / "chot_ho_so"
    if dich_goc.exists() and any(dich_goc.rglob("*.pdf")):
        log(f"Lưu ý: {dich_goc} đã có file từ lần trước; file trùng tên sẽ bị ghi đè, file khác giữ nguyên.")
    bo_ten, bo_ten_hs = BoTenDuyNhat(), BoTenDuyNhat()
    n_ok = n_bo = n_ten_goc = n_trang_trang = 0
    for r in sorted(doc_bang(f_bang), key=lambda r: (r.get("duong_dan") or "")):
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
            tach = lambda cot: [x.strip() for x in str(r.get(cot) or "").split(";")]  # noqa: E731
            so_l, ngay_l, loai_l = tach("so_cong_chung"), tach("ngay_cong_chung"), tach("loai_van_ban")
            lay = lambda l, k: l[k] if k < len(l) else (l[0] if len(l) == 1 else "")  # noqa: E731
            for k, d in enumerate(ds):
                gt = gia_tri_ten(rel, lay(so_l, k), _doc_ngay_bang(lay(ngay_l, k)), lay(loai_l, k), k + 1)
                moi, qv = duong_dan_theo_mau(rel, mau_vb, gt, len(ds))
                n_ten_goc += qv and mau_vb != "{ten}"
                ghi_pdf(src, d, dich_goc / bo_ten.lay(moi))
            if cfg.get("xuat_ho_so"):
                trong = {x for d in ds for x in d}
                con_lai = [i for i in range(src.page_count) if i not in trong]
                if cfg.get("bo_trang_trang_ho_so", True) and con_lai:
                    trang_trang = trang_trang_cua_file(src, src_p, ra, cfg)
                    n_trang_trang += sum(1 for i in con_lai if i in trang_trang)
                    con_lai = [i for i in con_lai if i not in trang_trang]
                if con_lai:
                    gt = gia_tri_ten(rel, lay(so_l, 0), _doc_ngay_bang(lay(ngay_l, 0)), lay(loai_l, 0), 1)
                    moi, _ = duong_dan_theo_mau(rel, mau_hs, gt, 1)
                    ghi_pdf(src, con_lai, dich_hs / bo_ten_hs.lay(moi))
            src.close()
            n_ok += 1
        except Exception as e:
            log(f"  LỖI {rel}: {e}")
    log(f"Đã cắt {n_ok} file vào {dich_goc}" + (f" (hồ sơ: {dich_hs})" if cfg.get("xuat_ho_so") else "")
        + f" · bỏ qua {n_bo} dòng trống/BO.")
    if n_trang_trang:
        log(f"  Đã bỏ {n_trang_trang} trang trắng khỏi phần hồ sơ.")
    if n_ten_goc:
        log(f"  {n_ten_goc} văn bản thiếu số/ngày/loại để đặt tên theo mẫu nên giữ tên gốc "
            "(điền vào cột so_cong_chung / ngay_cong_chung / loai_van_ban rồi cắt lại).")
    return n_ok


# =====================================================================
# 7. CHẠY (dùng chung cho dòng lệnh và giao diện)
# =====================================================================

def doi_ten_ket_qua(kq: list[dict], ra: Path, log=print):
    """Đổi tên file kết quả theo mẫu, xử lý trùng tên. Hai bước qua tên tạm để không ghi đè nhầm file khác."""
    bo_ten = BoTenDuyNhat()
    viec = []
    for r in sorted(kq, key=lambda r: r["duong_dan"]):
        moi_cua_file = []
        for cu, moi in r.get("doi_ten", []):
            moi = bo_ten.lay(moi)
            viec.append((cu, moi))
            if not moi.startswith("ho_so/"):
                moi_cua_file.append(moi)
        if moi_cua_file:
            r["van_ban"] = moi_cua_file
            r["file_van_ban"] = "; ".join(m.rsplit("/", 1)[-1] for m in moi_cua_file)
    viec = [(cu, moi) for cu, moi in viec if cu != moi and (ra / cu).exists()]
    tam = []
    for k, (cu, moi) in enumerate(viec):
        t = ra / f"{cu}.doi_ten_{k}.tmp"
        os.replace(ra / cu, t)
        tam.append((t, moi))
    for t, moi in tam:
        (ra / moi).parent.mkdir(parents=True, exist_ok=True)
        os.replace(t, ra / moi)
    if viec:
        log(f"Đã đặt tên {len(viec)} file theo mẫu.")


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
        mau_ten_vb="{ten}",        # mẫu tên file văn bản, vd "{nam}_{so_cc}_{loai}"
        mau_ten_hs="{ten}",        # mẫu tên file hồ sơ còn lại (thư mục ho_so), vd "{ten}_HS"
        xem_tat_ca=False, xuat_ho_so=False, luu_chu=False, dpi_anh=40, debug=False,
        bo_trang_trang_ho_so=True,  # bỏ trang trắng khỏi phần hồ sơ (văn bản thì mặc định đã bỏ)
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
KHO_GITHUB = "phamngocson6596/tach-file-hoso"
URL_KHO = f"https://github.com/{KHO_GITHUB}"


def _so_phien_ban(s: str) -> tuple:
    return tuple(int(x) for x in re.findall(r"\d+", s or "")[:4])


def la_ban_cai() -> bool:
    """Đang chạy từ bản cài bằng bộ cài (có trình gỡ cài đặt cạnh file .exe)."""
    return getattr(sys, "frozen", False) and (thu_muc_ung_dung() / "unins000.exe").exists()


def kiem_tra_ban_moi(timeout: float = 6) -> dict | None:
    """Hỏi GitHub số phiên bản của bản phát hành mới nhất. Chỉ gửi đúng yêu cầu này, không gửi dữ liệu nào khác.
    Trả về thông tin bản mới nếu mới hơn bản đang dùng, None nếu đang là bản mới nhất. Lỗi mạng thì ném lỗi."""
    import urllib.request
    yc = urllib.request.Request(f"https://api.github.com/repos/{KHO_GITHUB}/releases/latest",
                                headers={"User-Agent": f"TachVanBan/{PHIEN_BAN}",
                                         "Accept": "application/vnd.github+json"})
    with urllib.request.urlopen(yc, timeout=timeout) as r:
        d = json.loads(r.read().decode("utf-8"))
    tag = d.get("tag_name") or ""
    if not _so_phien_ban(tag) or _so_phien_ban(tag) <= _so_phien_ban(PHIEN_BAN):
        return None
    tai = {a.get("name"): a.get("browser_download_url") for a in d.get("assets", [])}
    return dict(phien_ban=tag.lstrip("vV"), trang=d.get("html_url") or f"{URL_KHO}/releases/latest",
                tai_cai_dat=tai.get("TachVanBan-CaiDat.exe"), tai_zip=tai.get("TachVanBan-KhongCanCai.zip"))


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
        doi_ten_ket_qua(kq, ra, log)
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
    g.add_argument("--ten-van-ban", default=md["mau_ten_vb"],
                   help="mẫu tên file văn bản; trường: " + ", ".join("{%s} %s" % kv for kv in TRUONG_TEN.items()))
    g.add_argument("--ten-ho-so", default=md["mau_ten_hs"], help="mẫu tên file hồ sơ còn lại, vd {ten}_HS")
    g.add_argument("--giu-trang-trang-ho-so", action="store_true", help="giữ trang trắng trong phần hồ sơ (mặc định bỏ)")
    g.add_argument("--luu-chu", action="store_true", help="lưu chữ OCR từng file vào chu_ocr/ (để dò lỗi)")
    g.add_argument("--theo-bang", "--theo-csv", dest="theo_bang",
                   help="bỏ qua OCR, cắt PDF theo cột trang_van_ban trong bao_cao.xlsx/.csv đã sửa")
    g.add_argument("--debug", action="store_true")
    a = ap.parse_args()

    for mau in (a.ten_van_ban, a.ten_ho_so):
        loi = kiem_tra_mau_ten(mau)
        if loi:
            sys.exit(f"Mẫu tên '{mau}' không hợp lệ: {loi}")
    if a.theo_bang:
        cat_theo_bang(a.vao, a.ra, a.theo_bang,
                      cfg=dict(mau_ten_vb=a.ten_van_ban, mau_ten_hs=a.ten_ho_so, xuat_ho_so=a.xuat_ho_so,
                               bo_trang_trang_ho_so=not a.giu_trang_trang_ho_so, dpi=a.dpi, lang=a.lang,
                               engine=a.engine, luon_ocr=a.luon_ocr, nguong_trang=a.nguong_trang))
        return
    cfg = dict(md, mau_ten_vb=a.ten_van_ban, mau_ten_hs=a.ten_ho_so, bo_trang_trang_ho_so=not a.giu_trang_trang_ho_so, mot_van_ban=not a.nhieu_van_ban, vi_tri=a.vi_tri, so_cc_trong_ten=a.so_cc_trong_ten,
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
