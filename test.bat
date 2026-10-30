@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"
if exist ".runtime\node.exe" set "PATH=%CD%\.runtime;%PATH%"
".venv\Scripts\python.exe" tools\prepare_reveal.py
if errorlevel 1 exit /b 1
node --test --test-concurrency=1 tests\node.test.mjs tests\render.test.mjs tests\fun-deck.test.mjs
if errorlevel 1 exit /b 1
".venv\Scripts\python.exe" -m unittest discover -s tests -p "test_*.py" -v
exit /b %ERRORLEVEL%
