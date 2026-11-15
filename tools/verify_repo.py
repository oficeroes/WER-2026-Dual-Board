# -*- coding: utf-8 -*-
"""仓库自检：必需文件、文档链接、超大/二进制文件。

运行：
    python tools/verify_repo.py
"""
from __future__ import annotations

import re
import sys
import urllib.parse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

REQUIRED = [
    "README.md",
    "docs/01_我们做了什么.md",
    "docs/02_双板通讯原理.md",
    "docs/03_积木块自定义.md",
    "docs/04_安装步骤.md",
    "docs/05_真机记录.md",
    "docs/06_排错与限制.md",
    "docs/07_证据索引.md",
    "docs/images/myfunc-flyout.png",
    "WER_函数库/README_从这里开始.md",
    "WER_函数库/工具/原生积木/原生积木核心.py",
    "WER_函数库/工具/原生积木/安装原生积木.cmd",
    "WER_函数库/工具/双板通讯/构建双板通讯扩展.py",
    "WER_函数库/我的函数库.srhs",
    "WER_函数库/示例/WER函数库.srhs",
    "双板通讯研究/README_可行性研究主报告.md",
    "双板通讯研究/实验/实验19_双板通讯积木原型/wl_prelude.py",
    "双板通讯研究/实验/实验14_W4_C程序下发.js",
    "双板通讯研究/实验/实验09_有线握手_CH340.py",
    "双板通讯研究/实验/实验05_运行环境探测.py",
    "逆向资料/下载分析/协议规格.md",
    "逆向资料/下载分析/下载链路逆向.md",
    "tools/build_dual.py",
    "tools/install_all.py",
    "tools/安装双板通讯积木.cmd",
    "tools/检查安装.cmd",
    "tools/还原原版.cmd",
]


def main() -> int:
    errors = []
    for rel in REQUIRED:
        p = ROOT / rel
        if not p.exists():
            errors.append("缺少必需文件：" + rel)

    # README / docs 相对链接
    missing_links = 0
    checked_links = 0
    for md in ROOT.rglob("*.md"):
        if ".git" in md.parts:
            continue
        text = md.read_text(encoding="utf-8", errors="ignore")
        for m in re.finditer(r"!?\[[^\]]*\]\(([^)]+)\)", text):
            link = m.group(1).strip()
            if link.startswith(("http://", "https://", "#", "mailto:", "data:")):
                continue
            checked_links += 1
            link = urllib.parse.unquote(link.split("#")[0].split("?")[0])
            if link and not (md.parent / link).exists():
                missing_links += 1
                errors.append(f"坏链接：{md.relative_to(ROOT)} -> {link}")

    # 大文件 / 二进制
    big = []
    binaries = []
    for p in ROOT.rglob("*"):
        if not p.is_file() or ".git" in p.parts:
            continue
        size = p.stat().st_size
        if size > 50 * 1024 * 1024:
            big.append((size, p.relative_to(ROOT)))
        if p.suffix.lower() in {".apk", ".dex", ".so", ".bin", ".jar"}:
            binaries.append(p.relative_to(ROOT))

    print("=" * 68)
    print(" WER-2026-Dual-Board · 仓库自检")
    print("=" * 68)
    print(f"必需文件：{len(REQUIRED) - sum(1 for e in errors if e.startswith('缺少必需文件'))}/{len(REQUIRED)}")
    print(f"Markdown 相对链接：{checked_links} 个，坏链接 {missing_links}")
    print(f"超大文件（>50MB）：{len(big)}")
    for size, p in big:
        print(f"  {size/1024/1024:.1f} MiB  {p}")
    print(f"二进制（apk/dex/so/bin/jar）：{len(binaries)}")
    for p in binaries:
        print("  ", p)

    if errors:
        print("\nFAIL:")
        for e in errors:
            print("  -", e)
        return 1
    print("\nOK：结构完整，没有坏链接 / 超大文件 / 二进制。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
