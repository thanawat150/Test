@echo off
setlocal
cd /d "%~dp0"

if not exist .venv py -3.11 -m venv .venv
call .venv\Scripts\activate.bat

python -m pip install --upgrade pip
pip install -r requirements-dev.txt

pytest -q
if errorlevel 1 exit /b 1

pyinstaller --noconfirm --clean --onefile --windowed ^
  --name VideoSegmentCutter ^
  --collect-all imageio_ffmpeg ^
  --collect-all python_calamine ^
  video_segment_cutter.py

echo.
echo Build complete:
echo %CD%\dist\VideoSegmentCutter.exe
pause
