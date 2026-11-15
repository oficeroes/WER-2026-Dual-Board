# -*- coding: utf-8 -*-
r"""从本机已安装的 IDE 构建「双板通讯」补丁（不自动安装）。

前置：
  1. 已运行 WER_函数库\工具\原生积木\安装原生积木.cmd
     （这一步会生成 备份\browser_assets.原始.*.bin，并让当前资源包含「我的函数」prelude）
  2. 已完全关闭 AbilixScratch3.0

用法：
  python tools\build_dual.py
  set WER_ASSETS=D:\...\browser_assets
  python tools\build_dual.py

输出：
  WER_函数库\安装包_双板通讯\browser_assets.patched + install_dual.cmd/.ps1
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parents[1]
ASSETS_DEFAULT = Path(r"D:\Program Files\AbilixScratch3.0\AbilixScratch3.0_Data\Resources\browser_assets")
BUILD = ROOT / "WER_函数库" / "工具" / "双板通讯" / "构建双板通讯扩展.py"
BACKUP_DIR = ROOT / "WER_函数库" / "工具" / "原生积木" / "备份"
OUT_DIR = ROOT / "WER_函数库" / "安装包_双板通讯"


def find_backup() -> Optional[Path]:
    if not BACKUP_DIR.exists():
        return None
    files = sorted(BACKUP_DIR.glob("browser_assets.原始.*.bin"), key=lambda p: p.stat().st_mtime, reverse=True)
    return files[0] if files else None


def has_userlib(assets: Path) -> bool:
    try:
        sys.path.insert(0, str(ROOT / "WER_函数库" / "工具" / "底层"))
        import patch_browser_assets as pb  # type: ignore
        info = pb.read_zfb_index(str(assets), with_data=False)
        names = {e["name"] for e in info["entries"]}
        return "/Blockly_Code/abilix_userlib.js" in names
    except Exception as exc:  # 读不了就交给构建脚本报更具体的错
        print(f"[warn] 无法预检资源包条目：{exc}")
        return True


def main() -> int:
    assets = Path(os.environ.get("WER_ASSETS", str(ASSETS_DEFAULT)))
    print("=" * 68)
    print(" WER 双板通讯原生积木 · 构建补丁")
    print("=" * 68)
    print("项目根目录 :", ROOT)
    print("IDE 资源包 :", assets)

    if not assets.is_file():
        print("\n[STOP] 找不到 IDE 资源包：", assets)
        print("      如果 IDE 装在别处，请设置 WER_ASSETS 或改用 --assets 参数。")
        return 2

    backup = find_backup()
    if backup is None:
        print("\n[STOP] 找不到原版备份：")
        print("      ", BACKUP_DIR / "browser_assets.原始.<sha>.bin")
        print("       请先运行：WER_函数库\\工具\\原生积木\\安装原生积木.cmd")
        print("       它会安装「我的函数」，并自动生成这个原版备份。")
        return 2
    print("原版备份   :", backup)

    if not has_userlib(assets):
        print("\n[STOP] 当前 IDE 资源包里没有「我的函数」补丁（abilix_userlib.js）。")
        print("       请先运行：WER_函数库\\工具\\原生积木\\安装原生积木.cmd")
        return 2

    if not BUILD.is_file():
        print("\n[STOP] 找不到构建脚本：", BUILD)
        return 2

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    cmd = [
        sys.executable, str(BUILD),
        "--assets", str(assets),
        "--orig", str(backup),
        "--out", str(OUT_DIR),
    ]
    print("\n>>> 运行构建脚本：")
    print("    " + " ".join(cmd))
    print()
    rc = subprocess.call(cmd, cwd=str(ROOT))
    if rc != 0:
        print("\n[FAIL] 构建失败（退出码 %d）。" % rc)
        return rc

    print("\n" + "=" * 68)
    print(" 构建完成")
    print("=" * 68)
    print("补丁包：", OUT_DIR / "browser_assets.patched")
    print("下一步：右键运行（或双击）")
    print("        WER_函数库\\安装包_双板通讯\\install_dual.cmd")
    print("        会弹 UAC，点「是」。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
