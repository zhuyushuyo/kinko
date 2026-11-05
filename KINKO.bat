@echo off
rem KINKO を起動します（ダブルクリック）。
cd /d "%~dp0"
python -c "import PyQt6, cryptography, argon2" 2>nul || python -m pip install -r requirements.txt
start "" pythonw main.py
