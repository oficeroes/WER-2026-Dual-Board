# -*- coding: utf-8 -*-
"""Build + install the dual-board native blocks (Windows).

Precondition: "My Functions" was installed once via
    WER_函数库\\工具\\原生积木\\安装原生积木.cmd
so the original-asset backup and abilix_userlib.js exist.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / "tools" / "build_dual.py"
PS1 = ROOT / "WER_函数库" / "安装包_双板通讯" / "install_dual.ps1"


def main() -> int:
    print("=" * 68)
    print(" WER 双板通讯原生积木 · 构建并安装")
    print("=" * 68)
    print("前置：已经运行过 WER_函数库\\工具\\原生积木\\安装原生积木.cmd")
    print()

    rc = subprocess.call([sys.executable, str(BUILD)], cwd=str(ROOT))
    if rc != 0:
        print("\n[STOP] 构建失败（退出码 %d）。" % rc)
        print("如果提示 abilix_userlib.js 缺失：先安装「我的函数」。")
        return rc

    if not PS1.is_file():
        print("\n[STOP] 找不到安装脚本：", PS1)
        return 2

    print("\n" + "=" * 68)
    print(" 安装（会弹 UAC，请点「是」）")
    print("=" * 68)
    # install_dual.ps1 自己会提权；提权后是另一个窗口，这里只负责拉起。
    return subprocess.call([
        "powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass",
        "-File", str(PS1),
    ])


if __name__ == "__main__":
    sys.exit(main())
