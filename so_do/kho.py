"""Kho trên máy (SQLite) để tra cứu chéo giữa các hồ sơ: khách quen, tài sản đã từng làm, nhãn lạ.

Bản gốc của dữ liệu là file <tên>.gcn.json đặt cạnh file scan; kho chỉ là chỉ mục để tìm nhanh,
dựng lại được bất cứ lúc nào bằng lệnh `python -m so_do lap-chi-muc <thư mục>`.
Kho chứa dữ liệu cá nhân: nằm trong thư mục người dùng, không đồng bộ lên mạng. (Bản thử: chưa mã hoá.)
"""
from __future__ import annotations

import json
import os
import re
import sqlite3
from pathlib import Path

from .doc_khung import bo_dau

_LUOC_DO = """
CREATE TABLE IF NOT EXISTS giay_to (
    id INTEGER PRIMARY KEY,
    sha256 TEXT UNIQUE NOT NULL,          -- cùng một file đọc lại thì ghi đè, không nhân bản
    tep TEXT, file_json TEXT, loai TEXT, engine TEXT, schema_version TEXT, ngay_doc TEXT,
    so_phat_hanh TEXT, so_loi INTEGER, so_canh_bao INTEGER, so_can_xac_nhan INTEGER,
    du_lieu TEXT NOT NULL                 -- toàn bộ kết quả JSON
);
CREATE TABLE IF NOT EXISTS nguoi (
    id INTEGER PRIMARY KEY,
    so_giay_to TEXT UNIQUE,               -- khoá nhận diện: số CCCD/CMND/hộ chiếu (chỉ chữ và số)
    loai_giay_to TEXT, ho_ten TEXT, ho_ten_khong_dau TEXT, nam_sinh INTEGER, dia_chi TEXT
);
CREATE TABLE IF NOT EXISTS thua (
    id INTEGER PRIMARY KEY,
    khoa TEXT UNIQUE NOT NULL,            -- số thửa | tờ bản đồ | địa chỉ rút gọn
    so_thua TEXT, to_ban_do TEXT, dia_chi TEXT, dien_tich REAL
);
CREATE TABLE IF NOT EXISTS giay_to_nguoi (giay_to_id INTEGER, nguoi_id INTEGER, vai TEXT,
    PRIMARY KEY (giay_to_id, nguoi_id));
CREATE TABLE IF NOT EXISTS giay_to_thua (giay_to_id INTEGER, thua_id INTEGER,
    PRIMARY KEY (giay_to_id, thua_id));
CREATE TABLE IF NOT EXISTS nhan_moi (
    nhan TEXT PRIMARY KEY, muc TEXT, so_lan INTEGER, vi_du TEXT
);
CREATE INDEX IF NOT EXISTS ix_nguoi_ten ON nguoi(ho_ten_khong_dau);
CREATE INDEX IF NOT EXISTS ix_thua_so ON thua(so_thua, to_ban_do);
"""


def duong_dan_mac_dinh() -> Path:
    goc = os.environ.get("LOCALAPPDATA") or os.path.join(Path.home(), ".local", "share")
    return Path(goc) / "eNotary" / "kho_so_do.sqlite"


def mo(duong_dan: Path | None = None) -> sqlite3.Connection:
    p = Path(duong_dan or duong_dan_mac_dinh())
    p.parent.mkdir(parents=True, exist_ok=True)
    kho = sqlite3.connect(p)
    kho.row_factory = sqlite3.Row
    kho.executescript(_LUOC_DO)
    return kho


def _gt(v):
    return v.get("gia_tri") if isinstance(v, dict) else None


def _rut_gon_dia_chi(dc: str) -> str:
    """Phần đủ phân biệt của địa chỉ thửa: phường/xã + quận/huyện, bỏ dấu, bỏ khoảng trắng."""
    n = bo_dau(dc)
    phan = [x.strip() for x in n.split(",")]
    giu = [x for x in phan if re.match(r"(phuong|xa|thi tran|quan|huyen|thi xa|thanh pho)\b", x)]
    return re.sub(r"\W+", "", ",".join(giu[:2] or phan[-2:]))


def luu(kho: sqlite3.Connection, kq: dict, file_json: str | None = None) -> list[str]:
    """Ghi một giấy chứng nhận vào kho. Trả về các lưu ý tra chéo (khách quen, tài sản đã có trong kho)."""
    ch, tep = kq["chuan_hoa"], kq.get("tep", {})
    from . import dem_trang_thai
    dem = dem_trang_thai(kq)
    loi = sum(k["muc_do"] == "loi" for k in kq["kiem_tra"])
    canh_bao = sum(k["muc_do"] == "canh_bao" for k in kq["kiem_tra"])
    luu_y = []
    with kho:
        cu = kho.execute("SELECT id FROM giay_to WHERE sha256=?", (tep["sha256"],)).fetchone()
        if cu:  # đọc lại cùng file: xoá liên kết cũ rồi ghi lại
            kho.execute("DELETE FROM giay_to_nguoi WHERE giay_to_id=?", (cu["id"],))
            kho.execute("DELETE FROM giay_to_thua WHERE giay_to_id=?", (cu["id"],))
            kho.execute("DELETE FROM giay_to WHERE id=?", (cu["id"],))
        gid = kho.execute(
            "INSERT INTO giay_to (sha256, tep, file_json, loai, engine, schema_version, ngay_doc, so_phat_hanh,"
            " so_loi, so_canh_bao, so_can_xac_nhan, du_lieu) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (tep["sha256"], tep.get("ten"), file_json, kq["loai_giay"], tep.get("engine"), kq["schema_version"],
             tep.get("ngay_doc"), _gt(ch["giay"].get("so_phat_hanh", {})), loi, canh_bao,
             dem.get("can_xac_nhan", 0), json.dumps(kq, ensure_ascii=False))).lastrowid

        for c in ch["chu"]:
            gt = _gt(c.get("giay_to", {})) or {}
            ten = _gt(c.get("ho_ten", {})) or ""
            so = re.sub(r"\W", "", gt.get("so", "")).upper() or None
            if so:
                kho.execute(
                    "INSERT INTO nguoi (so_giay_to, loai_giay_to, ho_ten, ho_ten_khong_dau, nam_sinh, dia_chi)"
                    " VALUES (?,?,?,?,?,?) ON CONFLICT(so_giay_to) DO UPDATE SET ho_ten=excluded.ho_ten,"
                    " ho_ten_khong_dau=excluded.ho_ten_khong_dau, nam_sinh=excluded.nam_sinh, dia_chi=excluded.dia_chi",
                    (so, gt.get("loai"), ten, bo_dau(ten), _gt(c.get("nam_sinh", {})), _gt(c.get("dia_chi", {}))))
                nid = kho.execute("SELECT id FROM nguoi WHERE so_giay_to=?", (so,)).fetchone()["id"]
            else:  # không có số giấy tờ thì không gộp được với ai: ghi riêng
                nid = kho.execute("INSERT INTO nguoi (ho_ten, ho_ten_khong_dau, dia_chi) VALUES (?,?,?)",
                                  (ten, bo_dau(ten), _gt(c.get("dia_chi", {})))).lastrowid
            kho.execute("INSERT OR IGNORE INTO giay_to_nguoi VALUES (?,?,?)", (gid, nid, c.get("vai")))
            khac = kho.execute("SELECT g.tep, g.so_phat_hanh FROM giay_to_nguoi gn JOIN giay_to g ON g.id=gn.giay_to_id"
                               " WHERE gn.nguoi_id=? AND g.id<>?", (nid, gid)).fetchall()
            if so and khac:
                luu_y.append(f"Khách quen: {ten} ({gt.get('loai')} {so}) đã có trong {len(khac)} giấy khác: "
                             + ", ".join(f"{r['so_phat_hanh'] or r['tep']}" for r in khac[:3]))

        for t in ch["thua"]:
            so_thua, to = _gt(t.get("so_thua", {})), _gt(t.get("to_ban_do", {}))
            dc = _gt(t.get("dia_chi", {})) or ""
            if not (so_thua and to):
                continue
            khoa = f"{so_thua}|{to}|{_rut_gon_dia_chi(dc)}"
            kho.execute("INSERT INTO thua (khoa, so_thua, to_ban_do, dia_chi, dien_tich) VALUES (?,?,?,?,?)"
                        " ON CONFLICT(khoa) DO UPDATE SET dia_chi=excluded.dia_chi, dien_tich=excluded.dien_tich",
                        (khoa, so_thua, to, dc, _gt(t.get("dien_tich", {}))))
            tid = kho.execute("SELECT id FROM thua WHERE khoa=?", (khoa,)).fetchone()["id"]
            kho.execute("INSERT OR IGNORE INTO giay_to_thua VALUES (?,?)", (gid, tid))
            khac = kho.execute("SELECT g.tep, g.so_phat_hanh FROM giay_to_thua gt JOIN giay_to g ON g.id=gt.giay_to_id"
                               " WHERE gt.thua_id=? AND g.id<>?", (tid, gid)).fetchall()
            if khac:
                luu_y.append(f"Tài sản đã có trong kho: thửa {so_thua} tờ {to} ({dc[:60]}) thuộc {len(khac)} giấy khác: "
                             + ", ".join(f"{r['so_phat_hanh'] or r['tep']}" for r in khac[:3])
                             + ". Thửa chung (chung cư, dự án) thì đây là bình thường.")

        for c in kq["chua_phan_loai"]:
            if c["nhan"]:
                kho.execute("INSERT INTO nhan_moi (nhan, muc, so_lan, vi_du) VALUES (?,?,1,?) ON CONFLICT(nhan)"
                            " DO UPDATE SET so_lan=so_lan+1, vi_du=excluded.vi_du",
                            (c["nhan"], c["tieu_de_muc"], c["gia_tri"][:120]))
    return luu_y


def tim_nguoi(kho: sqlite3.Connection, tu_khoa: str) -> list[dict]:
    """Tìm theo số giấy tờ (đúng) hoặc tên (không dấu, một phần)."""
    so = re.sub(r"\W", "", tu_khoa).upper()
    rows = kho.execute(
        "SELECT n.*, group_concat(coalesce(g.so_phat_hanh, g.tep), '; ') AS giay FROM nguoi n"
        " LEFT JOIN giay_to_nguoi gn ON gn.nguoi_id=n.id LEFT JOIN giay_to g ON g.id=gn.giay_to_id"
        " WHERE n.so_giay_to=? OR n.ho_ten_khong_dau LIKE ? GROUP BY n.id",
        (so, f"%{bo_dau(tu_khoa)}%")).fetchall()
    return [dict(r) for r in rows]


def tim_thua(kho: sqlite3.Connection, so_thua: str, to_ban_do: str | None = None) -> list[dict]:
    sql = ("SELECT t.*, group_concat(coalesce(g.so_phat_hanh, g.tep), '; ') AS giay FROM thua t"
           " LEFT JOIN giay_to_thua gt ON gt.thua_id=t.id LEFT JOIN giay_to g ON g.id=gt.giay_to_id"
           " WHERE t.so_thua=?" + (" AND t.to_ban_do=?" if to_ban_do else "") + " GROUP BY t.id")
    return [dict(r) for r in kho.execute(sql, (so_thua, to_ban_do) if to_ban_do else (so_thua,)).fetchall()]


def nhan_moi(kho: sqlite3.Connection) -> list[dict]:
    return [dict(r) for r in kho.execute("SELECT * FROM nhan_moi ORDER BY so_lan DESC")]


def lap_chi_muc(kho: sqlite3.Connection, thu_muc: Path) -> int:
    """Dựng lại kho từ các file .gcn.json trong thư mục (đệ quy)."""
    n = 0
    for f in sorted(Path(thu_muc).rglob("*.gcn.json")):
        luu(kho, json.loads(f.read_text(encoding="utf-8")), str(f))
        n += 1
    return n
