# -*- coding: utf-8 -*-
"""Restore the original AbilixScratch3.0 browser_assets (UAC handled by the .cmd)."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CMD = ROOT / "WER_函数库" / "工具" / "原生积木" / "还原原版.cmd"


def main() -> int:
    print("=" * 68)
    print(" 还原原版资源包（会弹 UAC）")
    print("=" * 68)
    if not CMD.is_file():
        print("[STOP] 找不到：", CMD)
        return 2
    return subprocess.call(["cmd.exe", "/c", str(CMD)])


if __name__ == "__main__":
    sys.exit(main())
