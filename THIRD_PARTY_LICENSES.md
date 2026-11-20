# Thành phần bên thứ ba

Mã nguồn của dự án phát hành theo giấy phép **GNU AGPL-3.0** (xem file `LICENSE`). Bản đóng gói cho Windows (`TachVanBan-CaiDat.exe` và `TachVanBan-KhongCanCai.zip`) có kèm các thành phần bên thứ ba dưới đây. Mỗi thành phần giữ nguyên giấy phép của nó.

| Thành phần | Dùng để | Giấy phép | Nguồn |
|---|---|---|---|
| Python | chạy chương trình | Python Software Foundation License | python.org |
| Tcl/Tk (tkinter) | giao diện | giấy phép Tcl/Tk (kiểu BSD) | tcl.tk |
| PyMuPDF / MuPDF | đọc, dựng ảnh và cắt trang PDF | GNU AGPL-3.0 (hoặc giấy phép thương mại của Artifex) | github.com/pymupdf/PyMuPDF |
| Pillow | xử lý ảnh | MIT-CMU | github.com/python-pillow/Pillow |
| pytesseract | gọi Tesseract từ Python | Apache-2.0 | github.com/madmaze/pytesseract |
| openpyxl | ghi và đọc bảng Excel | MIT | foss.heptapod.net/openpyxl/openpyxl |
| Tesseract OCR (bản dựng cho Windows của UB Mannheim) | nhận dạng chữ | Apache-2.0. Các thư viện đi kèm (Leptonica…) có giấy phép riêng. Bản đóng gói chỉ giữ các thư viện mà `tesseract.exe` cần; danh sách và giấy phép từng thư viện xem trên trang UB Mannheim | github.com/tesseract-ocr/tesseract, github.com/UB-Mannheim/tesseract |
| Mô hình ngôn ngữ `vie` (tessdata) | mô hình nhận dạng tiếng Việt | Apache-2.0 | github.com/tesseract-ocr/tessdata |
| Inno Setup | tạo bộ cài `TachVanBan-CaiDat.exe` | Inno Setup License (cho phép phân phối bộ cài tạo ra) | jrsoftware.org |
| PyInstaller (bootloader) | đóng gói thành `.exe` | GPL-2.0-or-later, có ngoại lệ cho bootloader (được phép phân phối chương trình đã đóng gói) | pyinstaller.org |

**Không đóng gói kèm:** thư viện Screen AI của Google Chrome và wrapper `locro`. Tuỳ chọn "Screen AI của Chrome" chỉ dùng được khi chạy từ mã nguồn, và người dùng phải tự cài các thành phần này.
