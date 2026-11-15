# -*- coding: utf-8 -*-
"""Read-only status check for the native block install."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CORE = ROOT / "WER_函数库" / "工具" / "原生积木" / "原生积木核心.py"


def main() -> int:
    print("=" * 68)
    print(" WER 原生积木 · 状态检查（只读）")
    print("=" * 68)
    if not CORE.is_file():
        print("[STOP] 找不到：", CORE)
        return 2
    rc = subprocess.call([sys.executable, str(CORE), "status"], cwd=str(ROOT))
    print()
    print("提示：status 只检查「我的函数」补丁；双板通讯分类请在 IDE 里看")
    print("      左侧是否出现「双板通讯」（4 个积木）。")
    return rc


if __name__ == "__main__":
    sys.exit(main())
