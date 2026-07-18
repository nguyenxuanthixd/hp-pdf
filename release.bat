@echo off
rem ============================================================
rem  Phat hanh phien ban moi HP Cons PDF
rem  Cach dung:  release.bat 1.0.2
rem  -> dat version, commit, tao tag v1.0.2, push len GitHub.
rem     GitHub Actions se tu build installer va dang Release.
rem ============================================================
setlocal
cd /d "%~dp0"

if "%~1"=="" (
    echo Dung: release.bat ^<x.y.z^>   (vi du: release.bat 1.0.2^)
    exit /b 1
)
set "VER=%~1"

echo [1/4] Dat version = %VER% ...
python tools\bump_version.py %VER% || goto :err

echo [2/4] Commit thay doi version ...
git add hpcons_pdf\__init__.py installer.iss || goto :err
git commit -m "Phat hanh v%VER%" || goto :err

echo [3/4] Tao tag v%VER% ...
git tag v%VER% || goto :err

echo [4/4] Push code + tag len GitHub ...
git push || goto :err
git push origin v%VER% || goto :err

echo.
echo ============================================
echo  XONG! GitHub Actions dang build v%VER%.
echo  Xem tien do: tab "Actions" tren trang GitHub cua repo.
echo  Ban cai dat se xuat hien o muc "Releases" khi build xong.
echo ============================================
exit /b 0

:err
echo.
echo  *** CO LOI - xem thong bao ben tren ***
exit /b 1
