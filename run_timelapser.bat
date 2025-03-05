@echo off
echo Starting Timelapser...
cd /d %~dp0
if exist .venv\Scripts\activate.bat (
    call .venv\Scripts\activate.bat
    python app.py
) else (
    echo Virtual environment not found. Please run setup first.
    pause
) 