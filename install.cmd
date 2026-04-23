@echo off
setlocal
set "EASYAI_LAUNCHER_DIR=%CD%"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0install.ps1" %*
