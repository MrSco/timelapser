@echo off
echo Setting up Timelapser...
cd /d %~dp0

echo Creating virtual environment...
python -m venv .venv

echo Activating virtual environment...
call .venv\Scripts\activate.bat

echo Installing dependencies...
pip install -e .

echo Creating .env file...
if not exist .env (
    copy .env.example .env
    echo .env file created. Please edit it with your configuration.
) else (
    echo .env file already exists.
)

echo Setup complete!
echo You can now run Timelapser using run_timelapser.bat
pause 