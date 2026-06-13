"""ローカル実行用のCLIエントリ。実体は src/sync.py。

例:
  uv run python main.py --count 1 --dry-run
  uv run python main.py --count 3
"""
from src.sync import _main

if __name__ == "__main__":
    _main()
