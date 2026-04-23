@echo off
setlocal
title RAG-Destroyer
cd /d "%~dp0"

REM Run everything in this same CMD window only
REM Do not use "start" and do not spawn new windows
echo ============================================================
echo          RAG-Destroyer ^| Streamlit UI ^(single window^)
echo ============================================================
echo.

set "PYEXE="
if exist ".venv\Scripts\python.exe" set "PYEXE=%~dp0.venv\Scripts\python.exe"
if not defined PYEXE if exist "venv\Scripts\python.exe" set "PYEXE=%~dp0venv\Scripts\python.exe"

if defined PYEXE (
    echo [*] Using: %PYEXE%
) else (
    echo [!] No .venv\Scripts\python.exe — using system Python.
    set "PYEXE=python"
)

echo [*] Starting Streamlit in this window...
"%PYEXE%" -m streamlit run app.py
set EXITCODE=%ERRORLEVEL%

echo.
echo ---------------------------------------------------
if %EXITCODE% neq 0 (
    echo [!] Stopped with error ^(exit %EXITCODE%^).
    pause
) else (
    echo Stopped.
)
exit /b %EXITCODE%
