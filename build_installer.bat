@echo off
rem ============================================================
rem  Dong goi HP Cons PDF thanh FILE CAI DAT (setup.exe)
rem  Buoc 1: build app dang onedir (PyInstaller)
rem  Buoc 2: dong goi bang Inno Setup -> Output\HPConsPDF_Setup_x.x.x.exe
rem ============================================================
cd /d "%~dp0"

echo [1/2] Build ung dung (onedir)...
python -m PyInstaller --noconfirm --clean --onedir --windowed ^
    --name "HPConsPDF" --icon logo.ico ^
    --add-data "logo.png;." --add-data "logo.ico;." ^
    --collect-all pypdfium2 --collect-all pypdfium2_raw ^
    --hidden-import PyQt6.QtPrintSupport --hidden-import PyQt6.QtNetwork ^
    main.py || goto :err

echo.
echo [2/2] Dong goi file cai dat (Inno Setup)...
set "ISCC=C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
if not exist "%ISCC%" set "ISCC=C:\Program Files\Inno Setup 6\ISCC.exe"
if not exist "%ISCC%" (
    echo  *** Chua cai Inno Setup. Tai tai: https://jrsoftware.org/isdl.php ***
    goto :err
)
"%ISCC%" installer.iss || goto :err

echo.
echo ============================================
echo  XONG! File cai dat nam trong thu muc: Output\
echo ============================================
pause
exit /b 0

:err
echo.
echo  *** CO LOI khi dong goi - xem thong bao ben tren ***
pause
exit /b 1
