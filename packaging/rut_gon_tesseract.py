# -*- coding: utf-8 -*-
"""
Rút gọn thư mục Tesseract trước khi đóng gói: chỉ giữ các DLL mà tesseract.exe thật sự nạp
(dò theo bảng import của file PE, kể cả import trễ, đệ quy qua các DLL được giữ), xoá phần còn lại.
Bản Tesseract cho Windows kèm nhiều thư viện chỉ dùng cho công cụ huấn luyện mô hình (pango, cairo, glib…).

    python packaging/rut_gon_tesseract.py <thư mục tesseract> [--thu]

--thu : chỉ liệt kê, không xoá. Bước tự kiểm tra sau khi đóng gói sẽ phát hiện nếu xoá nhầm.
"""
import sys
from pathlib import Path

import pefile  # có sẵn khi cài PyInstaller trên Windows


def dll_can_nap(f: Path) -> list[str]:
    pe = pefile.PE(str(f), fast_load=True)
    pe.parse_data_directories(directories=[
        pefile.DIRECTORY_ENTRY["IMAGE_DIRECTORY_ENTRY_IMPORT"],
        pefile.DIRECTORY_ENTRY["IMAGE_DIRECTORY_ENTRY_DELAY_IMPORT"],
    ])
    ten = []
    for thuoc_tinh in ("DIRECTORY_ENTRY_IMPORT", "DIRECTORY_ENTRY_DELAY_IMPORT"):
        for muc in getattr(pe, thuoc_tinh, None) or []:
            ten.append(muc.dll.decode("ascii", "ignore").lower())
    pe.close()
    return ten


def rut_gon(thu_muc: Path, goc=("tesseract.exe",), chi_thu=False) -> tuple[list[Path], list[Path]]:
    co_san = {p.name.lower(): p for p in thu_muc.glob("*.dll")}
    can, hang = set(), [thu_muc / g for g in goc]
    for f in hang:
        if not f.exists():
            raise SystemExit(f"Không thấy {f}")
    while hang:
        f = hang.pop()
        for ten in dll_can_nap(f):
            if ten in co_san and ten not in can:
                can.add(ten)
                hang.append(co_san[ten])
    giu = sorted((co_san[t] for t in can), key=lambda p: p.name.lower())
    bo = sorted((p for t, p in co_san.items() if t not in can), key=lambda p: p.name.lower())
    if not chi_thu:
        for p in bo:
            p.unlink()
    return giu, bo


def mb(ds) -> float:
    return sum(p.stat().st_size for p in ds) / 1048576 if ds else 0.0


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    thu_muc = Path(sys.argv[1])
    chi_thu = "--thu" in sys.argv
    co_san = list(thu_muc.glob("*.dll"))
    tong_truoc = mb(co_san)
    kich_thuoc = {p.name: p.stat().st_size / 1048576 for p in co_san}
    giu, bo = rut_gon(thu_muc, chi_thu=chi_thu)
    print(f"Giữ {len(giu)} DLL ({sum(kich_thuoc[p.name] for p in giu):.1f} MB):")
    for p in giu:
        print(f"   + {p.name:<40} {kich_thuoc[p.name]:6.1f} MB")
    print(f"{'Sẽ bỏ' if chi_thu else 'Đã bỏ'} {len(bo)} DLL ({sum(kich_thuoc[p.name] for p in bo):.1f} MB / tổng {tong_truoc:.1f} MB):")
    for p in sorted(bo, key=lambda p: -kich_thuoc[p.name]):
        print(f"   - {p.name:<40} {kich_thuoc[p.name]:6.1f} MB")
