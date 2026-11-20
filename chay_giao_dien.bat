@echo off
cd /d "%~dp0"
where pyw >nul 2>nul && (start "" pyw "%~dp0giao_dien.py" & exit /b)
where pythonw >nul 2>nul && (start "" pythonw "%~dp0giao_dien.py" & exit /b)
echo Khong tim thay Python. Hay cai Python (tick "Add python.exe to PATH") roi chay cai_dat.bat.
pause
