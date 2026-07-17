@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"

echo ============================================
echo   Update IPTV channel list from M3U file
echo ============================================
echo.

set PYCMD=
set PYVER=

for /f "delims=" %%v in ('python --version 2^>nul') do set PYVER=%%v
echo !PYVER! | find "Python" >nul 2>nul
if !errorlevel! equ 0 (
    set PYCMD=python
) else (
    set PYVER=
    for /f "delims=" %%v in ('py --version 2^>nul') do set PYVER=%%v
    echo !PYVER! | find "Python" >nul 2>nul
    if !errorlevel! equ 0 (
        set PYCMD=py
    )
)

if "!PYCMD!"=="" (
    echo ERROR: A working Python installation was not found.
    echo See start_server.bat for how to fix this.
    goto end
)

echo This will download the latest channel list from your IPTV provider
echo automatically ^(using the saved login in tools\iptv_credentials.json^)
echo and update the site with it.
echo.
pause

!PYCMD! tools\update_channels_from_m3u.py

echo.
echo If the site is already open in your browser, do a hard refresh
echo (Ctrl+F5) to make sure you see the updated channel list.
echo.

:end
pause
