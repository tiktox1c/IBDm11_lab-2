@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"
set "PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1"
set "PIP_CACHE_DIR=%CD%\.cache\pip"
set "npm_config_cache=%CD%\.cache\npm"
set "TEMP=%CD%\tmp"
set "TMP=%CD%\tmp"
if not exist "tmp" mkdir "tmp"
if exist ".runtime\node.exe" set "PATH=%CD%\.runtime;%PATH%"

echo HTML Presentation Converter: установка зависимостей
if exist ".venv\Scripts\python.exe" goto check_python
py -3 -c "import sys; assert sys.version_info >= (3,11)" >nul 2>nul
if not errorlevel 1 goto create_py
python -c "import sys; assert sys.version_info >= (3,11)" >nul 2>nul
if errorlevel 1 goto missing_python
python -m venv .venv
goto check_venv
:create_py
py -3 -m venv .venv
:check_venv
if errorlevel 1 goto failed
:check_python
".venv\Scripts\python.exe" -c "import sys, tkinter; assert sys.version_info >= (3,11)"
if errorlevel 1 goto missing_python
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto failed
node -e "if(Number(process.versions.node.split('.')[0]) < 22) process.exit(1)" >nul 2>nul
if errorlevel 1 goto missing_node
node -e "require('playwright')" >nul 2>nul
if not errorlevel 1 goto verify
call npm install --omit=dev --ignore-scripts --no-audit --no-fund
if errorlevel 1 goto failed
:verify
".venv\Scripts\python.exe" main.py --check
if errorlevel 1 goto failed
echo.
echo Готово. Для запуска откройте run.bat.
echo Отдельный Chromium не устанавливался.
pause
exit /b 0
:missing_python
echo Нужен Python 3.11+ с компонентом Tcl/Tk: https://www.python.org/downloads/windows/
echo При установке включите Python Launcher и Add Python to PATH.
goto failed
:missing_node
echo Нужен Node.js LTS 22+ вместе с npm: https://nodejs.org/
goto failed
:failed
echo.
echo Настройка не завершена. Прочитайте сообщение выше и README.md.
echo Системные программы и браузеры автоматически не устанавливаются.
pause
exit /b 1
