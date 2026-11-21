"""Test bộ đọc giấy chứng nhận bằng DỮ LIỆU GIẢ (không dùng giấy tờ thật trong repo).

Chạy: python -m unittest discover tests
"""
import sqlite3
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

from so_do import doc_giay
from so_do import kho as kho_mod
from so_do.doc_khung import tach_truong
from so_do.doc_so import chu_thanh_so, so_viet

# Dạng chữ Screen AI trả về cho một giấy chứng nhận mẫu 2009-2023 (tên, số giả).
TRANG_1 = """CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM
Độc lập - Tự do - Hạnh phúc
GIẤY CHỨNG NHẬN
QUYỀN SỬ DỤNG ĐẤT
I. Người sử dụng đất, chủ sở hữu nhà ở và tài sản khác gắn liền với đất
Ông: NGUYỄN VĂN AN
Năm sinh: 1980, CCCD số: 079 080 000 111
Địa chỉ thường trú: số 1 đường Số 2, phường Bến Nghé, quận 1, Tp.Hồ Chí
Minh
Bà: LÊ THỊ BÌNH
Năm sinh: 1982, CCCD số: 079 182 000 222
Địa chỉ thường trú: số 1 đường Số 2, phường Bến Nghé, quận 1, Tp.Hồ Chí Minh
AB 123456
Được quét bằng CamScanner"""

TRANG_2 = """II. Thửa đất, nhà ở và tài sản khác gắn liền với đất
1. Thửa đất:
a) Thửa đất số: 15
, tờ bản đồ số: 42,
b) Địa chỉ: phường Thảo Điền, thành phố Thủ Đức, Thành phố Hồ Chí Minh,
c) Diện tích: 120,5m², (bằng chữ: Một trăm hai mươi phẩy năm mét vuông),
d) Hình thức sử dụng: Sử dụng riêng,
đ) Mục đích sử dụng: Đất ở tại đô thị,
e) Thời hạn sử dụng: Lâu dài,
g) Nguồn gốc sử dụng: Công nhận quyền sử dụng đất như giao đất có thu tiền sử dụng đất.
2. Nhà ở: -/-
3. Công trình xây dựng khác: -/-
4. Rừng sản xuất là rừng trồng: -/-
5. Cây lâu năm: -/-
6. Ghi chú:
- Giấy chứng nhận này được cấp theo biên nhận số 000123.
Số vào sổ cấp GCN: CS 01234
Thành phố Hồ Chí Minh, ngày 15 tháng 03 năm 2022
SỞ TÀI NGUYÊN VÀ MÔI TRƯỜNG
KT. GIÁM ĐỐC
PHÓ GIÁM ĐỐC
Trần Văn Cường"""

TRANG_4_TRONG = """Nội dung thay đổi và cơ sở pháp lý
Xác nhận của cơ quan
có thẩm quyền
Người được cấp Giấy chứng nhận không được sửa chữa, tẩy xóa hoặc bổ
sung bất kỳ nội dung nào trong Giấy chứng nhận; khi bị mất hoặc hư
hỏng Giấy chứng nhận phải khai báo ngay với cơ quan cấp Giấy.
1234567890123"""

CONG_TRINH_BANG = """3. Công trình xây dựng khác:
Loại công trình: Tòa nhà A1 - Dự án khu dân cư mẫu
Hạng mục công trình
Diện tích
xây dựng
(m²)
Diện tích sàn
(m²) hoặc
công suất
Hình
thức sở
hữu
Cấp
công
trình
Thời
hạn sở
hữu
-/-
75,4
Sở hữu
riêng
Cấp 1
-/-
Căn hộ 12.03, Tầng 12"""


class DocSo(unittest.TestCase):
    def test_chu_thanh_so(self):
        self.assertEqual(chu_thanh_so("Hai mươi bảy nghìn ba trăm bốn mươi mốt mét vuông"), 27341)
        self.assertEqual(chu_thanh_so("Một trăm hai mươi phẩy năm mét vuông"), Decimal("120.5"))
        self.assertEqual(chu_thanh_so("hai mươi mốt"), 21)
        self.assertEqual(chu_thanh_so("một trăm lẻ năm"), 105)
        self.assertEqual(chu_thanh_so("một trăm linh tư"), 104)
        self.assertEqual(chu_thanh_so("một nghìn tỷ"), 10 ** 12)
        self.assertEqual(chu_thanh_so("Mười lăm phẩy không năm"), Decimal("15.05"))

    def test_chu_thanh_so_chiu_loi_ocr(self):
        self.assertEqual(chu_thanh_so("Hai mươi bảy nghìn ba trắm bốn mươi mốt"), 27341)

    def test_chu_khong_phai_so(self):
        self.assertIsNone(chu_thanh_so("đất ở tại đô thị"))
        self.assertIsNone(chu_thanh_so(""))

    def test_so_viet(self):
        self.assertEqual(so_viet("27341,5m²"), Decimal("27341.5"))
        self.assertEqual(so_viet("27.341,5 m2"), Decimal("27341.5"))


class TachTruong(unittest.TestCase):
    def test_hai_truong_mot_dong(self):
        self.assertEqual(tach_truong("Thửa đất số: 15 , tờ bản đồ số: 42,"),
                         [dict(nhan="Thửa đất số", gia_tri="15"), dict(nhan="tờ bản đồ số", gia_tri="42")])

    def test_dia_chi_nhieu_dau_phay_khong_bi_tach(self):
        kq = tach_truong("Địa chỉ: 512 đường X, Khu phố Y, phường Z, thành phố Thủ Đức,")
        self.assertEqual(len(kq), 1)
        self.assertEqual(kq[0]["gia_tri"], "512 đường X, Khu phố Y, phường Z, thành phố Thủ Đức")

    def test_trong_ngoac_khong_bi_tach(self):
        kq = tach_truong("Diện tích: 120,5m², (bằng chữ: Một trăm hai mươi phẩy năm mét vuông),")
        self.assertEqual(len(kq), 1)
        self.assertIn("bằng chữ", kq[0]["gia_tri"])


class DocGiay(unittest.TestCase):
    def setUp(self):
        self.kq = doc_giay([TRANG_1, TRANG_2, "", TRANG_4_TRONG], ma_vach=["1234567890123"],
                           thong_tin_tep=dict(ten="gia.pdf", sha256="a" * 64))
        self.ch = self.kq["chuan_hoa"]

    def test_chu(self):
        self.assertEqual([c["ho_ten"]["gia_tri"] for c in self.ch["chu"]], ["NGUYỄN VĂN AN", "LÊ THỊ BÌNH"])
        self.assertEqual([c["vai"] for c in self.ch["chu"]], ["Ông", "Bà"])
        self.assertEqual(self.ch["chu"][0]["giay_to"]["gia_tri"], dict(loai="CCCD", so="079080000111"))
        self.assertEqual(self.ch["chu"][0]["nam_sinh"]["gia_tri"], 1980)
        self.assertTrue(self.ch["chu"][0]["dia_chi"]["gia_tri"].endswith("Tp.Hồ Chí Minh"))  # nối dòng bị ngắt

    def test_thua(self):
        t = self.ch["thua"][0]
        self.assertEqual(t["so_thua"]["gia_tri"], "15")
        self.assertEqual(t["to_ban_do"]["gia_tri"], "42")
        self.assertEqual(t["dien_tich"]["gia_tri"], 120.5)
        self.assertEqual(t["dien_tich"]["so_tu_chu"], 120.5)
        self.assertEqual(t["muc_dich"][0]["loai"]["gia_tri"], "Đất ở tại đô thị")
        self.assertEqual(t["thoi_han"]["gia_tri"], "Lâu dài")

    def test_thong_tin_giay(self):
        g = self.ch["giay"]
        self.assertEqual(g["so_phat_hanh"]["gia_tri"], "AB 123456")
        self.assertEqual(g["so_vao_so"]["gia_tri"], "CS 01234")
        self.assertEqual(g["so_vao_so"]["trang_thai"], "can_xac_nhan")  # thường viết tay
        self.assertEqual(g["ngay_cap"]["gia_tri"], "2022-03-15")
        self.assertEqual(g["ngay_cap"]["trang_thai"], "can_xac_nhan")
        self.assertEqual(g["co_quan_cap"]["gia_tri"], "SỞ TÀI NGUYÊN VÀ MÔI TRƯỜNG")
        self.assertEqual(g["nguoi_ky"]["gia_tri"], "Trần Văn Cường")
        self.assertEqual(g["so_bien_nhan"]["gia_tri"], "000123")
        self.assertEqual(g["ma_vach"]["gia_tri"], g["so_ma_vach_in"]["gia_tri"])

    def test_o_trong_va_bien_dong_trong(self):
        self.assertEqual(self.ch["nha_o"], [])
        self.assertEqual(self.ch["cong_trinh"], [])
        self.assertNotIn("rung", self.ch)
        self.assertFalse(self.ch["bien_dong"]["co_noi_dung"])

    def test_khong_co_loi(self):
        self.assertEqual(self.kq["kiem_tra"], [])
        self.assertEqual(self.kq["chua_phan_loai"], [])

    def test_giu_nguyen_van(self):
        thua = next(m for m in self.kq["nguyen_van"] if m["tieu_de"] == "Thửa đất")
        nhan = [t["nhan"] for p in thua["noi_dung"] if p["kieu"] == "ban_ghi" for t in p["truong"]]
        self.assertEqual(nhan[:3], ["Thửa đất số", "tờ bản đồ số", "Địa chỉ"])


class NgoaiLe(unittest.TestCase):
    def _doc(self, trang_2, trang_1=TRANG_1, trang_4=TRANG_4_TRONG):
        return doc_giay([trang_1, trang_2, "", trang_4])

    def test_lech_dien_tich_so_va_chu(self):
        kq = self._doc(TRANG_2.replace("Một trăm hai mươi phẩy năm", "Một trăm hai mươi mốt phẩy năm"))
        self.assertIn("dien_tich_lech", [k["ma"] for k in kq["kiem_tra"]])
        self.assertEqual(kq["chuan_hoa"]["thua"][0]["dien_tich"]["trang_thai"], "can_xac_nhan")

    def test_nhieu_muc_dich_co_dien_tich(self):
        t2 = TRANG_2.replace("Mục đích sử dụng: Đất ở tại đô thị,",
                             "Mục đích sử dụng: Đất ở tại đô thị: 100m²; Đất trồng cây lâu năm: 20,5m²,")
        md = self._doc(t2)["chuan_hoa"]["thua"][0]["muc_dich"]
        self.assertEqual([(m["loai"]["gia_tri"], m["dien_tich"]["gia_tri"]) for m in md],
                         [("Đất ở tại đô thị", 100.0), ("Đất trồng cây lâu năm", 20.5)])

    def test_tong_muc_dich_lech(self):
        t2 = TRANG_2.replace("Mục đích sử dụng: Đất ở tại đô thị,",
                             "Mục đích sử dụng: Đất ở tại đô thị: 100m²; Đất trồng cây lâu năm: 50m²,")
        self.assertIn("tong_muc_dich_lech", [k["ma"] for k in self._doc(t2)["kiem_tra"]])

    def test_co_bien_dong(self):
        t4 = TRANG_4_TRONG.replace("Xác nhận của cơ quan",
                                   "Chuyển nhượng cho bà Phạm Thị Dung theo hồ sơ số 999\nXác nhận của cơ quan")
        kq = self._doc(TRANG_2, trang_4=t4)
        self.assertTrue(kq["chuan_hoa"]["bien_dong"]["co_noi_dung"])
        self.assertIn("co_bien_dong", [k["ma"] for k in kq["kiem_tra"]])

    def test_mat_so_thu_tu_muc(self):  # OCR làm mất "I." trước tiêu đề mục người sử dụng đất
        kq = self._doc(TRANG_2, trang_1=TRANG_1.replace("I. Người sử dụng", "Người sử dụng"))
        self.assertEqual(len(kq["chuan_hoa"]["chu"]), 2)

    def test_nhan_la_duoc_giu_lai(self):
        kq = self._doc(TRANG_2.replace("e) Thời hạn", "e) Số hiệu lô: L12,\ne) Thời hạn"))
        self.assertIn(("Số hiệu lô", "L12"), [(c["nhan"], c["gia_tri"]) for c in kq["chua_phan_loai"]])

    def test_ngay_cap_viet_tay_doc_hong(self):
        kq = self._doc(TRANG_2.replace("ngày 15 tháng 03 năm 2022", "ngày 3. tháng 01 năm 20L4"))
        self.assertIn("ngay_cap_hong", [k["ma"] for k in kq["kiem_tra"]])

    def test_bang_cong_trinh_chua_co_toa_do(self):
        t2 = TRANG_2.replace("3. Công trình xây dựng khác: -/-", CONG_TRINH_BANG)
        kq = self._doc(t2)
        ct = kq["chuan_hoa"]["cong_trinh"][0]
        self.assertEqual(ct["hang_muc"]["gia_tri"], "Căn hộ 12.03, Tầng 12")
        self.assertEqual(ct["dien_tich_san"]["gia_tri"], "75,4")
        self.assertEqual(ct["hinh_thuc_so_huu"]["gia_tri"], "Sở hữu riêng")
        self.assertEqual(ct["cap"]["gia_tri"], "Cấp 1")
        self.assertIsNone(ct["dien_tich_xay_dung"]["gia_tri"])
        self.assertEqual(ct["dien_tich_san"]["trang_thai"], "can_xac_nhan")
        self.assertEqual(ct["loai_cong_trinh"]["gia_tri"], "Tòa nhà A1 - Dự án khu dân cư mẫu")

    def test_nhan_bi_ocr_sai_nhe(self):
        kq = self._doc(TRANG_2.replace("Số vào sổ cấp GCN", "Số vio số cấp GON").replace("b) Địa chỉ", "b) Địa chì"))
        self.assertEqual(kq["chuan_hoa"]["giay"]["so_vao_so"]["gia_tri"], "CS 01234")
        self.assertIn("dia_chi", kq["chuan_hoa"]["thua"][0])


class Kho(unittest.TestCase):
    def setUp(self):
        self.tm = tempfile.TemporaryDirectory()
        self.kho = kho_mod.mo(Path(self.tm.name) / "kho.sqlite")

    def tearDown(self):
        self.kho.close()
        self.tm.cleanup()

    def _giay(self, sha, trang_1=TRANG_1, trang_2=TRANG_2):
        return doc_giay([trang_1, trang_2, "", TRANG_4_TRONG], thong_tin_tep=dict(ten=f"{sha}.pdf", sha256=sha))

    def test_luu_lai_cung_file_khong_nhan_ban(self):
        self.assertEqual(kho_mod.luu(self.kho, self._giay("a" * 64)), [])
        self.assertEqual(kho_mod.luu(self.kho, self._giay("a" * 64)), [])
        self.assertEqual(self.kho.execute("SELECT count(*) FROM giay_to").fetchone()[0], 1)
        self.assertEqual(self.kho.execute("SELECT count(*) FROM nguoi").fetchone()[0], 2)

    def test_khach_quen_va_tai_san_da_co(self):
        kho_mod.luu(self.kho, self._giay("a" * 64))
        luu_y = kho_mod.luu(self.kho, self._giay("b" * 64, trang_1=TRANG_1.replace("AB 123456", "AB 999999")))
        self.assertTrue(any(x.startswith("Khách quen: NGUYỄN VĂN AN") for x in luu_y))
        self.assertTrue(any(x.startswith("Tài sản đã có trong kho: thửa 15 tờ 42") for x in luu_y))

    def test_cung_so_thua_khac_phuong_la_hai_thua(self):
        kho_mod.luu(self.kho, self._giay("a" * 64))
        khac = TRANG_2.replace("phường Thảo Điền", "phường An Phú")
        luu_y = kho_mod.luu(self.kho, self._giay("b" * 64, trang_2=khac))
        self.assertFalse(any(x.startswith("Tài sản") for x in luu_y))
        self.assertEqual(len(kho_mod.tim_thua(self.kho, "15", "42")), 2)

    def test_tim_nguoi(self):
        kho_mod.luu(self.kho, self._giay("a" * 64))
        self.assertEqual(kho_mod.tim_nguoi(self.kho, "079 080 000 111")[0]["ho_ten"], "NGUYỄN VĂN AN")
        self.assertEqual(kho_mod.tim_nguoi(self.kho, "le thi binh")[0]["nam_sinh"], 1982)

    def test_dem_nhan_moi(self):
        kq = doc_giay([TRANG_1, TRANG_2.replace("e) Thời hạn", "e) Số hiệu lô: L12,\ne) Thời hạn")],
                      thong_tin_tep=dict(ten="x.pdf", sha256="c" * 64))
        kho_mod.luu(self.kho, kq)
        self.assertEqual(kho_mod.nhan_moi(self.kho)[0]["nhan"], "Số hiệu lô")

    def test_lap_chi_muc(self):
        import json
        f = Path(self.tm.name) / "ho_so" / "gia.gcn.json"
        f.parent.mkdir()
        f.write_text(json.dumps(self._giay("d" * 64), ensure_ascii=False), encoding="utf-8")
        kho2 = kho_mod.mo(Path(self.tm.name) / "kho2.sqlite")
        self.assertEqual(kho_mod.lap_chi_muc(kho2, Path(self.tm.name) / "ho_so"), 1)
        self.assertEqual(len(kho_mod.tim_nguoi(kho2, "LÊ THỊ BÌNH")), 1)
        kho2.close()


if __name__ == "__main__":
    unittest.main()
