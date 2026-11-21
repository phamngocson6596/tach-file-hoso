"""Dòng lệnh: python -m so_do <lệnh> …

  doc <file…>             OCR + đọc giấy chứng nhận, ghi <file>.gcn.json và <file>.gcn.html cạnh file, lưu vào kho
  tim --nguoi <số/tên>    tìm người trong kho (số CCCD/CMND hoặc tên không dấu)
  tim --thua <số> [--to <tờ>]   tìm thửa đất trong kho
  nhan-moi                các nhãn chưa có trong từ điển, gặp nhiều nhất trước (để bổ sung tu_dien_nhan.json)
  lap-chi-muc <thư mục>   dựng lại kho từ các file .gcn.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import dem_trang_thai, doc_giay
from . import kho as kho_mod


def main(argv=None):
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(prog="python -m so_do", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--kho", type=Path, help=f"file kho SQLite (mặc định {kho_mod.duong_dan_mac_dinh()})")
    sub = ap.add_subparsers(dest="lenh", required=True)

    d = sub.add_parser("doc", help="đọc giấy chứng nhận từ PDF/ảnh")
    d.add_argument("tep", nargs="+", type=Path)
    d.add_argument("--engine", choices=["screenai", "tesseract"], default="screenai")
    d.add_argument("--tu-chu", action="store_true",
                   help="tệp vào là chữ đã OCR (.txt, các trang ngăn bằng ký tự \\f), bỏ qua bước OCR")
    d.add_argument("--khong-luu-kho", action="store_true")

    t = sub.add_parser("tim", help="tra cứu kho")
    t.add_argument("--nguoi")
    t.add_argument("--thua")
    t.add_argument("--to")

    sub.add_parser("nhan-moi", help="nhãn chưa có trong từ điển")
    l = sub.add_parser("lap-chi-muc", help="dựng lại kho từ các file .gcn.json")
    l.add_argument("thu_muc", type=Path)

    a = ap.parse_args(argv)
    kho = kho_mod.mo(a.kho)

    if a.lenh == "doc":
        for p in a.tep:
            try:
                _doc_mot(p, a, kho)
            except (RuntimeError, FileNotFoundError) as e:
                print(f"  Không đọc được: {e}")
                if a.engine == "screenai":
                    print("  Gợi ý: kích hoạt Screen AI (HUONG_DAN.md mục 6) hoặc chạy thêm --engine tesseract")
                    break
    elif a.lenh == "tim":
        kq = kho_mod.tim_nguoi(kho, a.nguoi) if a.nguoi else kho_mod.tim_thua(kho, a.thua, a.to) if a.thua else []
        print(json.dumps(kq, ensure_ascii=False, indent=1) if kq else "Không thấy.")
    elif a.lenh == "nhan-moi":
        for r in kho_mod.nhan_moi(kho):
            print(f"{r['so_lan']:4d}  {r['nhan']}  (mục: {r['muc']})  ví dụ: {r['vi_du']}")
    elif a.lenh == "lap-chi-muc":
        print(f"Đã nạp {kho_mod.lap_chi_muc(kho, a.thu_muc)} giấy vào kho.")


def _doc_mot(p: Path, a, kho):
    from .bao_cao import ghi as ghi_html
    print(f"{p.name}")
    if a.tu_chu:
        import hashlib
        cac_trang, ma_vach, anh = p.read_text(encoding="utf-8").split("\f"), [], None
        sha = hashlib.sha256(p.read_bytes()).hexdigest()
    else:
        from . import ocr
        cac_trang, ma_vach = ocr.doc_tep(p, a.engine, log=lambda s: print(s, end="\r"))
        sha, anh = ocr.sha256(p), ocr.anh_thu_nho(p)
    kq = doc_giay(cac_trang, ma_vach, thong_tin_tep=dict(ten=p.name, sha256=sha, so_trang=len(cac_trang),
                                                          engine="chu_co_san" if a.tu_chu else a.engine))
    f_json, f_html = p.with_suffix(".gcn.json"), p.with_suffix(".gcn.html")
    f_json.write_text(json.dumps(kq, ensure_ascii=False, indent=1), encoding="utf-8")
    ghi_html(kq, f_html, anh)

    ch, dem = kq["chuan_hoa"], dem_trang_thai(kq)
    print(f"  {len(ch['chu'])} chủ · {len(ch['thua'])} thửa · {len(ch['nha_o'])} nhà ở · {len(ch['cong_trinh'])} công trình"
          f" · đọc được {dem.get('doc_duoc', 0)} · cần xác nhận {dem.get('can_xac_nhan', 0)}")
    for k in kq["kiem_tra"]:
        print(f"  [{'LỖI' if k['muc_do'] == 'loi' else 'lưu ý'}] {k['noi_dung']}")
    if kq["chua_phan_loai"]:
        print(f"  {len(kq['chua_phan_loai'])} nhãn chưa có trong từ điển: "
              + ", ".join(str(c["nhan"]) for c in kq["chua_phan_loai"][:5]))
    if not a.khong_luu_kho:
        for x in kho_mod.luu(kho, kq, str(f_json)):
            print(f"  [kho] {x}")
    print(f"  -> {f_json.name}, {f_html.name}")


if __name__ == "__main__":
    main()
