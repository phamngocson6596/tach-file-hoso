#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Sinh vài file PDF "scan giả" (toàn ảnh, có nhiễu, hơi nghiêng) mô phỏng hồ sơ công chứng
để chạy thử tach_van_ban.py khi chưa muốn dùng hồ sơ thật. Nội dung hoàn toàn bịa.

    python tao_du_lieu_thu.py  du_lieu_thu
"""
import random
import sys
from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter, ImageFont

W, H = 1240, 1754  # A4 @150dpi
random.seed(7)


def font(size, bold=False):
    ung_vien = (["DejaVuSerif-Bold.ttf", "timesbd.ttf", "Times New Roman Bold.ttf"] if bold
                else ["DejaVuSerif.ttf", "times.ttf", "Times New Roman.ttf"])
    for f in ung_vien:
        for thu_muc in ("", "/usr/share/fonts/truetype/dejavu/", "C:/Windows/Fonts/", "/Library/Fonts/",
                        "/System/Library/Fonts/Supplemental/"):
            try:
                return ImageFont.truetype(thu_muc + f, size)
            except OSError:
                pass
    return ImageFont.load_default()


F, FB, FT = font(26), font(26, True), font(34, True)


class Trang:
    def __init__(self):
        self.img = Image.new("L", (W, H), 250)
        self.d = ImageDraw.Draw(self.img)
        self.y = 110

    def giua(self, s, f=FB, cach=10):
        w = self.d.textlength(s, font=f)
        self.d.text(((W - w) / 2, self.y), s, font=f, fill=20)
        self.y += f.size + cach

    def doan(self, s, f=F, le=120, cach=8):
        tu, dong = s.split(), ""
        for t in tu:
            thu = (dong + " " + t).strip()
            if self.d.textlength(thu, font=f) > W - 2 * le:
                self.d.text((le, self.y), dong, font=f, fill=20)
                self.y += f.size + cach
                dong = t
            else:
                dong = thu
        if dong:
            self.d.text((le, self.y), dong, font=f, fill=20)
            self.y += f.size + cach
        self.y += 6

    def quoc_hieu(self):
        self.giua("CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM")
        self.giua("Độc lập - Tự do - Hạnh phúc", cach=40)

    def dau(self, s, x=780, y=None):
        y = y or self.y
        self.d.ellipse((x, y, x + 260, y + 260), outline=60, width=5)
        self.d.text((x + 30, y + 115), s, font=font(20, True), fill=60)

    def so_trang(self, k):
        self.d.text((W - 140, H - 120), str(k), font=F, fill=20)
        return self

    def scan(self, nghieng=True):
        img = self.img
        if nghieng:
            img = img.rotate(random.uniform(-0.8, 0.8), fillcolor=250, resample=Image.BICUBIC)
        nhieu = Image.effect_noise((W, H), 18)
        img = Image.blend(img, nhieu, 0.08).filter(ImageFilter.GaussianBlur(0.6))
        return img.convert("RGB")


LOREM = ("Các bên cam kết những thông tin đã ghi trong hợp đồng này là đúng sự thật, việc giao kết hợp đồng "
         "hoàn toàn tự nguyện, không bị lừa dối hoặc ép buộc, và thực hiện đúng, đầy đủ các thỏa thuận đã ghi "
         "trong hợp đồng. Mọi tranh chấp phát sinh được giải quyết trên cơ sở thương lượng, hòa giải.")


def hd_dau(tieu_de="HỢP ĐỒNG CHUYỂN NHƯỢNG QUYỀN SỬ DỤNG ĐẤT", dau_luu=False):
    t = Trang()
    if dau_luu:  # dấu "HỒ SƠ LƯU / Số cc / Ngày" đóng bên trái, ngang hàng Quốc hiệu và tên hợp đồng
        for k, s in enumerate(["HỒ SƠ LƯU", "Số cc: 001234", "Ngày: 15/3/2022"]):
            t.d.text((70, t.y + k * (FB.size + 10) + (40 if k == 2 else 0)), s, font=FB, fill=40)
    t.quoc_hieu()
    if dau_luu:
        w = t.d.textlength(tieu_de, font=FT)
        x = max((W - w) / 2, 70 + t.d.textlength("Ngày: 15/3/2022", font=FB) + 80)
        t.d.text((x, t.y), tieu_de, font=FT, fill=20)
        t.y += FT.size + 30
    else:
        t.giua(tieu_de, FT, 30)
    t.doan("Hôm nay, tại Văn phòng công chứng Hòa An, Thành phố Hồ Chí Minh, chúng tôi gồm có:")
    t.doan("BÊN CHUYỂN NHƯỢNG (Bên A): Ông Trần Văn Bình, sinh năm 1970, CCCD số 079070000111.")
    t.doan("BÊN NHẬN CHUYỂN NHƯỢNG (Bên B): Bà Lê Thị Cúc, sinh năm 1985, CCCD số 079185000222.")
    t.doan("Điều 1. Quyền sử dụng đất chuyển nhượng", FB)
    t.doan("Thửa đất số 123, tờ bản đồ số 45, diện tích 100 m2, theo Giấy chứng nhận quyền sử dụng đất số "
           "CS 01234 do Sở Tài nguyên và Môi trường cấp ngày 01/02/2019.")
    t.doan("Điều 2. Giá chuyển nhượng và phương thức thanh toán", FB)
    t.doan("Giá chuyển nhượng là 2.000.000.000 đồng. Bên B thanh toán cho Bên A bằng chuyển khoản.")
    return t


def hd_giua(bat_dau=3):
    t = Trang()
    for k in range(bat_dau, bat_dau + 4):
        t.doan(f"Điều {k}. Quyền và nghĩa vụ của các bên", FB)
        t.doan(LOREM)
    return t


def hd_ky():
    t = Trang(); t.y = 300
    t.d.text((200, t.y), "BÊN A", font=FB, fill=20); t.d.text((820, t.y), "BÊN B", font=FB, fill=20)
    t.y += 40
    t.d.text((140, t.y), "(Ký, ghi rõ họ tên)", font=F, fill=20); t.d.text((760, t.y), "(Ký, ghi rõ họ tên)", font=F, fill=20)
    t.y += 220
    t.d.text((140, t.y), "Trần Văn Bình", font=F, fill=20); t.d.text((780, t.y), "Lê Thị Cúc", font=F, fill=20)
    return t


def loi_chung(tach=False, ngay="ngày 15 tháng 3 năm 2022", so="1234", quyen="02/2022", vp="Hòa An", so_trang=None):
    t = Trang(); t.y = 160
    t.giua("LỜI CHỨNG CỦA CÔNG CHỨNG VIÊN", FT, 30)
    t.doan(f"Hôm nay, {ngay}, tại Văn phòng công chứng {vp}, Thành phố Hồ Chí Minh, "
           "tôi Nguyễn Văn An, công chứng viên, chứng nhận:")
    for _ in range(3 if tach else 1):
        t.doan("- Hợp đồng được giao kết giữa Ông Trần Văn Bình và Bà Lê Thị Cúc; các bên đã tự nguyện thỏa thuận "
               "giao kết hợp đồng; tại thời điểm công chứng các bên có năng lực hành vi dân sự phù hợp theo quy định.")
    if tach:
        t2 = Trang(); t2.y = 140
        t2.doan("- Hợp đồng này được lập thành 03 bản chính, mỗi bản gồm 04 tờ, 05 trang.")
        tt = t2
    else:
        tt = t
    if so_trang:
        tt.doan(f"- Văn bản công chứng này được lập thành 03 (ba) bản chính, mỗi bản chính gồm "
                f"{(so_trang + 1) // 2:02d} tờ, {so_trang:02d} trang, có giá trị pháp lý như nhau.")
    tt.doan(f"Số công chứng {so}, quyển số {quyen} TP/CC-SCC/HĐGD.")
    tt.y += 30
    tt.d.text((820, tt.y), "CÔNG CHỨNG VIÊN", font=FB, fill=20)
    tt.dau("VPCC " + vp.upper(), y=tt.y + 40)
    tt.y += 330
    tt.d.text((830, tt.y), "Nguyễn Văn An", font=FB, fill=20)
    return [t, t2] if tach else [t]


def phieu_yc():
    t = Trang(); t.quoc_hieu(); t.giua("PHIẾU YÊU CẦU CÔNG CHỨNG HỢP ĐỒNG, GIAO DỊCH", FT, 30)
    t.doan("Kính gửi: Văn phòng công chứng Hòa An")
    t.doan("Họ tên người nộp phiếu: Trần Văn Bình. Địa chỉ liên hệ: 12 Nguyễn Trãi, Quận 1.")
    t.doan("Yêu cầu công chứng về: Hợp đồng chuyển nhượng quyền sử dụng đất.")
    t.doan("Các giấy tờ nộp kèm theo phiếu này gồm: Dự thảo hợp đồng; Bản sao giấy tờ tùy thân; Bản sao "
           "Giấy chứng nhận quyền sử dụng đất.")
    return t


def cccd(dau_sao=True):
    t = Trang()
    t.d.rounded_rectangle((200, 200, 1040, 730), 30, outline=40, width=4)
    t.d.text((330, 240), "CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM", font=font(22, True), fill=30)
    t.d.text((300, 275), "SOCIALIST REPUBLIC OF VIET NAM", font=font(20), fill=30)
    t.d.text((420, 330), "CĂN CƯỚC CÔNG DÂN", font=FT, fill=30)
    t.d.text((390, 375), "Citizen Identity Card", font=F, fill=30)
    t.d.rectangle((240, 420, 400, 640), fill=150)
    t.d.text((430, 440), "Số / No.: 079070000111", font=F, fill=30)
    t.d.text((430, 490), "Họ và tên: TRẦN VĂN BÌNH", font=F, fill=30)
    if dau_sao:
        t.y = 1000
        t.doan("CHỨNG THỰC BẢN SAO ĐÚNG VỚI BẢN CHÍNH", FB, le=600)
        t.dau("UBND PHƯỜNG", x=650, y=1080)
    return t


def gcn():
    t = Trang(); t.quoc_hieu()
    t.giua("GIẤY CHỨNG NHẬN", FT); t.giua("QUYỀN SỬ DỤNG ĐẤT, QUYỀN SỞ HỮU NHÀ Ở", FB)
    t.giua("VÀ TÀI SẢN KHÁC GẮN LIỀN VỚI ĐẤT", FB, 40)
    t.doan("I. Người sử dụng đất, chủ sở hữu nhà ở và tài sản khác gắn liền với đất: Ông Trần Văn Bình.")
    t.doan("II. Thửa đất, nhà ở và tài sản khác gắn liền với đất: Thửa đất số 123, tờ bản đồ số 45.")
    return t


def hon_nhan():
    t = Trang(); t.quoc_hieu(); t.giua("GIẤY XÁC NHẬN TÌNH TRẠNG HÔN NHÂN", FT, 30)
    t.doan("Xét đề nghị của ông Trần Văn Bình về việc xác nhận tình trạng hôn nhân, Ủy ban nhân dân phường "
           "Bến Nghé xác nhận: ông Trần Văn Bình hiện chưa đăng ký kết hôn với ai.")
    return t


def so_do():
    t = Trang()
    t.d.polygon([(300, 400), (900, 380), (950, 1100), (280, 1150)], outline=30, width=4)
    t.d.text((560, 750), "123", font=FT, fill=30)
    t.d.text((300, 1250), "Tỷ lệ 1/500", font=F, fill=30)
    return t


def to_bia(tieu_de="HỢP ĐỒNG CHUYỂN NHƯỢNG QUYỀN SỬ DỤNG ĐẤT"):
    """Tờ bìa hồ sơ lưu: Quốc hiệu, HỒ SƠ LƯU, số CC, tên hợp đồng, địa chỉ tài sản, tên văn phòng."""
    t = Trang(); t.quoc_hieu(); t.y += 120
    t.giua("HỒ SƠ LƯU", FT, 30); t.giua("Số cc: 001234", F); t.giua("Ngày: 15/3/2022", F, 200)
    t.giua(tieu_de, FT, 60)
    t.doan("Thửa đất số 123, tờ bản đồ số 45", le=300); t.doan("Phường 22, Quận Bình Thạnh", le=300)
    t.y = 2900
    t.giua("VĂN PHÒNG CÔNG CHỨNG HÒA AN - THÀNH PHỐ HỒ CHÍ MINH", F)
    return t


def trang_trang():
    return Trang()


def ban_sao_hd_cu():
    t = hd_dau("HỢP ĐỒNG MUA BÁN NHÀ Ở"); t.y += 60
    t.doan("SAO Y BẢN CHÍNH", FB, le=700); t.dau("PHÒNG CC SỐ 2", x=700, y=t.y)
    lc = loi_chung()[0]; lc.y = 1450; lc.doan("SAO Y BẢN CHÍNH", FB, le=120)
    return [t, lc]


def ghi(ten, ds, thu_muc):
    anh = [p.scan() for p in ds]
    thu_muc.mkdir(parents=True, exist_ok=True)
    anh[0].save(thu_muc / ten, save_all=True, append_images=anh[1:], resolution=150)


def tao_tat_ca(ra):
    ra = Path(ra)
    ghi("A_hoso_truoc_va_sau.pdf", [phieu_yc(), cccd(), hd_dau(), hd_giua(), hd_ky(), *loi_chung(), gcn(), hon_nhan()], ra)
    ghi("B_trang_trang_loichung_2trang.pdf", [hd_dau(), trang_trang(), hd_giua(), hd_ky(), *loi_chung(tach=True),
                                              cccd(False), so_do()], ra)
    ghi("C_hai_giao_dich.pdf", [hd_dau(), hd_ky(), *loi_chung(), cccd(), hd_dau("HỢP ĐỒNG THẾ CHẤP TÀI SẢN"),
                                hd_ky(), *loi_chung(), gcn()], ra)
    ghi("D_thieu_loi_chung.pdf", [phieu_yc(), hd_dau(), hd_giua(), hd_ky(), gcn()], ra)
    ghi("E_hoso_co_ban_sao_hd_cu.pdf", [phieu_yc(), hd_dau(), hd_ky(), *loi_chung(), gcn(), *ban_sao_hd_cu()], ra)
    ghi("F_mat_trang_tieu_de.pdf", [hd_giua(), hd_giua(7), hd_ky(), *loi_chung(), cccd()], ra)
    # bản sao HĐ cũ KHÔNG có dấu sao y, do văn phòng khác lập năm 2015 -> chỉ phân định được nhờ số CC/ngày/tên tổ chức
    ghi("H_2022_1234_ban_sao_khong_dau.pdf", [phieu_yc(), hd_dau(), hd_giua(), hd_ky(), *loi_chung(), cccd(),
        hd_dau("HỢP ĐỒNG MUA BÁN NHÀ Ở"), hd_ky(),
        *loi_chung(ngay="ngày 02 tháng 8 năm 2015", so="567", quyen="01/2015", vp="Sài Gòn Mới"), gcn()], ra)
    # 2 giao dịch thật trong 1 file + bản sao HĐ cũ của văn phòng khác trong hồ sơ (dùng thử chế độ nhiều văn bản/file)
    ghi("I_1234_1235_hai_gd_kem_ban_sao.pdf", [hd_dau(), hd_ky(), *loi_chung(),
        hd_dau("HỢP ĐỒNG THẾ CHẤP QUYỀN SỬ DỤNG ĐẤT"), hd_ky(), *loi_chung(so="1235"), cccd(),
        hd_dau("HỢP ĐỒNG MUA BÁN NHÀ Ở"), hd_ky(),
        *loi_chung(ngay="ngày 02 tháng 8 năm 2015", so="567", quyen="01/2015", vp="Sài Gòn Mới"), gcn()], ra)
    # --- kiểm tra thiếu/thừa trang: văn bản có in số trang ---
    def danh_so(ds):
        return [t.so_trang(k + 1) for k, t in enumerate(ds)]

    # mất trang 3/5 (lời chứng ghi 5 trang, có số trang in)
    vb = danh_so([hd_dau(), hd_giua(), hd_giua(7), hd_ky(), *loi_chung(so_trang=5)])
    ghi("J_thieu_trang_giua.pdf", [phieu_yc(), vb[0], vb[1], vb[3], vb[4], cccd()], ra)
    # trang 2 bị scan 2 lần (lời chứng ghi 4 trang)
    vb = danh_so([hd_dau(), hd_giua(), hd_ky(), *loi_chung(so_trang=4)])
    ghi("K_trang_scan_trung.pdf", [vb[0], vb[1], vb[1], vb[2], vb[3], gcn()], ra)
    # lời chứng không ghi số trang: chỉ còn số trang in và số Điều để phát hiện mất trang 2
    vb = danh_so([hd_dau(), hd_giua(), hd_giua(7), hd_ky(), *loi_chung()])
    ghi("L_thieu_trang_khong_ghi_so_trang.pdf", [vb[0], vb[2], vb[3], vb[4], cccd()], ra)
    # đủ trang (đối chứng): phải ĐẠT
    vb = danh_so([hd_dau(), hd_giua(), hd_ky(), *loi_chung(so_trang=4)])
    ghi("M_du_trang.pdf", [phieu_yc(), *vb, gcn()], ra)
    # trang tiêu đề bị scan 2 lần (trước đây bị hiểu nhầm thành 2 văn bản)
    vb = danh_so([hd_dau(), hd_giua(), hd_ky(), *loi_chung(so_trang=4)])
    ghi("N_trung_trang_tieu_de.pdf", [phieu_yc(), vb[0], vb[0], vb[1], vb[2], vb[3], gcn()], ra)
    # trang ký (rất ít chữ) bị scan 2 lần: phải so bằng hình ảnh
    vb = danh_so([hd_dau(), hd_giua(), hd_ky(), *loi_chung(so_trang=4)])
    ghi("O_trung_trang_ky.pdf", [vb[0], vb[1], vb[2], vb[2], vb[3], cccd()], ra)
    # lời chứng ghi số trang bằng chữ, bị thiếu 1 trang
    vb = [hd_dau(), hd_giua(), hd_giua(7), hd_ky(), *loi_chung()]
    lc = vb[-1]
    lc.y = 1250
    lc.doan("Văn bản này bao gồm năm trang.")
    ghi("P_thieu_trang_so_bang_chu.pdf", [vb[0], vb[1], vb[3], vb[4]], ra)
    # tờ bìa cùng tên hợp đồng nằm ngay trước trang đầu: lời chứng tính cả bìa (5 trang) -> bìa thuộc văn bản
    ghi("Q_to_bia_tinh_vao_vb.pdf", [phieu_yc(), to_bia(), hd_dau(), hd_giua(), hd_ky(), *loi_chung(so_trang=5),
                                     gcn()], ra)
    # lời chứng không tính bìa (4 trang) -> bìa để ở phần hồ sơ
    ghi("R_to_bia_khong_tinh.pdf", [phieu_yc(), to_bia(), hd_dau(), hd_giua(), hd_ky(), *loi_chung(so_trang=4),
                                    gcn()], ra)
    # dấu "HỒ SƠ LƯU / Số cc / Ngày" đóng sát tên hợp đồng: OCR ghép chung một dòng, vẫn phải nhận là trang tiêu đề
    ghi("S_dau_ho_so_luu_canh_tieu_de.pdf", [hd_dau("HỢP ĐỒNG THẾ CHẤP TÀI SẢN", dau_luu=True), hd_giua(), hd_ky(), *loi_chung(so_trang=4),
                                             gcn()], ra)
    # 1 trang hợp đồng bị scan lạc ra sau hồ sơ: lời chứng ghi 4 trang, tách được 3 -> chỉ ra trang lạc chỗ
    ghi("T_trang_scan_lac_cho.pdf", [hd_dau(), hd_ky(), *loi_chung(so_trang=4), phieu_yc(), gcn(), hd_giua()], ra)
    # hồ sơ có trang hợp đồng khác (nhiều 'Điều…'), văn bản đủ trang theo lời chứng -> chỉ ghi chú, vẫn Đạt
    ghi("V_hd_khac_trong_ho_so.pdf", [hd_dau(), hd_ky(), *loi_chung(so_trang=3), phieu_yc(), gcn(), hd_giua()], ra)
    print(f"Đã tạo 20 file thử trong {ra}/")


if __name__ == "__main__":
    tao_tat_ca(sys.argv[1] if len(sys.argv) > 1 else "du_lieu_thu")
