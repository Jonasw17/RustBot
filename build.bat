@echo off
echo === Rust Bot Builder ===
echo.

echo Step 1: Creating clean virtual environment...
python -m venv build_env
call build_env\Scripts\activate.bat

echo.
echo Step 2: Installing only what the bot needs...
pip install --quiet -r requirements.txt
pip install --quiet pyinstaller

echo.
echo Step 3: Building rust-bot.exe ...
python -m PyInstaller ^
  --onefile ^
  --name rust-bot ^
  --console ^
  --collect-all discord ^
  --collect-all rustplus ^
  --collect-all dotenv ^
  --collect-all aiohttp ^
  --collect-all websockets ^
  bot.py

echo.
echo Step 4: Building pair.exe ...
python -m PyInstaller ^
  --onefile ^
  --name pair ^
  --console ^
  --collect-all rustplus ^
  pair.py

echo.
call deactivate
echo Cleaning up build environment...
rmdir /s /q build_env

echo.
if exist dist\rust-bot.exe (
    echo SUCCESS!
    echo.
    echo Your files are in dist\
    echo   rust-bot.exe  - the bot
    echo   pair.exe      - pairing tool
    echo.
    echo Copy both files plus your .env to wherever you want to run the bot.
) else (
    echo FAILED - check errors above
)
pause