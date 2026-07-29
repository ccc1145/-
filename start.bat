@echo off
setlocal
cd /d "%~dp0"

rem PowerShell's per-machine execution policy does not affect this launcher.
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0tools\start-dev.ps1"

if errorlevel 1 (
    echo.
    echo Startup failed. See the message above for details.
    pause
)

