@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo === Cai thu vien Python cho cong cu tach van ban ===
where py >nul 2>nul && (py -m pip install --upgrade -r requirements.txt) || (python -m pip install --upgrade -r requirements.txt)
if errorlevel 1 (
  echo.
  echo LOI: khong cai duoc. Kiem tra da cai Python va tick "Add python.exe to PATH" chua.
) else (
  echo.
  echo Xong. Nho cai them Tesseract OCR co goi tieng Viet ^(xem HUONG_DAN.md^).
  echo Sau do bam dup chay_giao_dien.bat de mo cong cu.
)
pause
