@echo off
rem Chay HP Cons PDF tu ma nguon (danh cho may dev)
cd /d "%~dp0"
if exist "C:\Python311-nuget\tools\python.exe" (
    start "" "C:\Python311-nuget\tools\pythonw.exe" main.py
) else (
    start "" pythonw main.py
)
