"""So sánh các cách OCR trên giấy tờ đã biết đáp án: mỗi trường có được đọc đúng nguyên văn không.

Cách dùng:
    python cong_cu/thu_ocr.py <file.pdf> [engine,engine…]

    engine: tesseract (mặc định), screenai (cần Chrome + locro, xem HUONG_DAN.md mục 6)

Cần file đáp án <file>.dap_an.json đặt cạnh file PDF:
    {"truong": [{"trang": 1, "ten": "Số thửa", "dung": "Thửa đất số: 307"}, …]}

Kết quả ghi cạnh file PDF: <file>.ocr.html (bảng so sánh, mở bằng trình duyệt) và <file>.ocr.json.
Giấy tờ thật chứa dữ liệu cá nhân: chỉ chạy trên máy, không commit file PDF, đáp án hay kết quả.
"""
import difflib
import html
import json
import sys
import time
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import tach_van_ban as tvb  # noqa: E402
from tach_van_ban import pymupdf  # noqa: E402
from PIL import Image  # noqa: E402

# (tên hiển thị, engine, dpi, kênh màu). "do" = chỉ lấy kênh đỏ: nền hồng và dấu đỏ gần như biến mất.
BIEN_THE = {
    "tesseract": [("Tesseract 200dpi xám", 200, "xam"), ("Tesseract 300dpi xám", 300, "xam"),
                  ("Tesseract 200dpi kênh đỏ", 200, "do"), ("Tesseract 300dpi kênh đỏ", 300, "do")],
    "screenai": [("Screen AI 200dpi màu", 200, "mau"), ("Screen AI 200dpi kênh đỏ", 200, "do")],
}


def chuan(s: str) -> str:
    """So khớp không phân biệt hoa thường và khoảng trắng, giữ nguyên dấu tiếng Việt."""
    return "".join(unicodedata.normalize("NFC", s).lower().split())


def gan_nhat(dung: str, text: str) -> tuple[float, str]:
    """Điểm giống (1 = có nguyên văn) và đoạn OCR giống giá trị đúng nhất (dạng đã chuẩn hoá)."""
    a, t = chuan(dung), chuan(text)
    if a in t:
        return 1.0, a
    best, best_s, n = 0.0, "", len(a)
    for i in range(0, max(1, len(t) - n + 1)):
        for m in (n - 2, n, n + 2):
            seg = t[i:i + max(1, m)]
            r = difflib.SequenceMatcher(None, a, seg).ratio()
            if r > best:
                best, best_s = r, seg
    return best, best_s


def anh_trang(page, dpi: int, kenh: str) -> Image.Image:
    if kenh == "xam":
        pix = page.get_pixmap(dpi=dpi, colorspace=pymupdf.csGRAY, alpha=False)
        return Image.frombuffer("L", (pix.width, pix.height), pix.samples, "raw", "L", pix.stride, 1)
    pix = page.get_pixmap(dpi=dpi, colorspace=pymupdf.csRGB, alpha=False)
    rgb = Image.frombuffer("RGB", (pix.width, pix.height), pix.samples, "raw", "RGB", pix.stride, 1)
    return rgb if kenh == "mau" else rgb.split()[0]


def doc_ma_vach(doc) -> dict[int, list[str]]:
    """Mã vạch / QR trên từng trang (cần: pip install zxing-cpp). Đọc chính xác, không qua OCR."""
    try:
        import zxingcpp
    except ImportError:
        return {}
    kq = {}
    for i, page in enumerate(doc):
        ma = [f"{r.format}: {r.text}" for r in zxingcpp.read_barcodes(anh_trang(page, 300, "mau"))]
        if ma:
            kq[i + 1] = ma
    return kq


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    pdf = Path(sys.argv[1])
    engines = (sys.argv[2] if len(sys.argv) > 2 else "tesseract").split(",")
    dap_an = json.loads(pdf.with_suffix(".dap_an.json").read_text(encoding="utf-8"))["truong"]
    doc = pymupdf.open(str(pdf))
    trang_can = sorted({x["trang"] for x in dap_an})

    ket_qua = {}
    for engine in engines:
        cfg = dict(tvb.cfg_mac_dinh(), engine=engine)
        ok, tb = tvb.kiem_tra_ocr(cfg)
        if not ok:
            print(f"Bỏ qua {engine}: {tb}")
            continue
        for ten, dpi, kenh in BIEN_THE[engine]:
            texts, giay = {}, 0.0
            for so in trang_can:
                img = anh_trang(doc[so - 1], dpi, kenh)
                t0 = time.perf_counter()
                texts[so], _ = tvb.ocr_anh(img, cfg)
                giay += time.perf_counter() - t0
            cham = []
            for x in dap_an:
                r, doan = gan_nhat(x["dung"], texts[x["trang"]])
                cham.append(dict(x, diem=round(r, 3), doc_ra=doan))
            dat = sum(c["diem"] == 1.0 for c in cham)
            ket_qua[ten] = dict(giay=round(giay, 1), dat=dat, tong=len(cham), cham=cham, texts=texts)
            print(f"{ten:28s} đúng nguyên văn {dat:3d}/{len(cham)}   OCR {giay:6.1f}s")

    ma_vach = doc_ma_vach(doc)
    for so, ds in ma_vach.items():
        print(f"Mã vạch trang {so}: {'; '.join(ds)}")

    pdf.with_suffix(".ocr.json").write_text(
        json.dumps(dict(ket_qua=ket_qua, ma_vach=ma_vach), ensure_ascii=False, indent=1), encoding="utf-8")
    ghi_html(ket_qua, ma_vach, dap_an, pdf.with_suffix(".ocr.html"))
    print(f"Bảng so sánh: {pdf.with_suffix('.ocr.html')}")


def ghi_html(kq: dict, ma_vach: dict, dap_an: list, f: Path):
    ten_bt = list(kq)
    dong = []
    for i, x in enumerate(dap_an):
        o = []
        for t in ten_bt:
            c = kq[t]["cham"][i]
            mau = "#d9f2d9" if c["diem"] == 1 else ("#fff3c4" if c["diem"] >= .85 else "#f8d7da")
            o.append(f'<td style="background:{mau}">{c["diem"]:.2f}<br><small>{html.escape(c["doc_ra"])}</small></td>')
        dong.append(f"<tr><td>{x['trang']}</td><td>{html.escape(x['ten'])}</td><td>{html.escape(x['dung'])}</td>{''.join(o)}</tr>")
    tong = "".join(f"<th>{html.escape(t)}<br>{kq[t]['dat']}/{kq[t]['tong']} · {kq[t]['giay']}s</th>" for t in ten_bt)
    mv = "".join(f"<li>Trang {so}: {html.escape('; '.join(ds))}</li>" for so, ds in ma_vach.items()) or "<li>Không thấy (hoặc chưa cài zxing-cpp)</li>"
    raw = "".join(f"<details><summary>{html.escape(t)} — trang {so}</summary><pre>{html.escape(x)}</pre></details>"
                  for t in ten_bt for so, x in kq[t]["texts"].items())
    f.write_text(f"""<!DOCTYPE html><html lang="vi"><meta charset="utf-8"><title>So sánh OCR</title>
<style>body{{font-family:system-ui;margin:16px}}table{{border-collapse:collapse}}td,th{{border:1px solid #ccc;padding:4px 6px;vertical-align:top;font-size:13px}}pre{{white-space:pre-wrap}}</style>
<h2>So sánh OCR — có dữ liệu cá nhân, không chia sẻ</h2>
<p>Xanh: đúng nguyên văn · Vàng: gần đúng (≥ 0,85) · Đỏ: sai. Dòng nhỏ: đoạn OCR giống nhất (đã bỏ khoảng trắng, chữ thường).</p>
<table><tr><th>Tr.</th><th>Trường</th><th>Đáp án</th>{tong}</tr>{''.join(dong)}</table>
<h3>Mã vạch / QR (đọc trực tiếp, không OCR)</h3><ul>{mv}</ul>
<h3>Chữ OCR đầy đủ</h3>{raw}</html>""", encoding="utf-8")


if __name__ == "__main__":
    main()
