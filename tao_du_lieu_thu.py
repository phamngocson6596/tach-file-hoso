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


def hd_dau(tieu_de="HỢP ĐỒNG CHUYỂN NHƯỢNG QUYỀN SỬ DỤNG ĐẤT"):
    t = Trang(); t.quoc_hieu(); t.giua(tieu_de, FT, 30)
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


def loi_chung(tach=False, ngay="ngày 15 tháng 3 năm 2022", so="1234", quyen="02/2022", vp="Hòa An"):
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
    print(f"Đã tạo 8 file thử trong {ra}/")


if __name__ == "__main__":
    tao_tat_ca(sys.argv[1] if len(sys.argv) > 1 else "du_lieu_thu")
