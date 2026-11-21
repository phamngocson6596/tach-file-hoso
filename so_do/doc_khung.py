"""Lớp 1 - "nguyên văn": dựng khung giấy chứng nhận từ chữ OCR, KHÔNG cần biết trước tên trường.

Giấy chứng nhận đời nào cũng theo một khung: mục lớn (I, II…) -> mục con (1. Thửa đất…) -> các dòng
"nhãn: giá trị", bảng, hoặc đoạn chữ tự do. Ở đây chỉ nhận ra khung đó; nhãn gặp gì ghi nấy, đúng thứ tự.
Việc nhãn nào là trường gì để lớp 2 (chuan_hoa.py) làm theo từ điển.
"""
from __future__ import annotations

import re
import unicodedata

_MUC_LON = re.compile(r"^\W{0,2}(?P<ma>I{1,3}|IV|VI?)\s*\.\s*(?P<td>[^\d\W].*)$")
_MUC_CON = re.compile(r"^\W{0,2}(?P<so>\d{1,2})\W{0,2}?\s*[.)]\s*(?P<td>[^\d\W][^:]{0,80}?)\s*:\s*(?P<sau>.*)$")
_MUC_NHO = re.compile(r"^\W{0,2}(?P<chu>\S{1,2}?)\s*\)\s*(?P<nd>[^\d\W].*:.*)$")
# Gạch đầu dòng phải có khoảng trắng rồi tới chữ: "- Giấy chứng nhận…"; không nhầm với ô trống "-/-".
_GACH_DAU = re.compile(r"^\s*[-–•+]\s+(?P<nd>[^\W\d].*)$")
_DONG_NHAN = re.compile(r"^\W{0,2}(?P<nhan>[^\W\d][^:,()]{0,50}?)\s*:\s*(?P<gt>.*)$")
_DONG_KY = re.compile(r"^(?P<noi>[^,:]{2,45}),\s*ngày\b.*tháng.*năm", re.IGNORECASE)
_SO_PHAT_HANH = re.compile(r"^\W{0,2}(?P<so>[A-Z]{1,2}\s?\d{6,8})\W{0,2}$")
_SO_MA_VACH = re.compile(r"^\W{0,2}(?P<so>\d{10,16})\W{0,2}$")
_DONG_RAC = re.compile(r"quet bang camscanner|duoc quet bang")

# Dòng tiêu đề cột hay gặp: bắt đầu một bảng (Screen AI trả về bảng thành các dòng rời).
_TIEU_DE_BANG = ("hang muc cong trinh", "dien tich xay dung", "so hieu diem", "bang liet ke toa do",
                 "noi dung thay doi va co so phap ly", "xac nhan cua co quan")


def bo_dau(s: str) -> str:
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return s.replace("đ", "d").replace("Đ", "D").lower()


def tach_truong(chu: str) -> list[dict]:
    """ "Thửa đất số: 15, tờ bản đồ số: 42," -> [{nhan: Thửa đất số, gia_tri: 15}, {nhan: tờ bản đồ số, …}].

    Chỉ tách ở dấu phẩy/chấm phẩy nằm NGOÀI ngoặc và ngay sau đó là "nhãn:" (nhãn ngắn, bắt đầu bằng chữ).
    Vì vậy địa chỉ nhiều dấu phẩy, hay "(bằng chữ: …)" không bị tách nhầm.
    """
    sau, sau_ngoac = [], 0
    for c in chu:
        sau.append(sau_ngoac)
        sau_ngoac += (c == "(") - (c == ")")
    diem_dau = [0] + [i + 1 for i, c in enumerate(chu) if c in ",;" and sau[i] == 0]
    nhan = []
    for s in diem_dau:
        m = re.match(r"\s*(?P<nhan>[^\W\d][^,;:()]{0,50}?)\s*:", chu[s:])
        if m and len(m.group("nhan").split()) <= 8:
            nhan.append((s, s + m.end(), m.group("nhan").strip()))
    if not nhan:
        return [dict(nhan=None, gia_tri=_gon(chu))]
    kq = []
    if nhan[0][0] > 0 and chu[:nhan[0][0]].strip(" ,;"):
        kq.append(dict(nhan=None, gia_tri=_gon(chu[:nhan[0][0]])))
    for k, (s, het_nhan, ten) in enumerate(nhan):
        het = nhan[k + 1][0] if k + 1 < len(nhan) else len(chu)
        kq.append(dict(nhan=ten, gia_tri=_gon(chu[het_nhan:het])))
    return kq


def _gon(s: str) -> str:
    s = re.sub(r"\s+", " ", s).strip(" ,;.")
    return re.sub(r"\s+[-'’`\"_=|]+$", "", s)  # rác OCR đứng riêng ở cuối: "NGUYỄN VĂN AN -", "111 '"


def doc_khung(cac_trang: list[str], tieu_de_biet: list[str] = ()) -> list[dict]:
    """Chữ từng trang -> danh sách mục; mỗi mục có các phần tử theo đúng thứ tự trên giấy.

    tieu_de_biet: tiêu đề mục đã biết (lấy từ từ điển). Dòng mở đầu bằng một tiêu đề này được coi là
    bắt đầu mục mới kể cả khi OCR làm mất số thứ tự ("I.", "II.").

    Mục đặc biệt: "DAU" (phần trước mục I: quốc hiệu, tên giấy), "KY" (nơi cấp, ngày, cơ quan, người ký).
    Phần tử: ban_ghi (các cặp nhãn: giá trị), bang (các dòng thô của bảng), van_ban (đoạn chữ),
             so_phat_hanh, so_ma_vach_in.
    """
    biet = [bo_dau(t.rstrip("*")) for t in tieu_de_biet if len(t.rstrip("*")) >= 12]
    muc: list[dict] = []
    hien = _muc_moi(muc, "DAU", "", 1)
    lon = None          # mã mục lớn hiện tại (I, II…)
    pt = None           # phần tử đang được nối thêm dòng
    che_do_bang = False

    for so_trang, chu in enumerate(cac_trang, start=1):
        for so_dong, dong in enumerate(chu.splitlines(), start=1):
            dong = dong.strip()
            if not dong or _DONG_RAC.search(bo_dau(dong)):
                continue
            nguon = dict(trang=so_trang, dong=so_dong)
            khong_dau = bo_dau(dong)

            if m := _SO_PHAT_HANH.match(dong):
                hien["noi_dung"].append(dict(kieu="so_phat_hanh", gia_tri=m.group("so"), nguon=nguon))
                pt = None
                continue
            if m := _SO_MA_VACH.match(dong):
                hien["noi_dung"].append(dict(kieu="so_ma_vach_in", gia_tri=m.group("so"), nguon=nguon))
                pt = None
                continue
            if m := _MUC_LON.match(dong):
                lon = m.group("ma")
                hien = _muc_moi(muc, lon, _gon(m.group("td")), so_trang)
                pt, che_do_bang = None, False
                continue
            if ":" not in dong and any(khong_dau.startswith(t) for t in biet) and not hien["ma"].startswith("?"):
                hien = _muc_moi(muc, f"?{len(muc)}", _gon(dong), so_trang)
                pt, che_do_bang = None, False
                continue
            if _DONG_KY.match(dong):
                hien = _muc_moi(muc, "KY", "Nơi cấp, ngày cấp, người ký", so_trang)
                _phan_tu(hien, "van_ban", dong, nguon)
                pt, che_do_bang = None, False  # mỗi dòng của khối ký là một phần tử riêng
                continue
            if lon and (m := _MUC_CON.match(dong)):
                hien = _muc_moi(muc, f"{lon}.{m.group('so')}", _gon(m.group("td")), so_trang)
                pt, che_do_bang = None, False
                if _gon(m.group("sau")):
                    pt = _phan_tu(hien, "ban_ghi", f"{_gon(m.group('td'))}: {m.group('sau')}", nguon)
                continue
            if m := _MUC_NHO.match(dong):
                pt, che_do_bang = _phan_tu(hien, "ban_ghi", m.group("nd"), nguon), False
                continue
            if m := _GACH_DAU.match(dong):
                pt, che_do_bang = _phan_tu(hien, "van_ban", m.group("nd"), nguon), False
                continue
            if che_do_bang:
                pt["dong_tho"].append(dong)
                continue
            if (any(khong_dau.startswith(t) for t in _TIEU_DE_BANG) or dong.count("|") >= 2
                    or ("|" in dong and ":" not in dong)):
                # Bảng biến động nằm ngoài mục biến động (thiếu dòng tiêu đề "IV." do OCR/thiếu trang)
                if khong_dau.startswith("noi dung thay doi") and "thay doi" not in bo_dau(hien["tieu_de"]):
                    hien = _muc_moi(muc, "BD", "Những thay đổi sau khi cấp giấy chứng nhận", so_trang)
                pt = dict(kieu="bang", dong_tho=[dong], nguon=nguon, trang_thai="chua_dung_bang")
                hien["noi_dung"].append(pt)
                che_do_bang = True
                continue
            if _DONG_NHAN.match(dong):
                pt = _phan_tu(hien, "ban_ghi", dong, nguon)
                continue
            if hien["ma"] == "KY":
                _phan_tu(hien, "van_ban", dong, nguon)
                pt = None
                continue
            # Dòng nối tiếp phần tử trước (OCR xuống dòng giữa câu), trừ khi câu trước đã kết thúc
            # và dòng này mở đầu bằng chữ hoa (một ý mới trong phần ghi chú).
            if pt and pt["kieu"] in ("ban_ghi", "van_ban") and not (
                    pt["tho"].rstrip().endswith(".") and dong[:1].isupper()):
                pt["tho"] += " " + dong
                pt["nguon"]["den_dong"] = so_dong
                continue
            pt = _phan_tu(hien, "van_ban", dong, nguon)

    for m in muc:
        for p in m["noi_dung"]:
            if p["kieu"] == "ban_ghi":
                p["truong"] = tach_truong(p["tho"])
            elif p["kieu"] == "van_ban":
                p["noi_dung"] = _gon(p.pop("tho"))
    return [m for m in muc if m["noi_dung"] or m["ma"] != "DAU"]


def _muc_moi(muc: list, ma: str, tieu_de: str, trang: int) -> dict:
    m = dict(ma=ma, tieu_de=tieu_de, trang=trang, noi_dung=[])
    muc.append(m)
    return m


def _phan_tu(muc: dict, kieu: str, chu: str, nguon: dict) -> dict:
    p = dict(kieu=kieu, tho=chu, nguon=dict(nguon))
    muc["noi_dung"].append(p)
    return p
