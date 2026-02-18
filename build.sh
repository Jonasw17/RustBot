#!/bin/bash
set -e

echo "=== Rust Bot Builder ==="
echo

echo "Step 1: Creating clean virtual environment..."
python3 -m venv build_env
source build_env/bin/activate

echo
echo "Step 2: Installing only what the bot needs..."
pip install --quiet -r requirements.txt
pip install --quiet pyinstaller

echo
echo "Step 3: Building rust-bot ..."
python -m PyInstaller \
  --onefile \
  --name rust-bot \
  --console \
  --collect-all discord \
  --collect-all rustplus \
  --collect-all dotenv \
  --collect-all aiohttp \
  --collect-all websockets \
  bot.py


deactivate

echo
echo "Cleaning up build environment..."
rm -rf build_env

echo
if [ -f dist/rust-bot ]; then
    echo "SUCCESS!"
    echo
    echo "Your files are in dist/"
    echo "  rust-bot  - the bot"
    echo
    echo "Copy both files plus your .env to wherever you want to run the bot."
else
    echo "FAILED - check errors above"
    exit 1
fi