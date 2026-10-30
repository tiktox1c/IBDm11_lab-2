@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"
if exist ".runtime\node.exe" set "PATH=%CD%\.runtime;%PATH%"
if not exist ".venv\Scripts\python.exe" goto setup_required
".venv\Scripts\python.exe" main.py %*
if errorlevel 1 (
  echo Ошибка запуска. Проверьте установку Python, Node.js и Google Chrome.
  pause
)
exit /b
:setup_required
echo Сначала запустите setup.bat. Инструкция: README.md.
pause
exit /b 1
