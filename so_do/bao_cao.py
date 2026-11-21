"""Trang duyệt HTML: ảnh từng trang bên trái, các trường và trạng thái bên phải."""
from __future__ import annotations

import base64
import html
import json
from pathlib import Path

_MAU = {"doc_duoc": "#e7f5e7", "can_xac_nhan": "#fff1bf", "da_xac_nhan": "#cfe8ff"}
_TEN = {
    "giay": "Thông tin giấy", "chu": "Người sử dụng đất / chủ sở hữu", "thua": "Thửa đất", "nha_o": "Nhà ở",
    "cong_trinh": "Công trình xây dựng khác", "ghi_chu": "Ghi chú", "bien_dong": "Biến động sau khi cấp",
    "rung": "Rừng sản xuất là rừng trồng", "cay_lau_nam": "Cây lâu năm",
}


_NHAN = {
    "so_phat_hanh": "Số phát hành (seri)", "so_vao_so": "Số vào sổ cấp GCN", "ngay_cap": "Ngày cấp",
    "noi_cap": "Nơi cấp", "co_quan_cap": "Cơ quan cấp", "nguoi_ky": "Người ký", "so_bien_nhan": "Số biên nhận",
    "ma_vach": "Mã vạch (giải mã)", "so_ma_vach_in": "Số in dưới mã vạch", "vai": "Danh xưng", "ho_ten": "Họ tên",
    "nam_sinh": "Năm sinh", "ngay_sinh": "Ngày sinh", "giay_to": "Giấy tờ tuỳ thân", "dia_chi": "Địa chỉ",
    "so_thua": "Thửa đất số", "to_ban_do": "Tờ bản đồ số", "dien_tich": "Diện tích (m²)",
    "hinh_thuc_su_dung": "Hình thức sử dụng", "muc_dich": "Mục đích sử dụng", "loai": "Loại",
    "thoi_han": "Thời hạn sử dụng", "nguon_goc": "Nguồn gốc sử dụng", "loai_cong_trinh": "Loại công trình",
    "hang_muc": "Hạng mục", "dien_tich_xay_dung": "Diện tích xây dựng (m²)", "dien_tich_san": "Diện tích sàn (m²)",
    "hinh_thuc_so_huu": "Hình thức sở hữu", "cap": "Cấp", "thoi_han_so_huu": "Thời hạn sở hữu",
    "co_noi_dung": "Có nội dung biến động", "ket_cau": "Kết cấu", "so_tang": "Số tầng",
}


def _ten(k: str) -> str:
    return html.escape(_NHAN.get(k, k))


def _o(v) -> str:
    gt = v.get("gia_tri")
    if isinstance(gt, dict):
        gt = " ".join(str(x) for x in gt.values())
    tt = v.get("trang_thai", "")
    nguon = v.get("nguon") or {}
    goi_y = f"Nguyên văn: {v.get('nguyen_van', '')}\nNguồn: trang {nguon.get('trang', '?')} dòng {nguon.get('dong', '?')}"
    if v.get("ghi_chu"):
        goi_y += f"\n{v['ghi_chu']}"
    if v.get("bang_chu"):
        goi_y += f"\nBằng chữ: {v['bang_chu']} → {v.get('so_tu_chu')}"
    nhan = "" if tt == "doc_duoc" else f' <span class="tt">{html.escape(tt.replace("_", " "))}</span>'
    hien = str(gt) if gt is not None else f"— (đọc ra: {v.get('nguyen_van', '')})"
    return (f'<td style="background:{_MAU.get(tt, "#fff")}" title="{html.escape(goi_y)}">'
            f'{html.escape(hien)}{nhan}</td>')


def _bang_truong(d: dict) -> str:
    dong = []
    for k, v in d.items():
        if isinstance(v, dict) and "gia_tri" in v:
            dong.append(f"<tr><th>{_ten(k)}</th>{_o(v)}</tr>")
        elif isinstance(v, list):
            for i, x in enumerate(v, 1):
                if isinstance(x, dict):
                    dong.append(f'<tr><th>{_ten(k)} [{i}]</th><td><table>{_bang_truong(x)}</table></td></tr>')
        elif v is not None and not isinstance(v, (dict, list)):
            chu = ("Có" if v else "Không") if isinstance(v, bool) else str(v)
            dong.append(f"<tr><th>{_ten(k)}</th><td>{html.escape(chu)}</td></tr>")
    return "".join(dong)


def ghi(kq: dict, f: Path, anh_trang: list[bytes] | None = None):
    ch = kq["chuan_hoa"]
    phan = []
    for k in ("giay", "chu", "thua", "nha_o", "cong_trinh", "rung", "cay_lau_nam", "ghi_chu", "bien_dong"):
        v = ch.get(k)
        if not v:
            continue
        if isinstance(v, list):
            noi = "".join(f"<table>{_bang_truong(x) if 'gia_tri' not in x else '<tr>' + _o(x) + '</tr>'}</table>"
                          for x in v)
        else:
            noi = f"<table>{_bang_truong(v)}</table>"
        phan.append(f"<h3>{_TEN.get(k, k)}</h3>{noi}")

    kt = "".join(f'<li class="{k["muc_do"]}">{html.escape(k["noi_dung"])}</li>' for k in kq["kiem_tra"]) \
        or "<li>Không có.</li>"
    la = "".join(f"<li><b>{html.escape(str(c['nhan']))}</b> = {html.escape(c['gia_tri'])} "
                 f"<small>(mục {html.escape(c['tieu_de_muc'])})</small></li>" for c in kq["chua_phan_loai"]) \
        or "<li>Không có: mọi nhãn đều có trong từ điển.</li>"
    anh = "".join(f'<img src="data:image/png;base64,{base64.b64encode(a).decode()}">' for a in (anh_trang or []))
    tep = kq.get("tep", {})
    f.write_text(f"""<!DOCTYPE html><html lang="vi"><meta charset="utf-8"><title>Duyệt giấy chứng nhận</title>
<style>
body{{font-family:system-ui;margin:0;display:flex;height:100vh}}
#anh{{width:42%;overflow:auto;background:#eee;padding:8px}} #anh img{{width:100%;margin-bottom:8px;box-shadow:0 1px 4px #0003}}
#du{{flex:1;overflow:auto;padding:12px 18px}}
table{{border-collapse:collapse;margin:4px 0;width:100%}} th,td{{border:1px solid #ddd;padding:4px 6px;text-align:left;vertical-align:top;font-size:13px}}
th{{width:28%;background:#fafafa;font-weight:600}} td[title]{{cursor:help}}
.tt{{font-size:11px;background:#e0a800;color:#fff;border-radius:3px;padding:0 4px;margin-left:4px}}
li.loi{{color:#b00020;font-weight:600}} li.canh_bao{{color:#8a5a00}}
pre{{white-space:pre-wrap;font-size:12px;background:#f6f6f6;padding:8px}}
</style>
<div id="anh">{anh}</div>
<div id="du">
<h2>Giấy chứng nhận — bản đọc thử</h2>
<p><small>{html.escape(str(tep.get('ten', '')))} · engine {html.escape(str(tep.get('engine', '')))} ·
schema {html.escape(kq['schema_version'])} · {html.escape(str(tep.get('ngay_doc', '')))} ·
<b>Có dữ liệu cá nhân: không chia sẻ.</b></small></p>
<p>Xanh: đọc được · <span style="background:{_MAU['can_xac_nhan']}">Vàng: cần xác nhận</span>
(viết tay, đoán, hoặc kiểm tra không khớp). Rê chuột lên ô để xem nguyên văn và nguồn.</p>
<h3>Kiểm tra</h3><ul>{kt}</ul>
{''.join(phan)}
<h3>Nhãn chưa có trong từ điển</h3><ul>{la}</ul>
<details><summary>Lớp nguyên văn (khung giấy đúng như in)</summary>
<pre>{html.escape(json.dumps(kq['nguyen_van'], ensure_ascii=False, indent=1))}</pre></details>
</div></html>""", encoding="utf-8")
