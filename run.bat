@echo off
setlocal

set "PYTHON_EXE="
for /f "delims=" %%I in ('where python 2^>nul') do (
    if not defined PYTHON_EXE set "PYTHON_EXE=%%I"
)

if not defined PYTHON_EXE (
    if exist "%USERPROFILE%\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" set "PYTHON_EXE=%USERPROFILE%\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
)

if not defined PYTHON_EXE (
    echo Python was not found. Install Python 3.12+ or update run.bat with your Python path.
    exit /b 1
)

"%PYTHON_EXE%" -m pixel_annotator %*
