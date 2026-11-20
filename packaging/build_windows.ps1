# Đóng gói bản Windows: TachVanBan.exe + Tesseract + gói tiếng Việt, rồi tự kiểm tra và nén thành .zip
#
# Chạy trên máy Windows đã có Python (kèm: pip install -r requirements.txt pyinstaller) và Tesseract:
#   powershell -ExecutionPolicy Bypass -File packaging\build_windows.ps1
# Tham số:
#   -TesseractDir  thư mục cài Tesseract (mặc định C:\Program Files\Tesseract-OCR)
#   -VieModel      đường dẫn vie.traineddata để chép kèm (nếu Tesseract chưa có gói tiếng Việt)
#   -BoQuaKiemTra  không chạy tự kiểm tra sau khi đóng gói

param(
    [string]$TesseractDir = "C:\Program Files\Tesseract-OCR",
    [string]$VieModel = "",
    [switch]$BoQuaKiemTra
)
$ErrorActionPreference = "Stop"
$goc = Split-Path -Parent $PSScriptRoot
Set-Location $goc

$phienBan = (Select-String -Path "tach_van_ban.py" -Pattern 'PHIEN_BAN = "(.+)"').Matches[0].Groups[1].Value
Write-Host "== Đóng gói Tách văn bản công chứng $phienBan"

# --- 1. Tìm Tesseract
if (-not (Test-Path (Join-Path $TesseractDir "tesseract.exe"))) {
    $tim = Get-ChildItem "C:\Program Files", "C:\Program Files (x86)" -Filter tesseract.exe -Recurse -Depth 2 -ErrorAction SilentlyContinue | Select-Object -First 1
    if (-not $tim) { throw "Không tìm thấy tesseract.exe. Cài Tesseract hoặc chỉ -TesseractDir." }
    $TesseractDir = $tim.DirectoryName
}
Write-Host "Tesseract: $TesseractDir"

# --- 2. PyInstaller
if (Test-Path "dist\TachVanBan") { Remove-Item "dist\TachVanBan" -Recurse -Force }
python -m PyInstaller --noconfirm --clean --windowed --name TachVanBan `
    --paths . --hidden-import tach_van_ban --hidden-import tao_du_lieu_thu `
    --distpath dist --workpath build giao_dien.py
if ($LASTEXITCODE -ne 0) { throw "PyInstaller lỗi" }
$dich = "dist\TachVanBan"

# --- 3. Chép Tesseract kèm theo, chỉ giữ gói eng/osd/vie cho nhẹ
Copy-Item $TesseractDir "$dich\tesseract" -Recurse
Get-ChildItem "$dich\tesseract\tessdata\*.traineddata" |
    Where-Object { $_.BaseName -notin @("eng", "osd", "vie") } | Remove-Item -Force
Remove-Item "$dich\tesseract\tesseract-uninstall.exe" -ErrorAction SilentlyContinue
if ($VieModel) { Copy-Item $VieModel "$dich\tesseract\tessdata\vie.traineddata" -Force }
if (-not (Test-Path "$dich\tesseract\tessdata\vie.traineddata")) {
    throw "Thiếu gói tiếng Việt: chỉ -VieModel tới file vie.traineddata."
}

# --- 4. Tài liệu & giấy phép
Copy-Item README.md, HUONG_DAN.md, LICENSE, THIRD_PARTY_LICENSES.md $dich

# --- 5. Tự kiểm tra bản đóng gói trên dữ liệu giả (dùng đúng Tesseract đi kèm)
if (-not $BoQuaKiemTra) {
    $kt = Join-Path $env:TEMP "tvb_tu_kiem_tra"
    if (Test-Path $kt) { Remove-Item $kt -Recurse -Force }
    $p = Start-Process -FilePath "$dich\TachVanBan.exe" -ArgumentList "--tu-kiem-tra", "`"$kt`"" -Wait -PassThru
    Get-Content (Join-Path $kt "tu_kiem_tra.txt") -Encoding UTF8 | Write-Host
    if ($p.ExitCode -ne 0) { throw "Tự kiểm tra KHÔNG ĐẠT (mã thoát $($p.ExitCode))" }
}

# --- 6. Nén
$zip = "dist\TachVanBan-$phienBan-windows-x64.zip"
if (Test-Path $zip) { Remove-Item $zip }
Compress-Archive -Path $dich -DestinationPath $zip
Write-Host "== Xong: $zip"
