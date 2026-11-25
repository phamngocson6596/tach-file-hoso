#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Giao diện cho tach_van_ban.py — tách văn bản công chứng khỏi hồ sơ lưu trong PDF scan gộp.
Chạy:  python giao_dien.py   (Windows: bấm đúp chay_giao_dien.bat)
"""
from __future__ import annotations

import json
import multiprocessing
import os
import queue
import subprocess
import sys
import threading
import tkinter as tk
import webbrowser
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from tkinter.scrolledtext import ScrolledText

# Bản .exe không có cửa sổ dòng lệnh: sys.stdout/stderr = None, mọi lệnh print sẽ lỗi -> chuyển vào "hố đen".
if sys.stdout is None:
    sys.stdout = open(os.devnull, "w", encoding="utf-8")
if sys.stderr is None:
    sys.stderr = open(os.devnull, "w", encoding="utf-8")

THU_MUC = Path(__file__).resolve().parent
sys.path.insert(0, str(THU_MUC))
F_CAU_HINH = Path.home() / ".tach_van_ban_cauhinh.json"

ENGINE = {"Tesseract (khuyên dùng)": "tesseract", "Screen AI của Chrome (thử nghiệm)": "screenai"}
VI_TRI = {"Không cố định": "tu_dong", "Đầu file": "dau", "Cuối file": "cuoi"}
# Kiểu sắp xếp hồ sơ = (mỗi file một/nhiều văn bản, vị trí văn bản), kèm mô tả cách cắt
KIEU_SAP_XEP = {
    "1 văn bản, xếp ở đầu file": (
        "mot", "Đầu file",
        "Văn bản = từ đầu file tới hết lời chứng đầu tiên; phần sau là hồ sơ. Tờ bìa trước văn bản được gộp vào. "
        "Chắc chắn nhất nếu đơn vị luôn scan văn bản trước hồ sơ."),
    "Nhiều văn bản, xếp liền nhau ở đầu file": (
        "nhieu", "Đầu file",
        "Giữ mọi văn bản từ đầu file cho tới trang hồ sơ rõ ràng đầu tiên (phiếu yêu cầu, CCCD, sổ đỏ, bản sao…); "
        "từ đó trở xuống là hồ sơ. Mỗi văn bản ra 1 file (…__vb1, …__vb2)."),
    "1 văn bản, xếp ở cuối file": (
        "mot", "Cuối file",
        "Văn bản = văn bản có lời chứng cuối cùng; phía trước là hồ sơ."),
    "Nhiều văn bản, xếp liền nhau ở cuối file": (
        "nhieu", "Cuối file",
        "Giữ mọi văn bản từ cuối file ngược lên tới trang hồ sơ rõ ràng gần nhất; phía trước là hồ sơ."),
    "1 văn bản, vị trí không cố định (chấm điểm)": (
        "mot", "Không cố định",
        "Không biết văn bản nằm đâu: chấm điểm theo các dấu hiệu bên dưới để chọn 1 văn bản chính, các văn bản "
        "khác để ở hồ sơ."),
    "Nhiều văn bản, xếp xen kẽ với hồ sơ (chấm điểm)": (
        "nhieu", "Không cố định",
        "Văn bản và hồ sơ xen kẽ (VB1, hồ sơ 1, VB2…): chấm điểm theo các dấu hiệu bên dưới, giữ văn bản của đơn "
        "vị, loại bản sao văn bản cũ lưu trong hồ sơ."),
}
MAU_VB = ["{ten}", "{ten}_VB", "{so_ten}-{nam_ten}", "{nam}_{so_cc}", "{nam}_{so_cc}_{loai}", "{so_cc}_{loai}",
          "{ngay}_{so_cc}"]
MAU_HS = ["{ten}", "{ten}_HS", "{nam}_{so_cc}_HS", "{so_cc}_HS"]
NHAN_TT = {"DAT": ("Đạt", "#15803d"), "CAN_KIEM_TRA": ("Cần kiểm tra", "#b45309"),
           "KHONG_THAY": ("Không thấy", "#b91c1c"), "LOI": ("Lỗi", "#7f1d1d")}


def mo(duong_dan):
    duong_dan = str(duong_dan)
    if not os.path.exists(duong_dan):
        messagebox.showinfo("Chưa có", f"Chưa có:\n{duong_dan}\n\nHãy chạy tách trước.")
        return
    if sys.platform == "win32":
        os.startfile(duong_dan)  # noqa
    elif sys.platform == "darwin":
        subprocess.Popen(["open", duong_dan])
    else:
        subprocess.Popen(["xdg-open", duong_dan])


class GoiY:
    """Chú thích hiện khi rê chuột."""

    def __init__(self, w, text):
        self.w, self.text, self.tip = w, text, None
        w.bind("<Enter>", self.hien)
        w.bind("<Leave>", self.an)

    def hien(self, _):
        x, y = self.w.winfo_rootx() + 20, self.w.winfo_rooty() + self.w.winfo_height() + 4
        self.tip = tk.Toplevel(self.w)
        self.tip.wm_overrideredirect(True)
        self.tip.wm_geometry(f"+{x}+{y}")
        tk.Label(self.tip, text=self.text, justify="left", background="#fffbe6", relief="solid", borderwidth=1,
                 wraplength=380, padx=6, pady=4).pack()

    def an(self, _):
        if self.tip:
            self.tip.destroy()
            self.tip = None


class UngDung(tk.Tk):
    def __init__(self, tvb):
        super().__init__()
        self.tvb = tvb
        self.title(f"Tách văn bản công chứng · {tvb.PHIEN_BAN}")
        self.geometry("1280x800")
        self.minsize(1000, 680)
        self.q = queue.Queue()
        self.dung = threading.Event()
        self.luong = None
        self._kieu()
        self._bien()
        self._dung_giao_dien()
        self._nap_cau_hinh()
        self._doi_nut_ocr()
        self.after(100, self._doc_hang_doi)
        self.after(300, self.kiem_tra_ocr)
        self.after(1500, lambda: self.v["kiem_tra_cap_nhat"].get() and self.kiem_tra_cap_nhat(tu_dong=True))
        self.protocol("WM_DELETE_WINDOW", self._dong)

    # ------------------------------------------------------------------ giao diện
    def _kieu(self):
        st = ttk.Style(self)
        if "vista" in st.theme_names():
            st.theme_use("vista")
        elif "clam" in st.theme_names():
            st.theme_use("clam")
            st.configure("Horizontal.TProgressbar", background="#16a34a")
        st.configure("TLabelframe.Label", font=("Segoe UI", 10, "bold"))
        st.configure("Goiy.TLabel", foreground="#6b7280")
        st.configure("Lon.TButton", font=("Segoe UI", 11, "bold"), padding=(14, 6))

    def _bien(self):
        md = self.tvb.cfg_mac_dinh()
        self.v = dict(
            vao=tk.StringVar(), ra=tk.StringVar(),
            mot_van_ban=tk.StringVar(value="mot" if md["mot_van_ban"] else "nhieu"),
            vi_tri=tk.StringVar(value="Không cố định"),
            kieu_sap_xep=tk.StringVar(),  # chỉ để hiển thị: suy ra từ mot_van_ban + vi_tri
            so_cc_trong_ten=tk.BooleanVar(value=md["so_cc_trong_ten"]),
            uu_tien_ngay_moi=tk.BooleanVar(value=md["uu_tien_ngay_moi"]),
            ten_to_chuc=tk.StringVar(value=md["ten_to_chuc"]),
            can_quoc_hieu=tk.BooleanVar(value=md["can_quoc_hieu"]),
            giu_trang_trang=tk.BooleanVar(value=md["giu_trang_trang"]),
            engine=tk.StringVar(value="Tesseract (khuyên dùng)"),
            dpi=tk.StringVar(value=str(md["dpi"])),
            so_luong=tk.StringVar(value=str(max(1, min(6, (os.cpu_count() or 2) // 2)))),  # quá nhiều thì tranh CPU, RAM
            tesseract=tk.StringVar(value=self.tvb.tim_tesseract() or ""),
            luon_ocr=tk.BooleanVar(value=False),
            xuat_ho_so=tk.BooleanVar(value=False),
            xem_tat_ca=tk.BooleanVar(value=False),
            luu_chu=tk.BooleanVar(value=False),
            gioi_han=tk.StringVar(value="0"),
            kiem_tra_cap_nhat=tk.BooleanVar(value=True),
            mau_ten_vb=tk.StringVar(value=md["mau_ten_vb"]),
            mau_ten_hs=tk.StringVar(value=md["mau_ten_hs"]),
            bo_trang_trang_ho_so=tk.BooleanVar(value=md["bo_trang_trang_ho_so"]),
        )

    def _dung_giao_dien(self):
        goc = ttk.Frame(self, padding=10)
        goc.pack(fill="both", expand=True)
        goc.columnconfigure(0, weight=0, minsize=560)
        goc.columnconfigure(1, weight=1)
        goc.rowconfigure(1, weight=1)

        dau = ttk.Frame(goc)
        dau.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 8))
        ttk.Label(dau, text="Tách văn bản công chứng khỏi hồ sơ lưu", font=("Segoe UI", 14, "bold")).pack(side="left")
        ttk.Label(dau, text="   Chạy hoàn toàn trên máy này · không gửi dữ liệu ra ngoài", style="Goiy.TLabel").pack(side="left")
        w = ttk.Button(dau, text="Kiểm tra bản mới", command=lambda: self.kiem_tra_cap_nhat(tu_dong=False))
        w.pack(side="right")
        ttk.Label(dau, text=f"Phiên bản {self.tvb.PHIEN_BAN}", style="Goiy.TLabel").pack(side="right", padx=8)
        # dải báo bản mới: chỉ hiện khi GitHub có bản phát hành mới hơn
        self.dai_moi = tk.Frame(goc, bg="#dcfce7", highlightbackground="#86efac", highlightthickness=1)
        # nút đóng gói trước để luôn đủ chỗ, chữ co lại nếu cửa sổ hẹp
        ttk.Button(self.dai_moi, text="Ẩn", width=5, command=self.dai_moi.grid_remove).pack(side="right", padx=6, pady=4)
        ttk.Button(self.dai_moi, text="Xem có gì mới", command=lambda: webbrowser.open(self._ban_moi["trang"])) \
            .pack(side="right", padx=(0, 4), pady=4)
        tu_cai = self.tvb.la_ban_cai()
        self.nut_cap_nhat = ttk.Button(self.dai_moi, text="⬆ Cập nhật ngay" if tu_cai else "⬇ Tải bản mới",
                                       command=self._cap_nhat_ngay)
        self.nut_cap_nhat.pack(side="right", padx=4, pady=4)
        self.lb_moi = tk.Label(self.dai_moi, text="", bg="#dcfce7", fg="#14532d", font=("Segoe UI", 10, "bold"))
        self.lb_moi.pack(side="left", padx=10, pady=6)
        self.lb_moi_phu = tk.Label(self.dai_moi, bg="#dcfce7", fg="#166534", anchor="w",
                                   text="Bấm Cập nhật ngay: phần mềm tự tải, tự cài rồi tự mở lại." if tu_cai else
                                   "Bản không cần cài: tải file zip mới, giải nén đè lên thư mục cũ.")
        self.lb_moi_phu.pack(side="left", fill="x", expand=True)
        GoiY(self.lb_moi_phu, "Không cần gỡ bản cũ. Cấu hình, gói tiếng Việt và thư mục kết quả cũ được giữ nguyên.")
        self._ban_moi = None

        self.dai_moi.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(0, 8))
        self.dai_moi.grid_remove()
        goc.rowconfigure(1, weight=0)
        goc.rowconfigure(2, weight=1)
        trai = ttk.Frame(goc)
        trai.grid(row=2, column=0, sticky="nsew", padx=(0, 10))
        phai = ttk.Frame(goc)
        phai.grid(row=2, column=1, sticky="nsew")
        self._khung_thu_muc(trai)
        self._khung_cau_truc(trai)
        self._khung_ocr(trai)
        self._khung_chay(phai)

    def _o_chon(self, cha, hang, nhan, bien, lenh, goi_y=None):
        ttk.Label(cha, text=nhan).grid(row=hang, column=0, sticky="w", pady=2)
        e = ttk.Entry(cha, textvariable=bien)
        e.grid(row=hang, column=1, sticky="ew", padx=4, pady=2)
        ttk.Button(cha, text="Chọn…", command=lenh, width=7).grid(row=hang, column=2, pady=2)
        if goi_y:
            GoiY(e, goi_y)
        return e

    def _khung_thu_muc(self, cha):
        f = ttk.LabelFrame(cha, text="1. Thư mục", padding=8)
        f.pack(fill="x", pady=(0, 8))
        f.columnconfigure(1, weight=1)
        self._o_chon(f, 0, "PDF scan (đầu vào):", self.v["vao"], self.chon_vao,
                     "Thư mục chứa các file PDF scan gộp. Quét cả các thư mục con.")
        self._o_chon(f, 1, "Kết quả (đầu ra):", self.v["ra"], self.chon_ra,
                     "Nơi ghi văn bản đã tách, bảng báo cáo và trang xem lại. Nên là thư mục riêng.")
        self.lb_dem = ttk.Label(f, text="", style="Goiy.TLabel")
        self.lb_dem.grid(row=2, column=1, sticky="w", padx=4)

    def _khung_cau_truc(self, cha):
        f = ttk.LabelFrame(cha, text="2. Cấu trúc hồ sơ của đơn vị", padding=8)
        f.pack(fill="x", pady=(0, 8))
        f.columnconfigure(1, weight=1)
        ttk.Label(f, text="Giúp phân biệt văn bản công chứng với bản sao hợp đồng cũ lưu trong hồ sơ.",
                  style="Goiy.TLabel").grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 4))

        ttk.Label(f, text="Kiểu sắp xếp:").grid(row=1, column=0, sticky="w", pady=2)
        cb = ttk.Combobox(f, textvariable=self.v["kieu_sap_xep"], values=list(KIEU_SAP_XEP), state="readonly")
        cb.grid(row=1, column=1, columnspan=2, sticky="ew", padx=4, pady=2)
        cb.bind("<<ComboboxSelected>>", self._chon_kieu_sap_xep)
        GoiY(cb, "Đơn vị xếp văn bản và hồ sơ trong file scan thế nào. Biết chắc văn bản luôn ở đầu (hoặc cuối) "
                 "file thì chọn kiểu đó: công cụ chỉ cần tìm ranh giới văn bản / hồ sơ, chính xác hơn chấm điểm. "
                 "Không chắc hoặc xếp xen kẽ thì chọn kiểu chấm điểm.")
        self.lb_kieu = ttk.Label(f, text="", style="Goiy.TLabel", wraplength=520, justify="left")
        self.lb_kieu.grid(row=2, column=1, columnspan=2, sticky="w", padx=4)
        ttk.Separator(f).grid(row=3, column=0, columnspan=3, sticky="ew", pady=6)
        self.lb_dau_hieu = ttk.Label(f, text="", style="Goiy.TLabel", wraplength=540, justify="left")
        self.lb_dau_hieu.grid(row=4, column=0, columnspan=3, sticky="w")
        for k in ("mot_van_ban", "vi_tri"):
            self.v[k].trace_add("write", lambda *a: self._hien_kieu_sap_xep())
        self._hien_kieu_sap_xep()
        w = ttk.Checkbutton(f, text="Số công chứng có trong tên file/thư mục (vd 2022_1234.pdf, 1234_1235.pdf)",
                            variable=self.v["so_cc_trong_ten"])
        w.grid(row=5, column=0, columnspan=3, sticky="w", pady=2)
        GoiY(w, "Đọc dòng 'Số công chứng …' trong lời chứng và so với các con số trong tên file, tên thư mục. "
                "Khớp: là văn bản của đơn vị. Đọc được số mà không khớp: là bản sao trong hồ sơ. "
                "Đây là dấu hiệu mạnh nhất nếu đơn vị đặt tên file theo số công chứng.")
        w = ttk.Checkbutton(f, text="Ngày công chứng mới nhất (cũ hơn quá 30 ngày coi là bản sao trong hồ sơ)",
                            variable=self.v["uu_tien_ngay_moi"])
        w.grid(row=6, column=0, columnspan=3, sticky="w", pady=2)
        GoiY(w, "So ngày ghi trong lời chứng của các văn bản trong cùng file. Văn bản cũ hơn văn bản mới nhất quá "
                "30 ngày bị coi là bản sao lưu trong hồ sơ. Các giao dịch cùng ngày hoặc gần ngày đều được giữ.")
        ttk.Label(f, text="Tên tổ chức:").grid(row=7, column=0, sticky="w", pady=2)
        w = ttk.Entry(f, textvariable=self.v["ten_to_chuc"])
        w.grid(row=7, column=1, columnspan=2, sticky="ew", padx=4, pady=2)
        GoiY(w, "Tên tổ chức hành nghề công chứng của đơn vị, vd: Văn phòng công chứng Hòa An. "
                "Lời chứng ghi đúng tên này: văn bản của đơn vị. Ghi tên văn phòng/phòng công chứng khác: bản sao "
                "trong hồ sơ. Để trống nếu không dùng.")
        ttk.Label(f, text="Ghi ngắn: chỉ tên văn phòng, không ghi địa chỉ hay tỉnh/thành.", style="Goiy.TLabel") \
            .grid(row=8, column=1, columnspan=2, sticky="w", padx=4)

        ttk.Separator(f).grid(row=9, column=0, columnspan=3, sticky="ew", pady=6)
        w = ttk.Checkbutton(f, text="Văn bản luôn có Quốc hiệu (bỏ tick nếu có loại văn bản không có Quốc hiệu)",
                            variable=self.v["can_quoc_hieu"])
        w.grid(row=10, column=0, columnspan=3, sticky="w", pady=2)
        w = ttk.Checkbutton(f, text="Giữ trang trắng nằm giữa văn bản (mặc định bỏ đi)", variable=self.v["giu_trang_trang"])
        w.grid(row=11, column=0, columnspan=3, sticky="w", pady=2)
        GoiY(w, "Bật nếu cần giữ đúng số tờ như bản scan (vd scan 2 mặt có mặt sau trắng).")

    def _chon_kieu_sap_xep(self, _e=None):
        mot, vi_tri, _ = KIEU_SAP_XEP[self.v["kieu_sap_xep"].get()]
        self.v["mot_van_ban"].set(mot)
        self.v["vi_tri"].set(vi_tri)

    def _hien_kieu_sap_xep(self):
        hien = (self.v["mot_van_ban"].get(), self.v["vi_tri"].get())
        ten = next((k for k, (m, vt, _) in KIEU_SAP_XEP.items() if (m, vt) == hien), "")
        self.v["kieu_sap_xep"].set(ten)
        self.lb_kieu.config(text=KIEU_SAP_XEP[ten][2] if ten else "")
        cham_diem = hien[1] == "Không cố định"
        self.lb_dau_hieu.config(text=(
            "Dấu hiệu nhận ra văn bản của đơn vị — dùng để chấm điểm, loại bản sao văn bản cũ lưu lẫn trong hồ sơ:"
            if cham_diem else
            "Dấu hiệu đối chiếu — không dùng để chọn văn bản, chỉ báo 'cần kiểm tra' khi nghi lấy nhầm bản sao:"))

    def _khung_ocr(self, cha):
        f = ttk.LabelFrame(cha, text="3. Đọc chữ (OCR)", padding=8)
        f.pack(fill="x", pady=(0, 8))
        f.columnconfigure(1, weight=1)
        r = ttk.Frame(f)
        r.grid(row=0, column=0, columnspan=3, sticky="w", pady=2)
        ttk.Label(r, text="Công cụ:").pack(side="left")
        cb = ttk.Combobox(r, textvariable=self.v["engine"], values=list(ENGINE), state="readonly", width=30)
        cb.pack(side="left", padx=(4, 14))
        cb.bind("<<ComboboxSelected>>", lambda e: (self._doi_nut_ocr(), self.kiem_tra_ocr()))
        ttk.Label(r, text="Độ nét:").pack(side="left")
        w = ttk.Combobox(r, textvariable=self.v["dpi"], values=["150", "200", "300"], state="readonly", width=5)
        w.pack(side="left", padx=(4, 2))
        GoiY(w, "200 là đủ cho hầu hết bản scan. Tăng lên 300 nếu chữ nhỏ hoặc bản scan mờ (chậm hơn).")
        ttk.Label(r, text="dpi    Song song:").pack(side="left")
        w = ttk.Spinbox(r, from_=1, to=max(1, os.cpu_count() or 1), textvariable=self.v["so_luong"], width=4)
        w.pack(side="left", padx=4)
        GoiY(w, "Số file xử lý cùng lúc. Mặc định = số nhân CPU − 1. Giảm xuống nếu máy bị chậm khi đang chạy.")

        self._o_chon(f, 1, "Tesseract:", self.v["tesseract"], self.chon_tesseract,
                     "Đường dẫn tới tesseract.exe. Thường tự tìm thấy nếu cài vào C:\\Program Files\\Tesseract-OCR.")
        r = ttk.Frame(f)
        r.grid(row=2, column=0, columnspan=3, sticky="ew", pady=(2, 0))
        ttk.Button(r, text="Kiểm tra", command=self.kiem_tra_ocr).pack(side="left")
        w = ttk.Button(r, text="Tải Tesseract…", command=lambda: webbrowser.open(self.tvb.URL_TESSERACT))
        w.pack(side="left", padx=(6, 0))
        GoiY(w, "Mở trang tải bộ cài Tesseract cho Windows (UB Mannheim). Khi cài, ở mục Additional language "
                "data nhớ tick Vietnamese — hoặc bấm 'Tải gói tiếng Việt' sau khi cài.")
        self.nut_tai_goi = ttk.Button(r, text="Tải gói tiếng Việt", command=self.tai_goi)
        self.nut_tai_goi.pack(side="left", padx=(6, 0))
        GoiY(self.nut_tai_goi, "Tự tải mô hình tiếng Việt (vie.traineddata, ~0,5 MB) từ kho chính thức của Tesseract "
                               "về thư mục riêng của bạn — không cần quyền quản trị, không cần cài lại Tesseract.")
        w = ttk.Button(r, text="Tải thủ công…", command=lambda: webbrowser.open(self.tvb.URL_TRANG_GOI))
        w.pack(side="left", padx=(6, 0))
        GoiY(w, "Mở kho mô hình ngôn ngữ của Tesseract nếu máy không tải tự động được (vd mạng cơ quan chặn). "
                "Tải vie.traineddata rồi chép vào:\n" + str(self.tvb.thu_muc_goi_rieng()))
        self.nut_screen_ai = ttk.Button(r, text="Kích hoạt Screen AI", command=self.kich_hoat_screen_ai)
        GoiY(self.nut_screen_ai, "Dùng bộ nhận dạng chữ Screen AI mà Chrome trên máy đã tải về (không tải gì từ "
                                 "Internet): sao lưu sang thư mục riêng rồi chạy thử. Tính năng thử nghiệm; Screen AI "
                                 "là phần mềm mã đóng của Google.")
        self._nut_tesseract = [x for x in r.winfo_children() if x is not self.nut_screen_ai][1:]
        self.lb_ocr = ttk.Label(f, text="", wraplength=520)
        self.lb_ocr.grid(row=3, column=0, columnspan=3, sticky="w", pady=(4, 0))
        ttk.Checkbutton(f, text="OCR lại cả trang đã có sẵn lớp chữ (khi lớp chữ do máy scan tạo bị sai)",
                        variable=self.v["luon_ocr"]).grid(row=4, column=0, columnspan=3, sticky="w", pady=(4, 0))

    def _khung_dau_ra(self, cha, hang):
        f = ttk.LabelFrame(cha, text="4. Đầu ra", padding=8)
        f.grid(row=hang, column=0, sticky="ew", pady=(0, 8))
        f.columnconfigure(1, weight=1)
        goi_y_ten = ("Mẫu đặt tên file, gõ tự do hoặc chọn sẵn. Các trường:\n"
                     + "\n".join(f"{{{k}}}  {v}" for k, v in self.tvb.TRUONG_TEN.items())
                     + "\n\nVăn bản nào thiếu số/ngày/loại (OCR không đọc được) sẽ giữ tên gốc; điền tay vào cột "
                       "so_cong_chung / ngay_cong_chung / loai_van_ban trong bảng Excel rồi cắt bản chốt để đặt lại. "
                       "Trùng tên thì tự thêm (2), (3)…")
        ttk.Label(f, text="Tên file văn bản:").grid(row=0, column=0, sticky="w")
        w = ttk.Combobox(f, textvariable=self.v["mau_ten_vb"], values=MAU_VB)
        w.grid(row=0, column=1, columnspan=2, sticky="ew", padx=(4, 0))
        GoiY(w, goi_y_ten)
        self.lb_vi_du = ttk.Label(f, text="", style="Goiy.TLabel")
        self.lb_vi_du.grid(row=1, column=1, columnspan=2, sticky="w", padx=(4, 0))
        r = ttk.Frame(f)
        r.grid(row=2, column=0, columnspan=3, sticky="ew", pady=(2, 0))
        ttk.Checkbutton(r, text="Xuất thêm phần hồ sơ còn lại, tên:", variable=self.v["xuat_ho_so"]).pack(side="left")
        w = ttk.Combobox(r, textvariable=self.v["mau_ten_hs"], values=MAU_HS, width=18)
        w.pack(side="left", padx=4, fill="x", expand=True)
        GoiY(w, goi_y_ten + "\n\nFile hồ sơ nằm trong thư mục ho_so (khi tách) và chot_ho_so (khi cắt bản chốt).")
        w = ttk.Checkbutton(f, text="Bỏ trang trắng khỏi phần hồ sơ", variable=self.v["bo_trang_trang_ho_so"])
        w.grid(row=3, column=0, columnspan=3, sticky="w", padx=(22, 0))
        GoiY(w, "Áp dụng cho phần hồ sơ khi tách và khi cắt bản chốt. Văn bản công chứng thì mặc định đã bỏ trang "
                "trắng (muốn giữ thì tick 'Giữ trang trắng nằm giữa văn bản' ở mục 2).")
        for k in ("mau_ten_vb", "mau_ten_hs"):
            self.v[k].trace_add("write", lambda *_: self._cap_nhat_vi_du())
        ttk.Checkbutton(f, text="Ảnh thu nhỏ cho cả file đạt (để soát kỹ khi chạy thử)", variable=self.v["xem_tat_ca"]) \
            .grid(row=4, column=0, columnspan=3, sticky="w")
        w = ttk.Checkbutton(f, text="Lưu chữ OCR để dò lỗi (thư mục chu_ocr — có dữ liệu cá nhân)",
                            variable=self.v["luu_chu"])
        w.grid(row=5, column=0, columnspan=3, sticky="w")
        r = ttk.Frame(f)
        r.grid(row=6, column=0, columnspan=3, sticky="w", pady=(4, 0))
        ttk.Label(r, text="Chỉ chạy thử").pack(side="left")
        ttk.Spinbox(r, from_=0, to=100000, textvariable=self.v["gioi_han"], width=7).pack(side="left", padx=4)
        ttk.Label(r, text="file đầu tiên (0 = tất cả)", style="Goiy.TLabel").pack(side="left")
        w = ttk.Checkbutton(f, text="Tự kiểm tra bản mới khi mở phần mềm", variable=self.v["kiem_tra_cap_nhat"])
        w.grid(row=7, column=0, columnspan=3, sticky="w", pady=(4, 0))
        self._cap_nhat_vi_du()
        GoiY(w, "Khi mở, phần mềm hỏi GitHub số phiên bản mới nhất để báo nếu có bản mới. "
                "Chỉ gửi đúng yêu cầu này, không gửi bất kỳ dữ liệu hồ sơ nào. Bỏ tick nếu muốn phần mềm "
                "hoàn toàn không kết nối mạng.")

    def _khung_chay(self, cha):
        cha.rowconfigure(4, weight=1)
        cha.columnconfigure(0, weight=1)
        self._khung_dau_ra(cha, 0)
        r = ttk.Frame(cha)
        r.grid(row=1, column=0, sticky="ew")
        self.nut_chay = ttk.Button(r, text="▶  Bắt đầu tách", style="Lon.TButton", command=self.bat_dau)
        self.nut_chay.pack(side="left")
        self.nut_dung = ttk.Button(r, text="■  Dừng", command=self.dung_lai, state="disabled")
        self.nut_dung.pack(side="left", padx=8)

        r = ttk.Frame(cha)
        r.grid(row=2, column=0, sticky="ew", pady=(10, 2))
        r.columnconfigure(0, weight=1)
        self.tien_do = ttk.Progressbar(r, mode="determinate")
        self.tien_do.grid(row=0, column=0, sticky="ew")
        self.lb_tien_do = ttk.Label(r, text="Chưa chạy", width=22, anchor="e")
        self.lb_tien_do.grid(row=0, column=1, padx=(8, 0))

        r = ttk.Frame(cha)
        r.grid(row=3, column=0, sticky="w", pady=(4, 6))
        self.lb_dem_tt = {}
        for k, (ten, mau) in NHAN_TT.items():
            o = tk.Label(r, text=f"{ten}: 0", fg="white", bg=mau, padx=8, pady=2, font=("Segoe UI", 9, "bold"))
            o.pack(side="left", padx=(0, 6))
            self.lb_dem_tt[k] = (o, ten)
        self.lb_thieu = tk.Label(r, text="Thiếu trang: 0", fg="#b91c1c", bg="#fee2e2", padx=8, pady=2,
                                 font=("Segoe UI", 9, "bold"))
        self.lb_thieu.pack(side="left", padx=(6, 0))
        GoiY(self.lb_thieu, "Số file có văn bản nghi thiếu, thừa hoặc trùng trang (so với số trang ghi trong lời "
                            "chứng, số trang in, số Điều). Xem chi tiết ở cột nghi_thieu_trang trong bảng Excel, "
                            "hoặc bấm lọc 'Nghi thiếu/thừa trang' trong trang xem lại.")

        self.nhat_ky = ScrolledText(cha, height=8, font=("Consolas", 9), wrap="none", state="disabled")
        self.nhat_ky.grid(row=4, column=0, sticky="nsew")

        r = ttk.Frame(cha)
        r.grid(row=5, column=0, sticky="ew", pady=(8, 0))
        ttk.Button(r, text="Mở trang xem lại", command=lambda: self._mo_ket_qua("xem_lai.html")).pack(side="left")
        ttk.Button(r, text="Mở bảng Excel", command=lambda: self._mo_ket_qua("bao_cao.xlsx")).pack(side="left", padx=6)
        ttk.Button(r, text="Mở thư mục kết quả", command=lambda: self._mo_ket_qua("")).pack(side="left")

        f = ttk.LabelFrame(cha, text="5. Sau khi soát lại", padding=8)
        f.grid(row=6, column=0, sticky="ew", pady=(10, 0))
        lb = ttk.Label(f, text="Sửa cột trang_van_ban trong bao_cao.xlsx cho các file sai (vd 3-7; nhiều văn bản: "
                               "3-7;12-15; bỏ qua: BO), lưu lại rồi bấm nút dưới. Bộ file cuối cùng để tải lên nằm "
                               "ở thư mục chot.", justify="left")
        lb.pack(anchor="w", fill="x")
        lb.bind("<Configure>", lambda e: lb.configure(wraplength=max(200, e.width - 8)))
        self.nut_chot = ttk.Button(f, text="Cắt bản chốt theo bảng Excel", command=self.cat_chot)
        self.nut_chot.pack(anchor="w", pady=(6, 0))

    def _cap_nhat_vi_du(self):
        """Xem trước tên file với một văn bản mẫu."""
        if not hasattr(self, "lb_vi_du"):
            return
        tvb = self.tvb
        gt = tvb.gia_tri_ten("027529-23.pdf", "027529", (2023, 11, 30), "GIẤY ỦY QUYỀN", 1)
        loi = tvb.kiem_tra_mau_ten(self.v["mau_ten_vb"].get()) or (
            tvb.kiem_tra_mau_ten(self.v["mau_ten_hs"].get()) and "Tên hồ sơ: " + tvb.kiem_tra_mau_ten(self.v["mau_ten_hs"].get()))
        if loi:
            self.lb_vi_du.configure(text="✖ " + loi, foreground="#b91c1c")
            return
        vb, _ = tvb.duong_dan_theo_mau("027529-23.pdf", self.v["mau_ten_vb"].get(), gt, 1)
        self.lb_vi_du.configure(text=f"Ví dụ: 027529-23.pdf → {vb}", foreground="#6b7280")

    # ------------------------------------------------------------------ thao tác
    def chon_vao(self):
        d = filedialog.askdirectory(title="Chọn thư mục chứa PDF scan", initialdir=self.v["vao"].get() or None)
        if d:
            self.v["vao"].set(d)
            if not self.v["ra"].get():
                self.v["ra"].set(str(Path(d).parent / (Path(d).name + "_ket_qua")))
            self._dem_file()

    def chon_ra(self):
        d = filedialog.askdirectory(title="Chọn thư mục ghi kết quả", initialdir=self.v["ra"].get() or None)
        if d:
            self.v["ra"].set(d)

    def chon_tesseract(self):
        f = filedialog.askopenfilename(title="Chọn tesseract.exe",
                                       filetypes=[("tesseract", "tesseract*"), ("Tất cả", "*")])
        if f:
            self.v["tesseract"].set(f)
            self.kiem_tra_ocr()

    def _dem_file(self):
        vao, ra = self.v["vao"].get(), self.v["ra"].get() or "__khong_co__"

        def dem():
            try:
                n = len(self.tvb.liet_ke_pdf(vao, ra))
                self.q.put(("dem", f"Tìm thấy {n} file PDF"))
            except Exception as e:
                self.q.put(("dem", f"Không đọc được thư mục: {e}"))

        self.lb_dem.configure(text="Đang đếm file…")
        threading.Thread(target=dem, daemon=True).start()

    def _cfg(self) -> dict:
        v = self.v
        cfg = self.tvb.cfg_mac_dinh()
        cfg.update(
            mot_van_ban=v["mot_van_ban"].get() == "mot", vi_tri=VI_TRI[v["vi_tri"].get()],
            so_cc_trong_ten=v["so_cc_trong_ten"].get(), uu_tien_ngay_moi=v["uu_tien_ngay_moi"].get(),
            ten_to_chuc=v["ten_to_chuc"].get().strip(), can_quoc_hieu=v["can_quoc_hieu"].get(),
            giu_trang_trang=v["giu_trang_trang"].get(), engine=ENGINE[v["engine"].get()],
            dpi=int(v["dpi"].get() or 200), tesseract=v["tesseract"].get().strip() or None,
            luon_ocr=v["luon_ocr"].get(), xuat_ho_so=v["xuat_ho_so"].get(), xem_tat_ca=v["xem_tat_ca"].get(),
            bo_trang_trang_ho_so=v["bo_trang_trang_ho_so"].get(),
            luu_chu=v["luu_chu"].get(),
            mau_ten_vb=v["mau_ten_vb"].get().strip() or "{ten}", mau_ten_hs=v["mau_ten_hs"].get().strip() or "{ten}",
        )
        return cfg

    def _doi_nut_ocr(self):
        """Hiện nút theo công cụ đang chọn: Tesseract (tải Tesseract, gói tiếng Việt) hoặc Screen AI (kích hoạt)."""
        la_sai = ENGINE.get(self.v["engine"].get()) == "screenai"
        for w in self._nut_tesseract:
            w.pack_forget()
        self.nut_screen_ai.pack_forget()
        if la_sai:
            self.nut_screen_ai.pack(side="left", padx=(6, 0))
        else:
            for w in self._nut_tesseract:
                w.pack(side="left", padx=(6, 0))

    def kich_hoat_screen_ai(self):
        tt, tb = self.tvb.trang_thai_screen_ai()
        if tt == "chua_co_thu_vien":
            messagebox.showinfo("Screen AI", tb)
            return
        if tt == "chua_co_mo_hinh":
            chrome = self.tvb.tim_chrome()
            if chrome and messagebox.askyesno("Screen AI", self.tvb.HUONG_DAN_SCREEN_AI + "\n\nMở Chrome ngay?"):
                import subprocess
                subprocess.Popen([chrome, "chrome://components"])
            elif not chrome:
                messagebox.showinfo("Screen AI", "Máy chưa cài Google Chrome. Screen AI chỉ dùng được khi có Chrome; "
                                                 "hãy dùng Tesseract.")
            return
        self.nut_screen_ai.configure(state="disabled")
        self.lb_ocr.configure(text="Đang kích hoạt và chạy thử Screen AI…", foreground="#374151")

        def chay():
            try:
                self.q.put(("screen_ai", (True, self.tvb.kich_hoat_screen_ai())))
            except Exception as e:
                self.q.put(("screen_ai", (False, f"{type(e).__name__}: {e}")))

        threading.Thread(target=chay, daemon=True).start()

    def kiem_tra_ocr(self):
        ok, tb = self.tvb.kiem_tra_ocr(self._cfg())
        self.lb_ocr.configure(text=("✔ " if ok else "✖ ") + tb, foreground="#15803d" if ok else "#b91c1c")
        return ok

    def kiem_tra_cap_nhat(self, tu_dong: bool):
        def chay():
            try:
                self.q.put(("ban_moi", (tu_dong, self.tvb.kiem_tra_ban_moi(), None)))
            except Exception as e:
                self.q.put(("ban_moi", (tu_dong, None, str(e))))

        threading.Thread(target=chay, daemon=True).start()

    def _cap_nhat_ngay(self):
        if not self.tvb.la_ban_cai():
            self._tai_ban_moi()
            return
        if self.luong and self.luong.is_alive():
            messagebox.showinfo("Đang chạy", "Đang tách dở. Chờ chạy xong (hoặc bấm Dừng) rồi hãy cập nhật.")
            return
        b = self._ban_moi or {}
        if not messagebox.askyesno("Cập nhật", f"Cập nhật lên bản {b.get('phien_ban')}?\n\n"
                                   "Phần mềm sẽ tải bộ cài (khoảng 45 MB), tự đóng lại, cài bản mới rồi tự mở lại. "
                                   "Cấu hình và kết quả cũ được giữ nguyên."):
            return
        self.nut_cap_nhat.configure(state="disabled")
        self.lb_moi_phu.configure(text="Đang tải bộ cài…")

        def chay():
            try:
                f = self.tvb.tai_bo_cai(b, tien_do=lambda da, tong: self.q.put(("cap_nhat_tien_do", (da, tong))))
                self.q.put(("cap_nhat_xong", str(f)))
            except Exception as e:
                self.q.put(("cap_nhat_loi", str(e)))

        threading.Thread(target=chay, daemon=True).start()

    def _tai_ban_moi(self):
        b = self._ban_moi or {}
        if self.tvb.la_ban_cai():
            link = b.get("tai_cai_dat")
        elif getattr(sys, "frozen", False):
            link = b.get("tai_zip")
        else:
            link = None  # chạy từ mã nguồn: mở trang phát hành
        webbrowser.open(link or b.get("trang") or self.tvb.URL_KHO + "/releases/latest")

    def tai_goi(self):
        self.nut_tai_goi.configure(state="disabled")
        self.lb_ocr.configure(text="Đang tải gói tiếng Việt…", foreground="#374151")

        def chay():
            try:
                self.tvb.tai_goi_tieng_viet(log=lambda s: self.q.put(("log", s)))
                self.q.put(("goi_xong", None))
            except Exception as e:
                self.q.put(("log", f"LỖI tải gói: {e}"))
                self.q.put(("goi_loi", str(e)))

        threading.Thread(target=chay, daemon=True).start()

    def _ghi(self, s):
        self.nhat_ky.configure(state="normal")
        self.nhat_ky.insert("end", s + "\n")
        self.nhat_ky.see("end")
        self.nhat_ky.configure(state="disabled")

    def _dang_chay(self, co):
        self.nut_chay.configure(state="disabled" if co else "normal")
        self.nut_chot.configure(state="disabled" if co else "normal")
        self.nut_dung.configure(state="normal" if co else "disabled")

    def bat_dau(self):
        vao, ra = self.v["vao"].get().strip(), self.v["ra"].get().strip()
        if not vao or not os.path.exists(vao):
            messagebox.showwarning("Thiếu thư mục", "Hãy chọn thư mục chứa PDF scan.")
            return
        if not ra:
            messagebox.showwarning("Thiếu thư mục", "Hãy chọn thư mục ghi kết quả.")
            return
        if Path(ra).resolve() == Path(vao).resolve():
            messagebox.showwarning("Trùng thư mục", "Thư mục kết quả phải khác thư mục đầu vào.")
            return
        if not self._mau_ten_hop_le():
            return
        if not self.kiem_tra_ocr():
            messagebox.showerror("Chưa sẵn sàng", self.lb_ocr.cget("text"))
            return
        cfg = self._cfg()
        if cfg["luu_chu"] and not messagebox.askyesno(
                "Lưu chữ OCR", "Thư mục chu_ocr sẽ chứa toàn bộ chữ đọc được từ hồ sơ (họ tên, số giấy tờ…).\n"
                               "Chỉ bật khi cần dò lỗi và nhớ xoá sau khi dùng. Tiếp tục?"):
            return
        self._luu_cau_hinh()
        try:
            so_luong = max(1, int(self.v["so_luong"].get()))
            gioi_han = max(0, int(self.v["gioi_han"].get() or 0))
        except ValueError:
            messagebox.showwarning("Sai số", "Số luồng và số file chạy thử phải là số nguyên.")
            return
        self.dung.clear()
        self.tien_do.configure(value=0, maximum=1)
        self.lb_tien_do.configure(text="Đang chuẩn bị…")
        for o, ten in self.lb_dem_tt.values():
            o.configure(text=f"{ten}: 0")
        self._dem_hien = {k: 0 for k in NHAN_TT}
        self._dem_thieu = 0
        self.lb_thieu.configure(text="Thiếu trang: 0")
        self._dang_chay(True)

        def chay():
            try:
                self.tvb.chay_tach(vao, ra, cfg, so_luong=so_luong, gioi_han=gioi_han,
                                   log=lambda s: self.q.put(("log", s)),
                                   tien_do=lambda k, n, r: self.q.put(("tien_do", (k, n, r["trang_thai"],
                                                                                    bool(r.get("nghi_thieu_trang"))))),
                                   dung=self.dung)
            except Exception as e:
                self.q.put(("log", f"LỖI: {type(e).__name__}: {e}"))
            self.q.put(("xong", None))

        self.luong = threading.Thread(target=chay, daemon=True)
        self.luong.start()

    def _mau_ten_hop_le(self) -> bool:
        for nhan, k in (("Tên file văn bản", "mau_ten_vb"), ("Tên file hồ sơ", "mau_ten_hs")):
            loi = self.tvb.kiem_tra_mau_ten(self.v[k].get().strip() or "{ten}")
            if loi:
                messagebox.showwarning("Mẫu tên chưa đúng", f"{nhan}: {loi}")
                return False
        return True

    def dung_lai(self):
        self.dung.set()
        self.nut_dung.configure(state="disabled")
        self.lb_tien_do.configure(text="Đang dừng…")
        self._ghi("Đang dừng — bỏ các file đang xử lý dở (lần sau chạy lại), ghi báo cáo cho các file đã xong…")

    def cat_chot(self):
        vao, ra = self.v["vao"].get().strip(), self.v["ra"].get().strip()
        bang = Path(ra) / "bao_cao.xlsx"
        if not bang.exists():
            bang = Path(ra) / "bao_cao.csv"
        if not bang.exists():
            messagebox.showinfo("Chưa có bảng", "Chưa có bao_cao.xlsx trong thư mục kết quả. Hãy chạy tách trước.")
            return
        if not self._mau_ten_hop_le():
            return
        cfg = self._cfg()
        self._dang_chay(True)

        def chay():
            try:
                self.tvb.cat_theo_bang(vao, ra, bang, log=lambda s: self.q.put(("log", s)), cfg=cfg)
            except PermissionError:
                self.q.put(("log", "LỖI: không đọc được bảng — hãy đóng file Excel rồi bấm lại."))
            except Exception as e:
                self.q.put(("log", f"LỖI: {type(e).__name__}: {e}"))
            self.q.put(("xong_chot", None))

        threading.Thread(target=chay, daemon=True).start()

    def _mo_ket_qua(self, ten):
        ra = self.v["ra"].get().strip()
        if not ra:
            messagebox.showinfo("Chưa có", "Chưa chọn thư mục kết quả.")
            return
        mo(Path(ra) / ten if ten else Path(ra))

    def _doc_hang_doi(self):
        try:
            while True:
                loai, gt = self.q.get_nowait()
                if loai == "log":
                    self._ghi(gt)
                elif loai == "dem":
                    self.lb_dem.configure(text=gt)
                elif loai == "tien_do":
                    k, n, tt, thieu = gt
                    if thieu:
                        self._dem_thieu += 1
                        self.lb_thieu.configure(text=f"Thiếu trang: {self._dem_thieu}")
                    self.tien_do.configure(maximum=n, value=k)
                    self.lb_tien_do.configure(text=f"{k}/{n} file")
                    self._dem_hien[tt] = self._dem_hien.get(tt, 0) + 1
                    o, ten = self.lb_dem_tt[tt]
                    o.configure(text=f"{ten}: {self._dem_hien[tt]}")
                elif loai == "xong":
                    self._dang_chay(False)
                    self.lb_tien_do.configure(text="Xong" if not self.dung.is_set() else "Đã dừng")
                    if (Path(self.v["ra"].get()) / "xem_lai.html").exists() and self._dem_hien and any(self._dem_hien.values()):
                        if messagebox.askyesno("Xong", "Đã tách xong. Mở trang xem lại?"):
                            self._mo_ket_qua("xem_lai.html")
                elif loai == "ban_moi":
                    tu_dong, ban, loi = gt
                    if ban:
                        self._ban_moi = ban
                        self.lb_moi.configure(text=f"🔔 Đã có bản mới {ban['phien_ban']} "
                                                   f"(đang dùng {self.tvb.PHIEN_BAN})")
                        self.dai_moi.grid()
                    elif not tu_dong and loi:
                        messagebox.showwarning("Không kiểm tra được",
                                               f"Không kết nối được tới GitHub để kiểm tra bản mới:\n{loi}\n\n"
                                               f"Có thể xem trực tiếp tại {self.tvb.URL_KHO}/releases")
                    elif not tu_dong:
                        messagebox.showinfo("Bản mới nhất", f"Bạn đang dùng bản mới nhất ({self.tvb.PHIEN_BAN}).")
                elif loai == "screen_ai":
                    ok, tb = gt
                    self.nut_screen_ai.configure(state="normal")
                    (messagebox.showinfo if ok else messagebox.showerror)("Screen AI", tb)
                    self.kiem_tra_ocr()
                elif loai == "cap_nhat_tien_do":
                    da, tong = gt
                    self.lb_moi_phu.configure(text=f"Đang tải bộ cài… {da / 1048576:.1f}"
                                                   + (f" / {tong / 1048576:.1f} MB" if tong else " MB"))
                elif loai == "cap_nhat_loi":
                    self.nut_cap_nhat.configure(state="normal")
                    self.lb_moi_phu.configure(text="Tải bộ cài không thành công.")
                    if messagebox.askyesno("Không cập nhật được", f"{gt}\n\nMở trang tải để cập nhật bằng tay?"):
                        webbrowser.open((self._ban_moi or {}).get("trang") or self.tvb.URL_KHO + "/releases/latest")
                elif loai == "cap_nhat_xong":
                    self.lb_moi_phu.configure(text="Đang mở bộ cài, phần mềm sẽ tự mở lại sau khi cài xong…")
                    self.update()
                    try:
                        self.tvb.chay_bo_cai(gt)
                    except Exception as e:
                        self.nut_cap_nhat.configure(state="normal")
                        messagebox.showerror("Không chạy được bộ cài", f"{e}\n\nBộ cài đã tải về: {gt}")
                    else:
                        self._luu_cau_hinh()
                        self.destroy()
                        return
                elif loai in ("goi_xong", "goi_loi"):
                    self.nut_tai_goi.configure(state="normal")
                    if loai == "goi_loi":
                        messagebox.showerror("Không tải được", f"Không tải được gói tiếng Việt:\n{gt}\n\n"
                                             "Bấm 'Tải thủ công…' để tải bằng trình duyệt, rồi chép vie.traineddata vào:\n"
                                             f"{self.tvb.thu_muc_goi_rieng()}")
                    self.kiem_tra_ocr()
                elif loai == "xong_chot":
                    self._dang_chay(False)
                    if messagebox.askyesno("Xong", "Đã cắt bản chốt. Mở thư mục chot?"):
                        self._mo_ket_qua("chot")
        except queue.Empty:
            pass
        self.after(100, self._doc_hang_doi)

    # ------------------------------------------------------------------ cấu hình
    def _luu_cau_hinh(self):
        try:
            F_CAU_HINH.write_text(json.dumps({k: v.get() for k, v in self.v.items()}, ensure_ascii=False, indent=1),
                                  encoding="utf-8")
        except OSError:
            pass

    def _nap_cau_hinh(self):
        try:
            d = json.loads(F_CAU_HINH.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return
        for k, gt in d.items():
            if k in self.v and k != "kieu_sap_xep":
                try:
                    self.v[k].set(gt)
                except tk.TclError:
                    pass
        # Tesseract đi kèm bản đóng gói luôn được ưu tiên; đường dẫn đã lưu không còn tồn tại thì tìm lại
        tim = self.tvb.tim_tesseract()
        da_luu = self.v["tesseract"].get().strip()
        if (tim and Path(tim).parent.parent == self.tvb.thu_muc_ung_dung()) or (da_luu and not os.path.exists(da_luu)):
            self.v["tesseract"].set(tim or "")
        if self.v["vao"].get():
            self._dem_file()

    def _dong(self):
        if self.luong and self.luong.is_alive():
            if not messagebox.askyesno("Đang chạy", "Đang tách dở. Thoát sẽ dừng giữa chừng. Vẫn thoát?"):
                return
            self.dung.set()
        self._luu_cau_hinh()
        self.destroy()


def tu_kiem_tra(thu_muc: str) -> int:
    """Chạy thử toàn bộ trên dữ liệu giả, không mở cửa sổ. Dùng để kiểm tra bản đóng gói (CI).
    Ghi kết quả vào <thu_muc>/tu_kiem_tra.txt; trả về 0 nếu đạt."""
    import tach_van_ban as tvb
    import tao_du_lieu_thu
    goc = Path(thu_muc)
    nhat_ky = []
    try:
        tao_du_lieu_thu.tao_tat_ca(goc / "scan")
        cfg = tvb.cfg_mac_dinh()
        ok, tb = tvb.kiem_tra_ocr(cfg)
        nhat_ky.append(f"OCR: {tb}")
        if not ok:
            raise RuntimeError(tb)
        tt_sai, tb_sai = tvb.trang_thai_screen_ai()
        nhat_ky.append(f"Screen AI: {tt_sai} · {tb_sai}")
        if getattr(sys, "frozen", False) and tt_sai == "chua_co_thu_vien":
            raise RuntimeError("bản đóng gói thiếu thư viện locro")
        kq = tvb.chay_tach(goc / "scan", goc / "ket_qua", cfg, so_luong=2, log=nhat_ky.append)
        tt = {r["duong_dan"][0]: r["trang_thai"] for r in kq}
        nghi_trang = {r["duong_dan"][0] for r in kq if r.get("nghi_thieu_trang")}
        mong_doi_dat = {"A", "B", "E", "H", "M", "Q", "R", "S", "V"}
        mong_doi_nghi_trang = {"J", "K", "N", "O", "P", "T"}  # L: chỉ lộ qua số Điều (dấu hiệu yếu) nên chỉ là lưu ý
        loi = [r["duong_dan"] for r in kq if r["trang_thai"] == "LOI"]
        thieu = sorted(k for k in mong_doi_dat if tt.get(k) != "DAT")
        sai_trang = sorted(mong_doi_nghi_trang ^ nghi_trang)
        nhat_ky.append(f"Trạng thái: {tt}")
        nhat_ky.append(f"Nghi thiếu/thừa trang: {sorted(nghi_trang)}")
        vb = {r["duong_dan"][0]: r["trang_van_ban"] for r in kq}
        cb_t = next((r["canh_bao"] for r in kq if r["duong_dan"][0] == "T"), "")
        if "nằm ngoài văn bản: 6 — văn bản đang thiếu trang" not in cb_t:  # trang scan lạc chỗ phải được chỉ ra
            thieu.append(f"T: không chỉ ra trang scan lạc chỗ ({cb_t[:80]})")
        if vb.get("Q") != "2-6" or vb.get("R") != "3-6":  # tờ bìa: Q gộp vào văn bản, R để ở hồ sơ
            thieu.append(f"tờ bìa: Q={vb.get('Q')} (cần 2-6), R={vb.get('R')} (cần 3-6)")
        # "Một văn bản" + "văn bản ở đầu file": văn bản = từ đầu file tới hết lời chứng đầu tiên (chạy lại, dùng cache)
        kq_dau = tvb.chay_tach(goc / "scan", goc / "ket_qua", dict(cfg, vi_tri="dau"), so_luong=2, log=lambda s: None)
        vb_dau = {r["duong_dan"][0]: (r["trang_thai"], r["trang_van_ban"]) for r in kq_dau}
        nhat_ky.append(f"Văn bản ở đầu file: C={vb_dau.get('C')}, I={vb_dau.get('I')}, A={vb_dau.get('A')}")
        if vb_dau.get("C") != ("DAT", "1-3") or vb_dau.get("I") != ("DAT", "1-3") or vb_dau.get("A") != ("DAT", "3-6"):
            thieu.append(f"tuỳ chọn văn bản ở đầu file: {vb_dau}")
        # "Nhiều văn bản xếp liền nhau ở đầu file": giữ các văn bản tới trang hồ sơ rõ ràng đầu tiên
        kq_nd = tvb.chay_tach(goc / "scan", goc / "ket_qua", dict(cfg, vi_tri="dau", mot_van_ban=False),
                              so_luong=2, log=lambda s: None)
        vb_nd = {r["duong_dan"][0]: (r["trang_thai"], r["trang_van_ban"]) for r in kq_nd}
        nhat_ky.append(f"Nhiều văn bản ở đầu file: I={vb_nd.get('I')}, C={vb_nd.get('C')}, E={vb_nd.get('E')}")
        if vb_nd.get("I") != ("DAT", "1-3;4-6") or vb_nd.get("C") != ("DAT", "1-3") or vb_nd.get("E") != ("DAT", "2-4"):
            thieu.append(f"kiểu nhiều văn bản ở đầu file: {vb_nd}")
        # đặt tên theo số / năm trong tên file gốc (không phụ thuộc OCR)
        for goc_ten, mong in (("007552-24.pdf", ("007552", "2024")), ("2023_027529.pdf", ("027529", "2023")),
                              ("2022/1234.pdf", ("1234", "2022"))):
            if tvb.so_nam_trong_ten(goc_ten) != mong:
                thieu.append(f"tách số/năm từ tên {goc_ten}: {tvb.so_nam_trong_ten(goc_ten)}")
        gt = tvb.gia_tri_ten("007552-24.pdf")
        ten_thu = tvb.duong_dan_theo_mau("007552-24.pdf", "0076-{so_ten}-{nam_ten}-VB", gt, 1)[0]
        if ten_thu != "0076-007552-2024-VB.pdf":
            thieu.append(f"đặt tên theo số/năm trong tên file: {ten_thu}")
        ten_thu = tvb.duong_dan_theo_mau("007552-24.pdf", "0076-{so_cc}-{nam}-VB", gt, 1)[0]
        if ten_thu != "007552-24.pdf":  # không đọc được số CC: giữ tên gốc như trước, không tự đoán
            thieu.append(f"không đọc được số CC mà không giữ tên gốc: {ten_thu}")
        dat = len(kq) == 20 and not loi and not thieu and not sai_trang
        if sai_trang:
            thieu.append(f"kiểm tra số trang sai ở {sai_trang}")
        # bấm Dừng giữa chừng: phải dừng ngay (không chờ file dở) và vẫn ghi báo cáo
        import threading
        import time
        ev = threading.Event()
        threading.Timer(2, ev.set).start()
        t0 = time.time()
        tvb.chay_tach(goc / "scan", goc / "ket_qua_dung", cfg, so_luong=2, log=lambda s: None, dung=ev)
        dung_sau = time.time() - t0
        nhat_ky.append(f"Bấm Dừng sau 2s: dừng hẳn sau {dung_sau:.1f}s")
        if dung_sau > 20:
            dat = False
            thieu.append(f"bấm Dừng mà {dung_sau:.0f}s mới dừng")
        nhat_ky.append("KẾT QUẢ: ĐẠT" if dat else f"KẾT QUẢ: KHÔNG ĐẠT (lỗi: {loi}, không đạt như mong đợi: {thieu})")
    except Exception:
        import traceback
        nhat_ky.append("KẾT QUẢ: LỖI\n" + traceback.format_exc())
        dat = False
    goc.mkdir(parents=True, exist_ok=True)
    (goc / "tu_kiem_tra.txt").write_text("\n".join(nhat_ky), encoding="utf-8")
    return 0 if dat else 1


def main():
    if "--tu-kiem-tra" in sys.argv:
        i = sys.argv.index("--tu-kiem-tra")
        sys.exit(tu_kiem_tra(sys.argv[i + 1] if i + 1 < len(sys.argv) else "tu_kiem_tra"))
    if sys.platform == "win32":
        try:  # chữ nét trên màn hình độ phân giải cao
            import ctypes
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            pass
    try:
        import tach_van_ban as tvb
    except ImportError as e:
        r = tk.Tk()
        r.withdraw()
        messagebox.showerror("Thiếu thư viện",
                             f"Chưa cài đủ thư viện Python ({e.name}).\n\n"
                             "Windows: bấm đúp cai_dat.bat.\nmacOS/Linux: pip install -r requirements.txt")
        return
    UngDung(tvb).mainloop()


if __name__ == "__main__":
    multiprocessing.freeze_support()
    main()
