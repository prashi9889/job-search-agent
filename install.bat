@echo off
rem Double-click to install. Put profile.json in this folder first.
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0install.ps1"
echo.
pause
