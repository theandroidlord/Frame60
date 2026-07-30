@echo off
REM One-time setup for frame60 on Windows cmd shell.
REM Same job as install.sh does for Termux -- get python + ffmpeg on PATH.

echo Checking for python...
where python >nul 2>nul
if %errorlevel% neq 0 (
    echo Python not found. Installing via winget...
    winget install -e --id Python.Python.3.12
) else (
    echo Python already installed. Good rep.
)

echo Checking for ffmpeg...
where ffmpeg >nul 2>nul
if %errorlevel% neq 0 (
    echo ffmpeg not found. Installing via winget...
    winget install -e --id Gyan.FFmpeg
) else (
    echo ffmpeg already installed. Good rep.
)

echo.
echo If either install just ran for the first time, close and reopen this
echo cmd window so PATH picks up the new binaries.
echo.
echo Setup complete. Run from inside this project folder with:
echo   python -m frame60 IN.mp4 OUT.mp4 --profile battery-saver
