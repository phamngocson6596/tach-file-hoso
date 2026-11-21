"""Đọc giấy chứng nhận quyền sử dụng đất (sổ đỏ / sổ hồng) thành dữ liệu có cấu trúc - BẢN THỬ.

Hai lớp dữ liệu:
  nguyen_van  - khung giấy đúng như in: mục -> dòng "nhãn: giá trị" / bảng / đoạn chữ (không cần biết trước trường)
  chuan_hoa   - các trường app dùng (chủ, thửa, nhà ở, công trình, thông tin giấy), sinh từ lớp nguyên văn
                theo từ điển nhãn tu_dien_nhan.json; mỗi giá trị kèm nguyên văn, nguồn, trạng thái xác nhận.

Dùng:  python -m so_do doc <file.pdf>      (xem python -m so_do -h)
"""
from __future__ import annotations

from datetime import datetime

from .chuan_hoa import SCHEMA_VERSION, chuan_hoa, nap_tu_dien
from .doc_khung import doc_khung

__all__ = ["doc_giay", "SCHEMA_VERSION"]


def doc_giay(cac_trang: list[str], ma_vach: list[str] | None = None, tu_dien: dict | None = None,
             thong_tin_tep: dict | None = None) -> dict:
    """Chữ OCR từng trang -> kết quả đầy đủ (lớp nguyên văn + lớp chuẩn hoá + kiểm tra)."""
    td = tu_dien or nap_tu_dien()
    tieu_de = [a for ds in td["muc"].values() for a in ds]
    nguyen_van = doc_khung(cac_trang, tieu_de_biet=tieu_de)
    kq = chuan_hoa(nguyen_van, td, ma_vach)
    return dict(
        schema_version=SCHEMA_VERSION,
        loai_giay="giay_chung_nhan",
        tep=dict(thong_tin_tep or {}, ngay_doc=datetime.now().isoformat(timespec="seconds"),
                 tu_dien_phien_ban=td.get("phien_ban")),
        chuan_hoa=kq["chuan_hoa"],
        kiem_tra=kq["kiem_tra"],
        chua_phan_loai=kq["chua_phan_loai"],
        nguyen_van=nguyen_van,
    )


def dem_trang_thai(kq: dict) -> dict:
    """Số giá trị theo trạng thái (doc_duoc / can_xac_nhan / da_xac_nhan) trong lớp chuẩn hoá."""
    dem: dict[str, int] = {}

    def duyet(v):
        if isinstance(v, dict):
            if "trang_thai" in v and "gia_tri" in v:
                dem[v["trang_thai"]] = dem.get(v["trang_thai"], 0) + 1
            for x in v.values():
                duyet(x)
        elif isinstance(v, list):
            for x in v:
                duyet(x)

    duyet(kq["chuan_hoa"])
    return dem
