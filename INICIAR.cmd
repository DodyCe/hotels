@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>nul
if not errorlevel 1 (
    py -3 start.py --open
    goto :finish
)
if exist "%USERPROFILE%\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" (
    "%USERPROFILE%\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" start.py --open
    goto :finish
)
where python >nul 2>nul
if not errorlevel 1 (
    python start.py --open
    goto :finish
)
echo Necesitas Python 3.12 o superior para iniciar los microservicios.
:finish
pause
