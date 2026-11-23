# Tách văn bản công chứng khỏi hồ sơ lưu (PDF scan gộp)

Công cụ dành cho các tổ chức hành nghề công chứng có bản scan cũ trong đó **văn bản công chứng và hồ sơ lưu bị scan chung một file**. Mục đích là lấy riêng văn bản công chứng ra để đưa lên Cơ sở dữ liệu công chứng.

- Công cụ tự nhận ra trang nào thuộc văn bản (từ trang tiêu đề đến hết lời chứng) và trang nào thuộc hồ sơ (phiếu yêu cầu, CCCD, giấy chứng nhận, bản sao…), rồi cắt văn bản ra thành file PDF riêng. Chất lượng ảnh giữ nguyên như bản scan.
- Hồ sơ có kèm **bản sao văn bản công chứng cũ**: công cụ loại bản sao ra dựa vào số công chứng, ngày công chứng, tên tổ chức hoặc vị trí trong file. Cách này dùng được cả khi mỗi file có một văn bản lẫn khi mỗi file có nhiều văn bản.
- Những file chưa chắc chắn được đưa vào nhóm **cần kiểm tra**. Bạn xem lại bằng ảnh thu nhỏ, sửa trong Excel, rồi cắt bản chốt.
- **Chạy hoàn toàn trên máy**, không gửi dữ liệu ra ngoài.

---

## 1. Cài đặt (làm một lần)

### Cách 1 — Bản đóng gói cho Windows (khuyên dùng)

**Yêu cầu: Windows 10 hoặc 11, bản 64-bit.** Windows 7 và 8.1 không chạy được.

Vào trang **Releases** của dự án trên GitHub và tải một trong hai file. Cả hai đều đã kèm sẵn Python, Tesseract và gói tiếng Việt.

- **`TachVanBan-CaiDat.exe`** (khuyên dùng, file nhỏ nhất): chạy file, bấm Next. Mặc định cài cho riêng người dùng hiện tại nên **không cần quyền quản trị**. Sau khi cài có biểu tượng ở menu Start, gỡ được trong *Settings → Apps*.
- **`TachVanBan-KhongCanCai.zip`** (dùng khi máy không cho cài phần mềm): giải nén ra một thư mục, ví dụ `D:\TachVanBan`, rồi chạy **`TachVanBan.exe`**.

Nếu Windows báo *"Windows protected your PC"*, bấm **More info**, rồi **Run anyway**. Cảnh báo này hiện ra vì file chưa được ký số.

Với cách này, bạn bỏ qua phần còn lại của mục 1 và chuyển sang mục 2.

### Cách 2 — Chạy từ mã nguồn

**Bước 1. Cài Python (bản 3.9 trở lên, khuyên dùng 3.13 hoặc 3.14)**

- Vào python.org/downloads/windows và chọn **"Windows installer (64-bit)"** (file `.exe`).
- Khi cài, **tick ô "Add python.exe to PATH"**.
- Không cần dùng file MSIX hay "Python Install Manager".

**Bước 2. Cài Tesseract OCR có gói tiếng Việt**

| Hệ điều hành | Cách cài |
|---|---|
| Windows | Tải bộ cài *Tesseract at UB Mannheim* (github.com/UB-Mannheim/tesseract/wiki). Ở màn hình *Choose Components*, mở **Additional language data** và tick **Vietnamese**. Giữ thư mục cài mặc định. |
| macOS | `brew install tesseract tesseract-lang` |
| Ubuntu/Debian | `sudo apt install tesseract-ocr tesseract-ocr-vie` |

Nếu lỡ quên tick Vietnamese thì không cần cài lại. Mở giao diện và bấm **Tải gói tiếng Việt**: công cụ tự tải mô hình tiếng Việt (`vie.traineddata`, khoảng 0,5 MB) về thư mục riêng của bạn, không cần quyền quản trị. Nếu mạng cơ quan chặn việc tải tự động:
- bấm **Tải thủ công…**, tải `vie.traineddata` bằng trình duyệt;
- chép file vào `%LOCALAPPDATA%\TachVanBan\tessdata\`.

**Bước 3. Cài thư viện cho công cụ**

- **Windows:** bấm đúp **`cai_dat.bat`**.
- **macOS/Linux:** chạy `pip install -r requirements.txt`.

---

### Cập nhật lên bản mới

- **Bộ cài:** khi có bản mới, phần mềm hiện dòng màu xanh *"Đã có bản mới …"* ở đầu cửa sổ. Bấm **⬆ Cập nhật ngay**, phần mềm sẽ:
  1. tải bộ cài mới (khoảng 45 MB) và kiểm tra mã băm SHA-256 với GitHub;
  2. tự đóng lại, cài bản mới ở chế độ im lặng vào đúng thư mục cũ;
  3. tự mở lại.

  Nếu lúc đầu cài "cho mọi người dùng", Windows sẽ hỏi quyền quản trị. Có từ bản 0.3.5; bản cũ hơn thì tải bộ cài và chạy bằng tay một lần.
- **Bản zip:** xoá thư mục cũ, giải nén bản mới vào cùng chỗ.
- Cấu hình, gói tiếng Việt đã tải và thư mục kết quả đều được giữ nguyên.
- Có thể bấm **Kiểm tra bản mới** ở góc phải trên bất cứ lúc nào.
- Muốn phần mềm hoàn toàn không kết nối mạng: bỏ tick **Tự kiểm tra bản mới khi mở phần mềm** ở mục 4.

## 2. Dùng giao diện

Mở giao diện theo một trong các cách sau:

- **Bản cài hoặc bản zip:** mở *Tách văn bản công chứng* từ menu Start, hoặc chạy `TachVanBan.exe`.
- **Mã nguồn trên Windows:** bấm đúp `chay_giao_dien.bat`.
- **macOS/Linux:** chạy `python3 giao_dien.py`.

1. **Thư mục:** chọn thư mục chứa PDF scan (công cụ quét cả các thư mục con), rồi chọn thư mục ghi kết quả.
2. **Cấu trúc hồ sơ của đơn vị:** khai báo theo cách đơn vị đã scan (xem bảng bên dưới). Rê chuột lên từng ô để xem giải thích.
3. **Đọc chữ (OCR):** bấm **Kiểm tra**. Phải hiện ✔ *Tesseract … có gói tiếng Việt* mới chạy được.
   - Báo chưa có Tesseract: bấm **Tải Tesseract…** để mở trang tải bộ cài.
   - Báo thiếu gói tiếng Việt: bấm **Tải gói tiếng Việt**.
4. **Đầu ra:** lần đầu nên đặt **Chỉ chạy thử 50 file** và tick **Ảnh thu nhỏ cho cả file đạt**.
5. Bấm **▶ Bắt đầu tách**. Chạy xong thì bấm **Mở trang xem lại**.
6. **Sau khi soát lại:**
   - bấm **Mở bảng Excel**, sửa cột `trang_van_ban` cho các file sai, lưu lại và **đóng Excel**;
   - bấm **Cắt bản chốt theo bảng Excel**.

   Thư mục **`chot/`** là bộ file cuối cùng để tải lên.

Cấu hình được lưu tự động cho lần mở sau. Chạy lại cùng thư mục kết quả sẽ không phải OCR lại, nên thử đổi tuỳ chọn gần như tức thì.

**Song song, Dừng và file bị treo**

- **Song song** là số file đọc cùng lúc. Đặt cao quá thì các file tranh CPU và RAM, mỗi file chậm đi rất nhiều. Máy văn phòng nên để **3–4**. Lỗi "tiến trình dừng bất thường / thiếu bộ nhớ" thì giảm số này.
- Bấm **■ Dừng** là dừng ngay: các file đang đọc dở bị bỏ, báo cáo vẫn được ghi cho các file đã xong. Chạy lại cùng thư mục kết quả thì các file đã xong không phải OCR lại.
- Một file chạy quá **15 phút + 3 phút/trang** thì bị coi là treo: công cụ bỏ qua, ghi `LOI` kèm lý do rồi chạy tiếp. Thường do file hỏng, file quá nặng, hoặc ổ mạng bị ngắt giữa chừng. Lý do lỗi của từng file hiện ngay trong nhật ký và ở cột `canh_bao`.

### Ý nghĩa các tuỳ chọn "Cấu trúc hồ sơ"

**Mỗi file scan chứa:**

| Lựa chọn | Khi nào dùng |
|---|---|
| **Một văn bản công chứng** (mặc định) | Mỗi file tương ứng với một số công chứng. Nếu file có nhiều văn bản, công cụ chấm điểm và chọn **1 văn bản chính**. Các văn bản còn lại được coi là hồ sơ. |
| **Có thể nhiều văn bản công chứng** | Đơn vị scan nhiều giao dịch vào chung một file. Mỗi văn bản được cắt thành file riêng (`…__vb1.pdf`, `…__vb2.pdf`). Văn bản nào có dấu hiệu là **bản sao lưu trong hồ sơ** thì bị loại. |

**Dấu hiệu nhận ra văn bản của đơn vị.** Các dấu hiệu này dùng cho **cả hai chế độ** trên.

| Dấu hiệu | Văn bản của đơn vị | Bản sao trong hồ sơ |
|---|---|---|
| **Số công chứng có trong tên file/thư mục** (ví dụ `2022/1234.pdf`, `1234_1235.pdf`) | số trong lời chứng khớp với tên file: **+6** | đọc được số nhưng không khớp: **−6** |
| **Tên tổ chức** — **ghi ngắn**, chỉ tên văn phòng (ví dụ *Văn phòng công chứng Hòa An*), không ghi địa chỉ hay tỉnh/thành | lời chứng ghi đúng tên (chịu được OCR sai vài chữ): **+3** | lời chứng ghi rõ tên văn phòng hoặc phòng công chứng khác hẳn: **−3**. Không đọc được tên tổ chức nào thì không cộng không trừ |
| **Ngày công chứng mới nhất** (mặc định bật) | cùng ngày hoặc gần ngày (không quá 30 ngày) với văn bản mới nhất trong file: **+2** | cũ hơn quá 30 ngày: **−2** |
| **Văn bản nằm ở: Đầu / Cuối file** | xem giải thích dưới bảng | xem giải thích dưới bảng |

Ý nghĩa của tuỳ chọn **vị trí**:

- **Chế độ một văn bản:** văn bản đầu tiên (hoặc cuối cùng) được +2.
- **Chế độ nhiều văn bản:** chỉ giữ các văn bản **xếp liền nhau** ở đầu (hoặc cuối) file, được +2. Văn bản nằm sau một trang hồ sơ bị −2.
- Nếu đơn vị xếp xen kẽ (VB1, hồ sơ 1, VB2, hồ sơ 2) thì chọn **Không cố định**.

Cách quyết định:

- **Một văn bản/file:** luôn xuất **đúng 1 văn bản**. Văn bản có đủ tiêu đề và lời chứng được ưu tiên tuyệt đối; văn bản thiếu lời chứng (tờ bìa, bản sao lẻ trong hồ sơ) chỉ được chọn khi không còn văn bản nào đủ. Trong số các văn bản đủ, cộng điểm các dấu hiệu: dẫn trước văn bản thứ hai **từ 2 điểm trở lên** là chắc chắn. Nếu không, công cụ vẫn tạm chọn văn bản điểm cao nhất (bằng điểm thì lấy văn bản đứng trước), các văn bản khác để ở hồ sơ, và báo cần kiểm tra để bạn xem lại.
- **Nhiều văn bản/file:**
  - văn bản có tổng điểm **âm** bị loại vào hồ sơ;
  - văn bản có điểm **0 hoặc dương** được giữ;
  - nếu có văn bản được 0 điểm trong khi văn bản khác có dấu hiệu, văn bản đó bị đánh dấu cần kiểm tra;
  - nếu mọi văn bản đều âm, công cụ giữ cả và báo cần kiểm tra.

Văn bản nào bị giữ hay bỏ, và vì sao, được ghi trong cột `thong_tin` hoặc `canh_bao` của bảng Excel.

**Các tuỳ chọn khác:**

| Tuỳ chọn | Khi nào dùng |
|---|---|
| **Văn bản luôn có Quốc hiệu** | Bỏ tick nếu đơn vị có loại văn bản không có Quốc hiệu. Nếu không, những văn bản đó sẽ luôn bị báo cần kiểm tra. |
| **Giữ trang trắng nằm giữa văn bản** | Bật khi cần giữ đúng số tờ của bản scan, ví dụ scan 2 mặt có mặt sau trắng. |

---

## 3. Kết quả

```
KetQua/
  dat/            văn bản đã cắt, chắc chắn (giữ cấu trúc thư mục con như bản gốc)
  can_kiem_tra/   văn bản đã cắt nhưng cần người xem lại
  chot/           bộ file cuối cùng, sau khi bấm "Cắt bản chốt"
  bao_cao.xlsx    1 dòng/file: trang văn bản, trạng thái, cảnh báo, số & ngày công chứng đọc được, nhãn từng trang
  xem_lai.html    ảnh thu nhỏ từng trang (file cần kiểm tra lên đầu); bấm vào trang để mở bản gốc
  .cache/         chữ đã OCR — xoá đi nếu muốn OCR lại từ đầu
```

Ý nghĩa các trạng thái:

- **Đạt:** tìm thấy văn bản có tiêu đề, Quốc hiệu và lời chứng, và không có điểm nào đáng ngờ.
- **Cần kiểm tra:** có ít nhất một trong các trường hợp sau:
  - chưa chắc văn bản nào là văn bản chính (đã tạm chọn một văn bản);
  - thiếu lời chứng;
  - không thấy trang tiêu đề;
  - có trang hồ sơ xen giữa văn bản;
  - không thấy số công chứng.
- **Không thấy:** không nhận ra văn bản công chứng nào, ví dụ file chỉ có hồ sơ hoặc trang bị xoay ngang.
- **Lỗi:** file hỏng hoặc có mật khẩu.

### Đặt tên file kết quả

Ở mục **4. Đầu ra**, ô **Tên file văn bản** và **tên file hồ sơ** nhận một *mẫu tên*. Bạn chọn mẫu có sẵn hoặc gõ tự do; ngay dưới ô có dòng ví dụ để xem trước.

| Trường | Lấy từ | Ví dụ |
|---|---|---|
| `{ten}` | tên file gốc | `2023_027529` |
| `{so_cc}` | số công chứng trong lời chứng. Nếu khớp với số trong tên file thì lấy theo tên file, để tránh OCR đọc sai | `027529` |
| `{nam}` | năm công chứng | `2023` |
| `{ngay}` | ngày công chứng | `2023-11-30` |
| `{loai}` | tiêu đề văn bản, không dấu | `GIAY_UY_QUYEN` |
| `{stt}` | số thứ tự văn bản trong file (khi một file có nhiều văn bản) | `1` |

Ví dụ: mẫu `{nam}_{so_cc}_{loai}` cho ra `2023_027529_GIAY_UY_QUYEN.pdf`.

- Giữ nguyên cấu trúc thư mục con như bản gốc.
- **Trùng tên** thì tự thêm `(2)`, `(3)`…
- File có nhiều văn bản mà mẫu không có `{stt}` thì tự thêm `__vb1`, `__vb2`.
- Văn bản nào **thiếu dữ liệu** cho mẫu (ví dụ không đọc được số công chứng) thì **giữ tên gốc**. Bảng Excel có các cột `so_cong_chung`, `ngay_cong_chung`, `loai_van_ban` và `file_van_ban`. Bạn điền hoặc sửa các cột này, rồi bấm **Cắt bản chốt**: tên file sẽ được đặt lại theo đúng giá trị đã sửa.
- Nếu chọn **Xuất thêm phần hồ sơ còn lại**, khi cắt bản chốt phần hồ sơ được ghi vào thư mục **`chot_ho_so`**, cạnh thư mục `chot`.
- Ô **Bỏ trang trắng khỏi phần hồ sơ** được bật sẵn. Ô này áp dụng cả khi tách lẫn khi cắt bản chốt; trang trắng được nhận ra từ kết quả đọc chữ đã lưu, nên không phải đọc lại. Văn bản công chứng thì mặc định đã bỏ trang trắng.

### Kiểm tra thiếu, thừa, trùng trang

Với mỗi văn bản đã tách, công cụ tự kiểm tra số trang. Kết quả ghi ở cột **`nghi_thieu_trang`** trong bảng Excel. File có nghi vấn được đưa vào nhóm **cần kiểm tra**; trong trang xem lại có nút lọc **"Nghi thiếu/thừa trang"**.

| Cách kiểm tra | Ví dụ cảnh báo | Độ tin cậy |
|---|---|---|
| So với câu *"…mỗi bản chính gồm 02 tờ, 05 trang"* trong lời chứng. Nhận cả "bao gồm", "gồm có" và số viết bằng chữ ("hai mươi mốt trang") | lời chứng ghi 5 trang nhưng chỉ tách được 4 trang (thiếu 1) | Cao. Khi khớp, bảng ghi *"đủ 5/5 trang theo lời chứng"* |
| Số trang in trên trang ("1", "- 2 -", "Trang 3/5") | lưu ý số trang (chưa chắc): số trang in nhảy từ 2 (tr.4) sang 4 (tr.5) | Thấp. **Chỉ ghi chú** ở cột `thong_tin`, không đưa file vào nhóm cần kiểm tra |
| Số Điều nhảy cóc giữa hai trang liền nhau | lưu ý số trang (chưa chắc): Điều nhảy từ 2 (tr.1) sang 7 (tr.2) | Trung bình. **Chỉ ghi chú**, vì OCR có thể đọc sót tiêu đề Điều |
| Trang bị scan 2 lần liền nhau. So chữ với trang nhiều chữ, so hình ảnh với trang ít chữ như trang ký | tr.3 trùng tr.2 (scan 2 lần), đã bỏ khỏi văn bản | Cao. **Chỉ tự bỏ khi chắc chắn**: hai trang gần như y hệt về hình ảnh, *hoặc* bỏ đi thì số trang khớp đúng với lời chứng. Không chắc thì chỉ cảnh báo "nghi scan trùng, chưa bỏ". Cả hai trường hợp đều đưa file vào nhóm cần kiểm tra |
| Hai trang không liền nhau trong văn bản giống hệt | tr.2 và tr.5 gần như giống hệt (scan trùng?) | Chỉ cảnh báo, không tự bỏ |

Khi lời chứng ghi số trang **khớp** với số trang tách được, công cụ bỏ qua các dấu hiệu yếu (số trang in, số Điều), vì khi đó văn bản không thể thiếu trang.

Không phát hiện được khi cả ba điều sau cùng xảy ra:
- lời chứng không ghi số trang;
- trang không in số;
- trang bị mất không làm nhảy số Điều.

Cách viết cột `trang_van_ban` khi sửa tay:

| Viết | Ý nghĩa |
|---|---|
| `3-7` | lấy trang 3 đến 7 |
| `1,3-6` | lấy trang 1 và 3 đến 6 (bỏ trang 2) |
| `3-7;12-15` | hai văn bản, xuất thành 2 file |
| `BO` | bỏ qua file này |

---

## 4. Dùng bằng dòng lệnh (chạy hàng loạt, đặt lịch)

```
python tach_van_ban.py "D:\Scan" "D:\KetQua" --so-cc-trong-ten --ten-to-chuc "Văn phòng công chứng Hòa An"
python tach_van_ban.py "D:\Scan" "D:\KetQua" --theo-bang "D:\KetQua\bao_cao.xlsx"
```

| Tuỳ chọn | Tác dụng |
|---|---|
| `--nhieu-van-ban` | một file có thể chứa nhiều văn bản công chứng |
| `--vi-tri dau` hoặc `--vi-tri cuoi` | văn bản chính thường nằm ở đầu hoặc cuối file |
| `--so-cc-trong-ten` | tên file hoặc thư mục chứa số công chứng |
| `--ten-to-chuc "…"` | tên tổ chức hành nghề công chứng của đơn vị |
| `--khong-uu-tien-ngay` | không dùng ngày công chứng để chọn văn bản chính |
| `--khong-can-quoc-hieu` | văn bản không có Quốc hiệu vẫn được tính là đạt |
| `--giu-trang-trang` | giữ trang trắng nằm giữa văn bản |
| `--gioi-han N` | chỉ chạy N file đầu |
| `--so-luong N` | số file xử lý song song |
| `--dpi 300` | OCR nét hơn nhưng chậm hơn |
| `--xem-tat-ca` | tạo ảnh thu nhỏ cho cả file đạt |
| `--xuat-ho-so` | xuất thêm phần hồ sơ còn lại |
| `--luu-chu` | lưu chữ OCR để dò lỗi (**có dữ liệu cá nhân**) |
| `--luon-ocr` | OCR cả những trang đã có lớp chữ |
| `--tesseract "…\tesseract.exe"` | chỉ đường dẫn khi công cụ không tự tìm thấy Tesseract |
| `--engine screenai` | dùng engine OCR của Chrome (xem mục 6) |

Muốn thử công cụ mà không dùng hồ sơ thật thì chạy:

```
python tao_du_lieu_thu.py du_lieu_thu
```

Lệnh này tạo 8 file scan giả với nội dung bịa, mô phỏng các tình huống thường gặp.

---

## 5. Cách công cụ nhận diện (để biết khi nào nó sai)

Chữ OCR được bỏ dấu và viết hoa trước khi so khớp, nên OCR sai dấu vẫn nhận ra được. Mỗi trang được gắn một nhãn:

- **Mở đầu:** có dòng viết hoa ở đầu trang bắt đầu bằng HỢP ĐỒNG, VĂN BẢN, GIẤY ỦY QUYỀN, DI CHÚC…
- **Thân:** có "Điều 1, 2…", hoặc trang nhiều chữ, hoặc trang ký tên (BÊN A, BÊN B, "ký, ghi rõ họ tên").
- **Tờ bìa:** trang ít chữ có tên hợp đồng, nằm ngay trước trang đầu của hợp đồng cùng tên (vd bìa "HỒ SƠ LƯU – Số cc – HỢP ĐỒNG MUA BÁN…"). Tờ bìa được gộp vào văn bản đó, không tách thành văn bản riêng. Nếu lời chứng ghi số trang mà không tính tờ bìa thì tờ bìa được để ở phần hồ sơ.
- **Lời chứng:**
  - có dòng viết hoa "LỜI CHỨNG";
  - kết thúc ở dòng "Số công chứng…, quyển số…" hoặc dòng chữ ký "CÔNG CHỨNG VIÊN";
  - số và ngày công chứng được đọc từ chính trang này.
- **Hồ sơ:** có tiêu đề như PHIẾU YÊU CẦU, GIẤY CHỨNG NHẬN, CĂN CƯỚC, GIẤY XÁC NHẬN…; hoặc có dấu "Sao y bản chính" hay "Chứng thực bản sao…"; hoặc là trang rất ít chữ.
- **Trang trắng.**

Muốn thêm loại giấy tờ thì sửa các danh sách `TIEU_DE_VAN_BAN`, `TIEU_DE_HO_SO`, `DAU_HIEU_HO_SO` ở đầu file `tach_van_ban.py`.

**Các trường hợp hay phải xem tay:**

- trang bị xoay ngang hoặc lộn ngược;
- hợp đồng viết tay;
- tiêu đề hoặc số công chứng bị con dấu đè lên;
- số công chứng viết tay;
- văn bản không có Quốc hiệu.

**Tốc độ:** khoảng 0,5–1 giây mỗi trang trên một nhân CPU ở 200 dpi. Một máy 8 nhân xử lý được vài chục nghìn trang mỗi giờ. Nên đo thực tế bằng cách chạy thử 50 file.

---

## 6. (Thử nghiệm) Dùng Screen AI của Chrome

Screen AI là bộ nhận dạng chữ mà Chrome dùng để đọc PDF scan. Bản cài đã có sẵn thư viện để gọi nó, nhưng **không kèm Screen AI**, vì đây là phần mềm mã đóng của Google. Công cụ chỉ dùng bản mà Chrome trên máy bạn đã tự tải về.

1. Ở mục **3. Đọc chữ**, chọn công cụ **Screen AI của Chrome (thử nghiệm)**, rồi bấm **Kích hoạt Screen AI**.
2. Nếu Chrome chưa tải Screen AI, phần mềm hướng dẫn cách để Chrome tải (và đề nghị mở Chrome giúp):
   - kéo một file PDF scan vào Chrome và chờ khoảng 1 phút; **hoặc**
   - vào `chrome://components`, tìm mục *Screen AI*, bấm *Check for update*.

   Sau đó bấm **Kích hoạt Screen AI** lần nữa.
3. Khi kích hoạt, phần mềm sao lưu Screen AI sang thư mục riêng (`%LOCALAPPDATA%\locro`), để vẫn dùng được nếu Chrome cập nhật hay xoá nó. Sau đó phần mềm chạy thử đọc một ảnh mẫu và báo kết quả.

Lưu ý:
- Chế độ này chạy tuần tự từng file (không chạy song song).
- Chế độ này **chưa được kiểm thử trên hồ sơ thật**. Nên chạy thử vài chục file và so với Tesseract trước khi dùng rộng.
- Screen AI có thể ngừng chạy sau một bản cập nhật Chrome. Việc dùng nó ngoài Chrome chưa rõ về mặt điều khoản của Google.
- Chạy từ mã nguồn thì cài thêm thư viện: `pip install git+https://github.com/sergiocorreia/clv-locro`.
