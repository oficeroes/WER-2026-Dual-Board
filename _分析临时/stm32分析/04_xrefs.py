# -*- coding: utf-8 -*-
"""Step 4: find literal-pool xrefs to .rodata/.data addresses inside .text (Thumb/ARM)."""
import os, re
from elftools.elf.elffile import ELFFile
import struct

BASE = r"D:\UserData\Documents\WER\2026普级赛\_分析临时\brainApk分析\6F"
OUT  = r"D:\UserData\Documents\WER\2026普级赛\_分析临时\stm32分析"
PATH = os.path.join(BASE, "assets_program_c_libRobot.so")

with open(PATH, "rb") as f:
    e = ELFFile(f)
    text = e.get_section_by_name(".text"); tdata = text.data(); tbase = text["sh_addr"]
    # strings
    strs = {}
    for secname in (".rodata", ".data"):
        sec = e.get_section_by_name(secname)
        if not sec: continue
        d = sec.data(); b = sec["sh_addr"]
        for m in re.finditer(rb"[\x20-\x7e]{3,}", d):
            strs[b + m.start()] = m.group().decode("ascii")
    # symbol addrs too
    symtab = e.get_section_by_name(".symtab")
    syms = sorted([(s["st_value"], s.name) for s in symtab.iter_symbols() if s.name and s["st_value"]])
    symmap = dict(syms)

    # scan text for 4-byte LE values in rodata/data range
    lo = min(strs); hi = max(strs) + 64
    xrefs = {}
    for off in range(0, len(tdata) - 3):
        v = struct.unpack_from("<I", tdata, off)[0]
        if lo <= v < hi:
            if v in strs or v in symmap or True:
                xrefs.setdefault(v, []).append(tbase + off)
    lines = ["=== LITERAL XREFS from .text to rodata/data ==="]
    for v in sorted(xrefs):
        label = strs.get(v) or symmap.get(v) or "?"
        lines.append("0x%08x  %-40s  <- %s" % (v, repr(label)[:60], ", ".join("0x%x" % a for a in xrefs[v][:8])))
    open(os.path.join(OUT, "04_xrefs.txt"), "w", encoding="utf-8").write("\n".join(lines))
    print("wrote 04_xrefs.txt n=%d" % len(xrefs))
