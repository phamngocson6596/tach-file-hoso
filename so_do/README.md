# so_do — đọc giấy chứng nhận (sổ đỏ / sổ hồng) thành dữ liệu — BẢN THỬ

Đọc file scan/ảnh giấy chứng nhận, tách thành dữ liệu có cấu trúc, ghi vào kho trên máy để tra cứu chéo.
Không gửi dữ liệu ra ngoài.

## Chạy thử

Từ thư mục gốc repo (cần các thư viện trong `requirements.txt`; mã vạch cần thêm `pip install zxing-cpp`):

```
python -m so_do doc "D:\Ho so\so_do.pdf"                      # mặc định dùng Screen AI
python -m so_do doc "D:\Ho so\so_do.pdf" --engine tesseract
python -m so_do tim --nguoi 079080000111                       # hoặc tên không dấu: --nguoi "nguyen van an"
python -m so_do tim --thua 15 --to 42
python -m so_do nhan-moi                                       # nhãn chưa có trong từ điển
python -m so_do lap-chi-muc "D:\Ho so"                         # dựng lại kho từ các file .gcn.json
```

Mỗi file đọc xong sinh ra hai file đặt cạnh nó:

- `<tên>.gcn.json` — **bản gốc của dữ liệu** (cấu trúc: `schema_gcn.json`).
- `<tên>.gcn.html` — trang duyệt: ảnh từng trang bên trái, các trường bên phải. Ô vàng là cần xác nhận;
  rê chuột lên ô để xem nguyên văn và trang, dòng nguồn.

Kho SQLite mặc định ở `%LOCALAPPDATA%\eNotary\kho_so_do.sqlite` (đổi bằng `--kho`). Kho chỉ là chỉ mục:
xoá đi thì dựng lại được từ các file `.gcn.json`.

## Cấu trúc hai lớp

| Lớp | Là gì | Ví dụ |
|---|---|---|
| `nguyen_van` | Khung giấy đúng như in: mục → dòng "nhãn: giá trị" / bảng / đoạn chữ. **Không cần biết trước tên trường**: sổ có thêm mục hay nhãn lạ vẫn giữ đủ. | `{"nhan": "Thửa đất số", "gia_tri": "15"}` |
| `chuan_hoa` | Trường app dùng, sinh từ lớp 1 theo **từ điển nhãn** `tu_dien_nhan.json`. Mọi thứ có thể nhiều là danh sách: `chu[]`, `thua[]`, `muc_dich[]`, `cong_trinh[]`. | `thua[0].so_thua = {gia_tri: "15", nguyen_van, nguon, trang_thai}` |

- Mỗi giá trị có `trang_thai`: `doc_duoc`, `can_xac_nhan` (viết tay, đoán từ bảng, kiểm tra không khớp), `da_xac_nhan`.
- Gặp nhãn chưa có trong từ điển: giữ ở `chua_phan_loai`, đếm trong kho (`nhan-moi`). Bổ sung một dòng vào
  `tu_dien_nhan.json` là lần sau nhận ra, **không phải sửa code**.

## Kiểm tra tự động

Diện tích bằng số ↔ bằng chữ · tổng diện tích các mục đích ↔ diện tích thửa · độ dài số CCCD/CMND · năm sinh ·
số thửa/tờ bản đồ bất thường · ngày cấp đọc không ra ngày hợp lệ · mã vạch ↔ số in dưới mã vạch ·
**trang biến động có nội dung** (chủ hiện tại / thế chấp có thể đã khác trang 1).

Tra chéo trong kho khi lưu: **khách quen** (cùng số giấy tờ đã có trong giấy khác), **tài sản đã có**
(cùng số thửa + tờ bản đồ + phường/quận).

## Giới hạn của bản thử

- Thử trên **một** giấy chứng nhận thật (mẫu 2009–2023, chụp CamScanner) và bộ dữ liệu giả trong `tests/`.
  Cần thêm mẫu: sổ đỏ cũ, sổ hồng, mẫu 2024 có mã QR, sổ có trang biến động, ảnh chụp điện thoại.
- **Bảng** (công trình, nhiều thửa) đang được *đoán* vì Screen AI chưa trả toạ độ chữ: mọi ô đánh dấu
  `can_xac_nhan`. Sẽ thay bằng bộ dựng bảng theo toạ độ.
- **Chữ viết tay** (ngày cấp, số vào sổ): engine nào cũng có thể đọc sai mà trông vẫn hợp lệ, nên luôn
  `can_xac_nhan`.
- Kho chưa mã hoá.

Chạy test: `python -m unittest discover tests`
