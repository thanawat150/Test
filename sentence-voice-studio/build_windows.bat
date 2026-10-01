@echo off
setlocal
cd /d "%~dp0"

if not exist .venv (
    py -3.11 -m venv .venv
)

call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -r requirements-dev.txt

pytest -q
if errorlevel 1 exit /b 1

pyinstaller --noconfirm --clean --onefile --windowed ^
  --name SentenceVoiceStudio ^
  --collect-all edge_tts ^
  sentence_voice_studio.py

echo.
echo Build complete:
echo %CD%\dist\SentenceVoiceStudio.exe
pause
