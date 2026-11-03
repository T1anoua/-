@echo off
chcp 65001 >nul
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0build\windows_task.ps1" -Task serial
if errorlevel 1 echo Operation did not complete. See the message above.
pause
