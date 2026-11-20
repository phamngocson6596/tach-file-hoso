# Đóng gói bản Windows: TachVanBan.exe + Tesseract + gói tiếng Việt (đã rút gọn), tự kiểm tra,
# rồi xuất 2 dạng: TachVanBan-CaiDat.exe (bộ cài 1 file, nén LZMA2) và TachVanBan-KhongCanCai.zip.
# Tên file KHÔNG kèm số phiên bản để link "bản mới nhất" luôn cố định:
#   https://github.com/phamngocson6596/tach-file-hoso/releases/latest/download/TachVanBan-CaiDat.exe
#
# Chạy trên máy Windows đã có Python (kèm: pip install -r requirements.txt pyinstaller),
# Tesseract và Inno Setup 6:
#   powershell -ExecutionPolicy Bypass -File packaging\build_windows.ps1
# Tham số:
#   -TesseractDir  thư mục cài Tesseract (mặc định C:\Program Files\Tesseract-OCR)
#   -VieModel      đường dẫn vie.traineddata để chép kèm (nếu Tesseract chưa có gói tiếng Việt)
#   -BoQuaKiemTra  không chạy tự kiểm tra
#   -BoQuaBoCai    không dựng bộ cài (chỉ ra bản zip)

param(
    [string]$TesseractDir = "C:\Program Files\Tesseract-OCR",
    [string]$VieModel = "",
    [switch]$BoQuaKiemTra,
    [switch]$BoQuaBoCai
)
$ErrorActionPreference = "Stop"
$goc = Split-Path -Parent $PSScriptRoot
Set-Location $goc

$phienBan = (Select-String -Path "tach_van_ban.py" -Pattern 'PHIEN_BAN = "(.+)"').Matches[0].Groups[1].Value
Write-Host "== Đóng gói Tách văn bản công chứng $phienBan"

function Get-MB($duongDan) {
    $tong = (Get-ChildItem $duongDan -Recurse -File -ErrorAction SilentlyContinue | Measure-Object Length -Sum).Sum
    return [math]::Round(($tong / 1MB), 1)
}

function Test-TuKiemTra([string]$exe, [string]$ten) {
    $kt = Join-Path $env:TEMP "tvb_tu_kiem_tra_$ten"
    if (Test-Path $kt) { Remove-Item $kt -Recurse -Force }
    $p = Start-Process -FilePath $exe -ArgumentList "--tu-kiem-tra", "`"$kt`"" -Wait -PassThru
    Write-Host "-- Tự kiểm tra ($ten):"
    Get-Content (Join-Path $kt "tu_kiem_tra.txt") -Encoding UTF8 | Write-Host
    if ($p.ExitCode -ne 0) { throw "Tự kiểm tra ($ten) KHÔNG ĐẠT (mã thoát $($p.ExitCode))" }
}

# --- 1. Tìm Tesseract
if (-not (Test-Path (Join-Path $TesseractDir "tesseract.exe"))) {
    $tim = Get-ChildItem "C:\Program Files", "C:\Program Files (x86)" -Filter tesseract.exe -Recurse -Depth 2 -ErrorAction SilentlyContinue | Select-Object -First 1
    if (-not $tim) { throw "Không tìm thấy tesseract.exe. Cài Tesseract hoặc chỉ -TesseractDir." }
    $TesseractDir = $tim.DirectoryName
}
Write-Host "Tesseract: $TesseractDir"

# --- 2. PyInstaller
#     Bỏ phần AI phân tích bố cục của PyMuPDF 2.x (mô hình ONNX + numpy + onnxruntime): công cụ không dùng tới
if (Test-Path "dist\TachVanBan") { Remove-Item "dist\TachVanBan" -Recurse -Force }
python -m PyInstaller --noconfirm --clean --windowed --name TachVanBan `
    --paths . --hidden-import tach_van_ban --hidden-import tao_du_lieu_thu `
    --exclude-module numpy --exclude-module onnxruntime --exclude-module pymupdf.layout --exclude-module pymupdf4llm `
    --distpath dist --workpath build giao_dien.py
if ($LASTEXITCODE -ne 0) { throw "PyInstaller lỗi" }
$dich = "dist\TachVanBan"
Remove-Item "$dich\_internal\pymupdf\layout" -Recurse -Force -ErrorAction SilentlyContinue

# --- 3. Chép Tesseract kèm theo và rút gọn:
#        chỉ giữ gói tiếng Việt; bỏ công cụ huấn luyện (*.exe khác tesseract.exe);
#        chỉ giữ DLL mà tesseract.exe thật sự nạp (dò bảng import)
Copy-Item $TesseractDir "$dich\tesseract" -Recurse
Get-ChildItem "$dich\tesseract\tessdata\*.traineddata" |
    Where-Object { $_.BaseName -ne "vie" } | Remove-Item -Force
Get-ChildItem "$dich\tesseract\*.exe" | Where-Object { $_.Name -ne "tesseract.exe" } | Remove-Item -Force
if ($VieModel) { Copy-Item $VieModel "$dich\tesseract\tessdata\vie.traineddata" -Force }
if (-not (Test-Path "$dich\tesseract\tessdata\vie.traineddata")) {
    throw "Thiếu gói tiếng Việt: chỉ -VieModel tới file vie.traineddata."
}
python packaging\rut_gon_tesseract.py "$dich\tesseract"
if ($LASTEXITCODE -ne 0) { throw "Rút gọn Tesseract lỗi" }

# --- 4. Tài liệu & giấy phép
Copy-Item README.md, HUONG_DAN.md, LICENSE, THIRD_PARTY_LICENSES.md $dich

# --- 5. Tự kiểm tra bản đóng gói trên dữ liệu giả (dùng đúng Tesseract đi kèm)
if (-not $BoQuaKiemTra) { Test-TuKiemTra "$dich\TachVanBan.exe" "ban_dong_goi" }

# --- 6. Báo cáo dung lượng (xem trong log của GitHub Actions)
$gocDich = (Resolve-Path $dich).Path
Write-Host ("== Dung lượng sau khi giải nén: {0} MB" -f (Get-MB $dich))
$bang = foreach ($muc in (Get-ChildItem "$dich\_internal", "$dich\tesseract", "$dich\tesseract\tessdata")) {
    $mb = if ($muc.PSIsContainer) { Get-MB $muc.FullName } else { [math]::Round(($muc.Length / 1MB), 1) }
    [pscustomobject]@{ MB = $mb; Muc = $muc.FullName.Substring($gocDich.Length + 1) }
}
$bang | Sort-Object MB -Descending | Select-Object -First 25 | Format-Table -AutoSize | Out-String | Write-Host

# --- 7. Bản zip chạy không cần cài
$zip = "dist\TachVanBan-KhongCanCai.zip"
if (Test-Path $zip) { Remove-Item $zip }
Compress-Archive -Path $dich -DestinationPath $zip -CompressionLevel Optimal

# --- 8. Bộ cài 1 file (Inno Setup) + cài thử im lặng rồi tự kiểm tra bản đã cài
if (-not $BoQuaBoCai) {
    $iscc = @("${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe", "$env:ProgramFiles\Inno Setup 6\ISCC.exe",
              "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe") | Where-Object { Test-Path $_ } | Select-Object -First 1
    if (-not $iscc) { throw "Không tìm thấy Inno Setup 6 (ISCC.exe). Cài Inno Setup hoặc chạy với -BoQuaBoCai." }
    & $iscc /Qp "/DMyAppVersion=$phienBan" "packaging\TachVanBan.iss"
    if ($LASTEXITCODE -ne 0) { throw "Inno Setup lỗi" }
    $setup = "dist\TachVanBan-CaiDat.exe"
    if (-not $BoQuaKiemTra) {
        $caiThu = Join-Path $env:TEMP "tvb_cai_thu"
        if (Test-Path $caiThu) { Remove-Item $caiThu -Recurse -Force }
        $p = Start-Process -FilePath $setup -ArgumentList "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/CURRENTUSER", "/DIR=`"$caiThu`"" -Wait -PassThru
        if ($p.ExitCode -ne 0) { throw "Cài thử bộ cài lỗi (mã thoát $($p.ExitCode))" }
        Test-TuKiemTra "$caiThu\TachVanBan.exe" "ban_da_cai"
        Start-Process -FilePath "$caiThu\unins000.exe" -ArgumentList "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART" -Wait | Out-Null
    }
}

Write-Host "== Xong. File phát hành:"
Get-ChildItem "dist\TachVanBan-CaiDat.exe", "dist\TachVanBan-KhongCanCai.zip" -ErrorAction SilentlyContinue | ForEach-Object {
    Write-Host ("   {0,-50} {1,7:N1} MB" -f $_.Name, ($_.Length / 1MB))
}
