@echo off
rem ============================================================
rem  Dong goi HP Cons PDF thanh file exe duy nhat (PyInstaller)
rem  Ket qua: dist\HPConsPDF.exe
rem ============================================================
cd /d "%~dp0"

python -m pip install -r requirements.txt || goto :err

python -m PyInstaller --noconfirm --clean --onefile --windowed ^
    --name "HPConsPDF" --icon logo.ico ^
    --add-data "logo.png;." --add-data "logo.ico;." ^
    --collect-all pypdfium2 --collect-all pypdfium2_raw ^
    --hidden-import PyQt6.QtPrintSupport --hidden-import PyQt6.QtNetwork ^
    main.py || goto :err

echo.
echo ============================================
echo  XONG! File ket qua: dist\HPConsPDF.exe
echo ============================================
pause
exit /b 0

:err
echo.
echo  *** LOI khi build - xem thong bao ben tren ***
pause
exit /b 1
