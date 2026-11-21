"""Lớp 2 - "chuẩn hoá": từ lớp nguyên văn sinh ra các trường app dùng, theo từ điển nhãn (tu_dien_nhan.json).

Mỗi giá trị là một object: {gia_tri, nguyen_van, nguon, trang_thai, ghi_chu?}
  trang_thai: doc_duoc | can_xac_nhan (viết tay, đoán, hoặc kiểm tra không khớp) | da_xac_nhan (người duyệt)
Trường không có trên giấy thì không có trong kết quả (không phải lỗi). Nhãn không có trong từ điển
không bị bỏ: vẫn nằm ở lớp nguyên văn và được liệt kê ở "chua_phan_loai".
"""
from __future__ import annotations

import difflib
import json
import re
from datetime import date
from pathlib import Path

from .doc_khung import bo_dau
from .doc_so import chu_thanh_so, so_viet

SCHEMA_VERSION = "0.1"
_TU_DIEN_MAC_DINH = Path(__file__).with_name("tu_dien_nhan.json")
_NGUONG_GIONG = 0.82
_O_TRONG = re.compile(r"^\W*-\W?\w?\W?-\W*$|^-+$")  # "-/-", "-l-", "-Í-": ô bỏ trống trên giấy


def nap_tu_dien(duong_dan: Path | None = None) -> dict:
    return json.loads(Path(duong_dan or _TU_DIEN_MAC_DINH).read_text(encoding="utf-8"))


def _chuan_nhan(s: str) -> str:
    return " ".join(re.sub(r"[^\w\s]", " ", bo_dau(s)).split())


def khop(nhan: str, bang: dict[str, list[str]]) -> str | None:
    """Tên trường chuẩn cho một nhãn in trên giấy, hoặc None. So bỏ dấu, chịu lỗi OCR nhẹ."""
    n = _chuan_nhan(nhan)
    tot, ten_tot = 0.0, None
    for ten, ds in bang.items():
        for a in ds:
            tien_to = a.endswith("*")
            c = _chuan_nhan(a.rstrip("*"))
            if tien_to:
                diem = 1.0 if n.startswith(c) else 0.0
            elif len(c) <= 3:  # nhãn rất ngắn ("Ông", "Bà"): phải khớp đúng
                diem = 1.0 if n == c else 0.0
            else:
                diem = 1.0 if n == c else difflib.SequenceMatcher(None, n, c).ratio()
            if diem > tot:
                tot, ten_tot = diem, ten
    return ten_tot if tot >= _NGUONG_GIONG else None


def _gt(gia_tri, nguyen_van, nguon, trang_thai="doc_duoc", ghi_chu=None) -> dict:
    d = dict(gia_tri=gia_tri, nguyen_van=nguyen_van, nguon=nguon, trang_thai=trang_thai)
    if ghi_chu:
        d["ghi_chu"] = ghi_chu
    return d


def chuan_hoa(nguyen_van: list[dict], tu_dien: dict | None = None, ma_vach: list[str] | None = None) -> dict:
    td = tu_dien or nap_tu_dien()
    kq = dict(giay={}, chu=[], thua=[], nha_o=[], cong_trinh=[], ghi_chu=[], bien_dong=dict(co_noi_dung=False),
              chua_phan_loai=[])
    kiem_tra: list[dict] = []

    for muc in nguyen_van:
        loai = _loai_muc(muc, td)
        if loai == "nguoi":
            _doc_nguoi(muc, td, kq)
        elif loai == "thua":
            _doc_thua(muc, td, kq)
        elif loai in ("nha_o", "cong_trinh"):
            _doc_tai_san(muc, loai, td, kq, kiem_tra)
        elif loai == "ghi_chu":
            _doc_ghi_chu(muc, td, kq)
        elif loai == "bien_dong" or muc["ma"] == "BD":
            _doc_bien_dong(muc, kq)
        elif muc["ma"] == "KY":
            _doc_khoi_ky(muc, kq)
            _doc_truong_giay(muc, td, kq)
        elif loai in ("rung", "cay_lau_nam"):
            gt = [t["gia_tri"] for p in muc["noi_dung"] if p["kieu"] == "ban_ghi" for t in p["truong"]]
            if any(not _O_TRONG.match(g) for g in gt):
                kq[loai] = _gt("; ".join(gt), "; ".join(gt), dict(trang=muc["trang"]))
        else:
            _doc_truong_giay(muc, td, kq)
        for p in muc["noi_dung"]:  # số phát hành / số in dưới mã vạch có thể ở bất kỳ mục nào
            if p["kieu"] == "so_phat_hanh" and "so_phat_hanh" not in kq["giay"]:
                kq["giay"]["so_phat_hanh"] = _gt(re.sub(r"\s+", " ", p["gia_tri"]), p["gia_tri"], p["nguon"])
            if p["kieu"] == "so_ma_vach_in":
                kq["giay"]["so_ma_vach_in"] = _gt(p["gia_tri"], p["gia_tri"], p["nguon"])

    if ma_vach:
        kq["giay"]["ma_vach"] = _gt(ma_vach[0], ma_vach[0], dict(nguon="giai_ma_vach"))

    _kiem_tra(kq, kiem_tra)
    return dict(chuan_hoa={k: v for k, v in kq.items() if k != "chua_phan_loai"},
                chua_phan_loai=kq["chua_phan_loai"], kiem_tra=kiem_tra)


def _loai_muc(muc: dict, td: dict) -> str | None:
    if muc["ma"] in ("DAU", "KY", "BD"):
        return None
    return khop(muc["tieu_de"], td["muc"])


def _ban_ghi(muc: dict):
    """(nhãn, giá trị, nguồn) theo thứ tự trên giấy."""
    for p in muc["noi_dung"]:
        if p["kieu"] == "ban_ghi":
            for t in p["truong"]:
                yield t["nhan"], t["gia_tri"], p["nguon"]


def _chua_phan_loai(kq: dict, muc: dict, nhan, gia_tri, nguon):
    kq["chua_phan_loai"].append(dict(muc=muc["ma"], tieu_de_muc=muc["tieu_de"], nhan=nhan, gia_tri=gia_tri,
                                     nguon=nguon))


def _doc_truong_giay(muc: dict, td: dict, kq: dict) -> bool:
    """Các trường của bản thân tờ giấy (số vào sổ…) có thể nằm ở mục bất kỳ."""
    co = False
    for nhan, gia_tri, nguon in _ban_ghi(muc):
        ten = khop(nhan, td["truong"]["giay"]) if nhan else None
        if ten == "so_vao_so":
            kq["giay"]["so_vao_so"] = _gt(gia_tri, gia_tri, nguon, "can_xac_nhan", "thường viết tay")
            co = True
    return co


def _doc_nguoi(muc: dict, td: dict, kq: dict):
    bang = td["truong"]["nguoi"]
    nguoi = None
    for nhan, gia_tri, nguon in _ban_ghi(muc):
        ten = khop(nhan, bang) if nhan else None
        if ten == "ho_ten":
            nguoi = dict(vai=nhan, ho_ten=_gt(gia_tri, gia_tri, nguon))
            kq["chu"].append(nguoi)
            continue
        if ten is None:
            if not _la_truong_giay(nhan, gia_tri, nguon, td, kq):
                _chua_phan_loai(kq, muc, nhan, gia_tri, nguon)
            continue
        if nguoi is None:  # thông tin trước tên người: vẫn giữ, gắn vào một người chưa rõ tên
            nguoi = dict(vai=None)
            kq["chu"].append(nguoi)
        if ten == "giay_to":
            so = re.sub(r"[\s.]", "", gia_tri)
            nguoi["giay_to"] = _gt(dict(loai=_loai_giay_to(nhan), so=so), gia_tri, nguon)
        elif ten == "nam_sinh":
            m = re.search(r"\d{4}", gia_tri)
            nguoi["nam_sinh"] = _gt(int(m.group()) if m else None, gia_tri, nguon,
                                    "doc_duoc" if m else "can_xac_nhan")
        else:
            nguoi[ten] = _gt(gia_tri, gia_tri, nguon)


def _loai_giay_to(nhan: str) -> str:
    n = bo_dau(nhan)
    if "ho chieu" in n:
        return "Hộ chiếu"
    if "cmnd" in n or "chung minh" in n:
        return "CMND"
    if "dinh danh" in n:
        return "Số định danh"
    if "doanh nghiep" in n:
        return "Mã số doanh nghiệp"
    if "the can cuoc" in n or n.startswith("can cuoc so"):
        return "Thẻ căn cước"
    return "CCCD"


def _la_truong_giay(nhan, gia_tri, nguon, td, kq) -> bool:
    if nhan and khop(nhan, td["truong"]["giay"]) == "so_vao_so":
        kq["giay"]["so_vao_so"] = _gt(gia_tri, gia_tri, nguon, "can_xac_nhan", "thường viết tay")
        return True
    return False


def _doc_thua(muc: dict, td: dict, kq: dict):
    bang = td["truong"]["thua"]
    thua = None
    for nhan, gia_tri, nguon in _ban_ghi(muc):
        ten = khop(nhan, bang) if nhan else None
        if ten == "so_thua" or thua is None:
            thua = dict(muc_dich=[])
            kq["thua"].append(thua)
        if ten is None:
            # "Đất ở tại đô thị: 100m²; Đất trồng cây lâu năm: 150m²" -> các phần của mục đích sử dụng
            if nhan and bo_dau(nhan).startswith("dat "):
                thua["muc_dich"].append(_muc_dich(f"{nhan}: {gia_tri}", nguon))
            elif not _la_truong_giay(nhan, gia_tri, nguon, td, kq):
                _chua_phan_loai(kq, muc, nhan, gia_tri, nguon)
            continue
        if ten == "dien_tich":
            thua["dien_tich"] = _dien_tich(gia_tri, nguon)
        elif ten == "muc_dich":
            thua["muc_dich"].extend(_muc_dich(x, nguon) for x in gia_tri.split(";") if x.strip())
        elif ten in ("so_thua", "to_ban_do"):
            so = re.sub(r"\s+", "", gia_tri)
            thua[ten] = _gt(so, gia_tri, nguon, "doc_duoc" if re.fullmatch(r"\d+[a-zA-Z]?", so) else "can_xac_nhan")
        else:
            thua[ten] = _gt(gia_tri, gia_tri, nguon)


def _muc_dich(chu: str, nguon: dict) -> dict:
    loai, _, dt = chu.partition(":")
    d = dict(loai=_gt(loai.strip(), chu.strip(), nguon))
    if dt.strip():
        d["dien_tich"] = _gt(float(so_viet(dt)) if so_viet(dt) is not None else None, dt.strip(), nguon)
    return d


def _dien_tich(gia_tri: str, nguon: dict) -> dict:
    so = so_viet(gia_tri.split("(")[0])
    m = re.search(r"bằng chữ\s*:\s*(?P<chu>[^)]+)", gia_tri, re.IGNORECASE)
    chu = m.group("chu").strip(" ,.") if m else None
    so_tu_chu = chu_thanh_so(chu) if chu else None
    d = _gt(float(so) if so is not None else None, gia_tri, nguon, "doc_duoc" if so is not None else "can_xac_nhan")
    if chu:
        d["bang_chu"] = chu
        d["so_tu_chu"] = float(so_tu_chu) if so_tu_chu is not None else None
    return d


def _doc_tai_san(muc: dict, loai: str, td: dict, kq: dict, kiem_tra: list):
    """Nhà ở / công trình: các dòng "nhãn: giá trị" và/hoặc bảng."""
    bang = td["truong"][loai]
    chung = {}
    for nhan, gia_tri, nguon in _ban_ghi(muc):
        if _O_TRONG.match(gia_tri):
            continue
        ten = khop(nhan, bang) if nhan else None
        if ten:
            chung[ten] = _gt(gia_tri, gia_tri, nguon)
        elif not _la_truong_giay(nhan, gia_tri, nguon, td, kq) and khop(nhan or "", td["muc"]) != loai:
            _chua_phan_loai(kq, muc, nhan, gia_tri, nguon)
    hang = []
    for p in muc["noi_dung"]:
        if p["kieu"] == "bang":
            hang.extend(_doan_bang(p))
    if hang:
        for h in hang:
            kq[loai].append({**{k: v for k, v in chung.items()}, **h})
        kiem_tra.append(dict(ma="bang_doan", muc_do="canh_bao",
                             noi_dung=f"Bảng {muc['tieu_de']} được dựng lại khi chưa có toạ độ chữ: cần xác nhận từng ô."))
    elif chung:
        kq[loai].append(chung)


def _doan_bang(p: dict) -> list[dict]:
    """Đoán hàng của bảng công trình khi OCR trả về các ô thành dòng rời (chưa có toạ độ).

    Bỏ phần tiêu đề cột; giá trị nhận theo kiểu: "-/-", số, "Sở hữu …", "Cấp …", và tên hạng mục.
    Tất cả đánh dấu "can_xac_nhan". Khi đọc được toạ độ (bảng thật) thì thay hàm này.
    """
    dong = p["dong_tho"]
    gia_tri, i = [], 0
    while i < len(dong):
        d = dong[i].strip()
        n = bo_dau(d)
        if _O_TRONG.match(d) or re.fullmatch(r"\d+(?:[.,]\d+)?", d) or re.fullmatch(r"cap\s+\S+", n):
            gia_tri.append(d)
        elif n.startswith("so huu"):
            if n in ("so huu",) and i + 1 < len(dong) and bo_dau(dong[i + 1]).strip() in ("rieng", "chung"):
                d = f"{d} {dong[i + 1].strip()}"
                i += 1
            gia_tri.append(d)
        elif gia_tri or re.search(r"\d", d):  # sau phần tiêu đề: dòng có chữ + số là tên hạng mục
            if re.search(r"[^\W\d]", d) and not n.startswith(("dien tich", "hinh", "thoi", "cong", "trinh")):
                gia_tri.append(("hang_muc", d))
        i += 1
    hang_muc = [g[1] for g in gia_tri if isinstance(g, tuple)]
    o = [g for g in gia_tri if not isinstance(g, tuple)]
    if not hang_muc and not o:
        return []
    nguon = dict(p["nguon"])
    cx = lambda v: _gt(None if _O_TRONG.match(v) else v, v, nguon, "can_xac_nhan", "đoán từ bảng chưa có toạ độ")
    h = {}
    if hang_muc:
        h["hang_muc"] = cx(hang_muc[0])
    cot = ["dien_tich_xay_dung", "dien_tich_san", "hinh_thuc_so_huu", "cap", "thoi_han_so_huu"]
    if len(o) == len(cot):  # đúng số cột của mẫu bảng công trình: gán theo thứ tự cột
        h.update({c: cx(v) for c, v in zip(cot, o)})
    else:  # gán theo kiểu giá trị
        for v in o:
            n = bo_dau(v)
            if n.startswith("so huu"):
                h["hinh_thuc_so_huu"] = cx(v)
            elif n.startswith("cap"):
                h["cap"] = cx(v)
            elif re.fullmatch(r"\d+(?:[.,]\d+)?", v):
                h.setdefault("dien_tich_san", cx(v))
    return [h]


def _doc_ghi_chu(muc: dict, td: dict, kq: dict):
    for p in muc["noi_dung"]:
        if p["kieu"] == "van_ban":
            kq["ghi_chu"].append(_gt(p["noi_dung"], p["noi_dung"], p["nguon"]))
            m = re.search(r"biên nhận số\s*(\d+)", p["noi_dung"], re.IGNORECASE)
            if m:
                kq["giay"]["so_bien_nhan"] = _gt(m.group(1), p["noi_dung"], p["nguon"])
    for nhan, gia_tri, nguon in _ban_ghi(muc):
        if not _la_truong_giay(nhan, gia_tri, nguon, td, kq):
            kq["ghi_chu"].append(_gt(f"{nhan}: {gia_tri}" if nhan else gia_tri, gia_tri, nguon))


# Chữ in sẵn trên trang biến động (không phải nội dung biến động)
_CHU_IN_SAN = ["noi dung thay doi va co so phap ly", "xac nhan cua co quan", "co tham quyen",
               "nguoi duoc cap giay chung nhan khong duoc sua chua tay xoa hoac bo",
               "sung bat ky noi dung nao trong giay chung nhan khi bi mat hoac hu",
               "hong giay chung nhan phai khai bao ngay voi co quan cap giay"]


def _doc_bien_dong(muc: dict, kq: dict):
    dong = []
    for p in muc["noi_dung"]:
        if p["kieu"] == "bang":
            dong.extend(p["dong_tho"])
        elif p["kieu"] == "van_ban":
            dong.append(p["noi_dung"])
        elif p["kieu"] == "ban_ghi":
            dong.append(p["tho"])
    con_lai = []
    for d in dong:
        n = _chuan_nhan(d)
        if not any(difflib.SequenceMatcher(None, n, c).ratio() > 0.8 or n in c for c in _CHU_IN_SAN):
            con_lai.append(d)
    bd = kq["bien_dong"]
    if sum(c.isalpha() for c in " ".join(con_lai)) > 15:
        bd.update(co_noi_dung=True, dong_tho=con_lai, trang_thai="can_xac_nhan",
                  ghi_chu="Có nội dung biến động: kiểm tra chủ hiện tại, thế chấp, chuyển nhượng.")


def _doc_khoi_ky(muc: dict, kq: dict):
    dong = [p for p in muc["noi_dung"] if p["kieu"] == "van_ban"]
    if not dong:
        return
    dau = dong[0]
    m = re.search(r"^(?P<noi>[^,]+),\s*ngày\s*(?P<d>\S{1,3}?)\s*tháng\s*(?P<m>\S{1,3}?)\s*năm\s*(?P<y>\S{2,6})",
                  dau["noi_dung"], re.IGNORECASE)
    if m:
        kq["giay"]["noi_cap"] = _gt(m.group("noi").strip(), dau["noi_dung"], dau["nguon"])
        ngay = _ngay(m.group("d"), m.group("m"), m.group("y"))
        kq["giay"]["ngay_cap"] = _gt(ngay.isoformat() if ngay else None, dau["noi_dung"], dau["nguon"],
                                     "can_xac_nhan", "ngày cấp thường viết tay" + ("" if ngay else "; đọc không ra ngày hợp lệ"))
    for p in dong[1:]:
        n = bo_dau(p["noi_dung"])
        if "co_quan_cap" not in kq["giay"] and p["noi_dung"].isupper() and re.search(
                r"van phong|so tai nguyen|uy ban|ubnd|chi nhanh", n):
            kq["giay"]["co_quan_cap"] = _gt(p["noi_dung"], p["noi_dung"], p["nguon"])
    ten = [p for p in dong if re.fullmatch(r"[A-ZÀ-ỸĐ][a-zà-ỹđ]+(?:\s+[A-ZÀ-ỸĐ][a-zà-ỹđ]+){1,4}", p["noi_dung"])]
    if ten:
        kq["giay"]["nguoi_ky"] = _gt(ten[-1]["noi_dung"], ten[-1]["noi_dung"], ten[-1]["nguon"])


def _ngay(d: str, m: str, y: str) -> date | None:
    try:
        return date(int(y), int(m), int(d))
    except ValueError:
        return None


def _kiem_tra(kq: dict, ds: list):
    def them(ma, muc_do, noi_dung):
        ds.append(dict(ma=ma, muc_do=muc_do, noi_dung=noi_dung))

    if not kq["chu"]:
        them("thieu_chu", "loi", "Không đọc được người sử dụng đất / chủ sở hữu.")
    for i, c in enumerate(kq["chu"], 1):
        ten = c.get("ho_ten", {}).get("gia_tri", f"người thứ {i}")
        gt = c.get("giay_to", {}).get("gia_tri")
        if gt:
            dai = {"CCCD": (12,), "Thẻ căn cước": (12,), "CMND": (9, 12), "Số định danh": (12,)}.get(gt["loai"])
            if dai and (not gt["so"].isdigit() or len(gt["so"]) not in dai):
                them("giay_to_sai_dang", "canh_bao", f"Số {gt['loai']} của {ten} ({gt['so']}) không đúng độ dài.")
                c["giay_to"]["trang_thai"] = "can_xac_nhan"
        ns = c.get("nam_sinh", {}).get("gia_tri")
        if ns and not 1900 <= ns <= date.today().year:
            them("nam_sinh_la", "canh_bao", f"Năm sinh của {ten} ({ns}) bất thường.")
    if not kq["thua"]:
        them("thieu_thua", "loi", "Không đọc được thông tin thửa đất.")
    for i, t in enumerate(kq["thua"], 1):
        for ten in ("so_thua", "to_ban_do", "dien_tich"):
            if ten not in t:
                them(f"thieu_{ten}", "canh_bao", f"Thửa {i}: không đọc được {ten.replace('_', ' ')}.")
            elif t[ten]["trang_thai"] == "can_xac_nhan":
                them(f"{ten}_la", "canh_bao", f"Thửa {i}: {ten.replace('_', ' ')} '{t[ten]['nguyen_van']}' bất thường.")
        dt = t.get("dien_tich")
        if dt and "bang_chu" in dt:
            if dt.get("so_tu_chu") is None:
                them("dien_tich_chu_khong_doc", "canh_bao", f"Thửa {i}: không đọc được diện tích bằng chữ '{dt['bang_chu']}'.")
                dt["trang_thai"] = "can_xac_nhan"
            elif dt["gia_tri"] is not None and abs(dt["so_tu_chu"] - dt["gia_tri"]) > 0.001:
                them("dien_tich_lech", "loi",
                     f"Thửa {i}: diện tích bằng số {dt['gia_tri']} khác bằng chữ {dt['so_tu_chu']} ('{dt['bang_chu']}').")
                dt["trang_thai"] = "can_xac_nhan"
        tong = [m["dien_tich"]["gia_tri"] for m in t["muc_dich"] if m.get("dien_tich", {}).get("gia_tri")]
        if tong and dt and dt["gia_tri"] and abs(sum(tong) - dt["gia_tri"]) > 0.05:
            them("tong_muc_dich_lech", "loi", f"Thửa {i}: tổng diện tích các mục đích {sum(tong)} khác diện tích thửa {dt['gia_tri']}.")
    g = kq["giay"]
    if "so_phat_hanh" not in g:
        them("thieu_so_phat_hanh", "canh_bao", "Không đọc được số phát hành (số seri) của giấy chứng nhận.")
    if "ngay_cap" in g and g["ngay_cap"]["gia_tri"] is None:
        them("ngay_cap_hong", "loi", f"Ngày cấp đọc không hợp lệ: '{g['ngay_cap']['nguyen_van']}'.")
    if "ma_vach" in g and "so_ma_vach_in" in g and g["ma_vach"]["gia_tri"] != g["so_ma_vach_in"]["gia_tri"]:
        them("ma_vach_lech", "canh_bao", "Số in dưới mã vạch khác với số giải mã từ mã vạch.")
    if kq["bien_dong"]["co_noi_dung"]:
        them("co_bien_dong", "canh_bao", kq["bien_dong"]["ghi_chu"])
