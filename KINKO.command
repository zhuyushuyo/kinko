#!/bin/bash
# KINKO を起動します（Finder でダブルクリック）。
cd "$(dirname "$0")" || exit 1
PY="$(command -v python3)"
if [ -z "$PY" ]; then
  echo "python3 が見つかりません。README の「必要なもの」を見てください。"
  read -r -p "Enter で閉じます" _
  exit 1
fi
if ! "$PY" -c "import PyQt6, cryptography, argon2" 2>/dev/null; then
  echo "必要なライブラリを入れます: python3 -m pip install -r requirements.txt"
  if ! "$PY" -m pip install -r requirements.txt; then
    echo "インストールできませんでした。README の「必要なもの」を見てください。"
    read -r -p "Enter で閉じます" _
    exit 1
  fi
fi
"$PY" main.py
