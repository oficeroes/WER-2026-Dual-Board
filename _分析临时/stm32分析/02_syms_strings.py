# -*- coding: utf-8 -*-
"""Step 2: dump strings (.rodata/.data) with vaddr, all FUNC syms sorted by addr, and debug_str."""
import os, re
from elftools.elf.elffile import ELFFile

BASE = r"D:\UserData\Documents\WER\2026普级赛\_分析临时\brainApk分析\6F"
OUT  = r"D:\UserData\Documents\WER\2026普级赛\_分析临时\stm32分析"
PATH = os.path.join(BASE, "assets_program_c_libRobot.so")

lines = []
with open(PATH, "rb") as f:
    e = ELFFile(f)
    # all local + global func symbols, sorted
    funcs = []
    for secname in (".symtab", ".dynsym"):
        s = e.get_section_by_name(secname)
        if not s:
            continue
        for sym in s.iter_symbols():
            if sym["st_info"]["type"] in ("STT_FUNC", "STT_OBJECT") and sym["st_value"]:
                funcs.append((sym["st_value"], sym.name, sym["st_size"], sym["st_info"]["type"], secname, sym["st_shndx"]))
    # dedupe by (value,name)
    seen = set(); uniq = []
    for x in funcs:
        key = (x[0], x[1])
        if key in seen: continue
        seen.add(key); uniq.append(x)
    uniq.sort()
    lines.append("=== ALL SYMBOLS (FUNC/OBJECT) sorted by addr, n=%d ===" % len(uniq))
    for v, n, size, t, sec, shndx in uniq:
        lines.append("0x%08x %-42s size=%-6d %s %s %s" % (v, n, size, t, sec, shndx))

    # rodata strings with addresses
    for secname in (".rodata", ".data"):
        sec = e.get_section_by_name(secname)
        if not sec: continue
        data = sec.data(); base = sec["sh_addr"]
        lines.append("")
        lines.append("=== STRINGS in %s (addr 0x%x, size 0x%x) ===" % (secname, base, len(data)))
        for m in re.finditer(rb"[\x20-\x7e]{3,}", data):
            lines.append("0x%08x  %s" % (base + m.start(), m.group().decode("ascii")))
    # whole-file strings for debug_str
    sec = e.get_section_by_name(".debug_str")
    if sec:
        data = sec.data()
        lines.append("")
        lines.append("=== .debug_str strings ===")
        for m in re.finditer(rb"[\x20-\x7e]{3,}", data):
            lines.append(m.group().decode("ascii"))

open(os.path.join(OUT, "02_syms_strings.txt"), "w", encoding="utf-8").write("\n".join(lines))
print("wrote 02_syms_strings.txt lines=%d" % len(lines))
