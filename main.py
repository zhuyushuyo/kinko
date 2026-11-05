"""KINKO — アカウント金庫。 起動: python main.py"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from kinko.ui.app import run  # noqa: E402

if __name__ == "__main__":
    sys.exit(run())
