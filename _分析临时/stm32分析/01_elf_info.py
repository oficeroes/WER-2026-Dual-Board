# -*- coding: utf-8 -*-
"""Step 1: parse libRobot.so / libserial.so ELF headers, sections, symbols."""
import sys, os, json
from elftools.elf.elffile import ELFFile

BASE = r"D:\UserData\Documents\WER\2026普级赛\_分析临时\brainApk分析\6F"
OUT  = r"D:\UserData\Documents\WER\2026普级赛\_分析临时\stm32分析"
FILES = {
    "libRobot": os.path.join(BASE, "assets_program_c_libRobot.so"),
    "libRobot_v7a": os.path.join(BASE, "lib_armeabi-v7a_libRobot.so"),
    "libserial": os.path.join(BASE, "lib_armeabi-v7a_libserial.so"),
}

lines = []
for tag, path in FILES.items():
    lines.append("=" * 100)
    lines.append("FILE %s  %s  size=%d" % (tag, path, os.path.getsize(path)))
    with open(path, "rb") as f:
        e = ELFFile(f)
        lines.append("ELF: class=%s machine=%s type=%s entry=0x%x" % (
            e.elfclass, e.get_machine_arch(), e.header.e_type, e.header.e_entry))
        lines.append("SECTIONS:")
        for sec in e.iter_sections():
            lines.append("  [%2d] %-18s type=%-14s addr=0x%08x off=0x%05x size=0x%05x flags=%s" % (
                sec["sh_name"], sec.name, sec["sh_type"], sec["sh_addr"],
                sec["sh_offset"], sec["sh_size"], sec["sh_flags"]))
        # dynamic symbols
        try:
            dyn = e.get_section_by_name(".dynsym")
            syms = list(dyn.iter_symbols())
            lines.append("DYNSYM count=%d" % len(syms))
            for s in syms:
                if s.name:
                    lines.append("  %-50s val=0x%08x size=%-6d type=%s bind=%s shndx=%s" % (
                        s.name, s["st_value"], s["st_size"], s["st_info"]["type"],
                        s["st_info"]["bind"], s["st_shndx"]))
        except Exception as ex:
            lines.append("dynsym err %s" % ex)
        try:
            symtab = e.get_section_by_name(".symtab")
            if symtab:
                syms = list(symtab.iter_symbols())
                lines.append("SYMTAB count=%d" % len(syms))
                for s in syms:
                    if s.name and s["st_value"]:
                        lines.append("  %-50s val=0x%08x size=%-6d type=%s" % (
                            s.name, s["st_value"], s["st_size"], s["st_info"]["type"]))
            else:
                lines.append("NO .symtab (stripped)")
        except Exception as ex:
            lines.append("symtab err %s" % ex)

open(os.path.join(OUT, "01_elf_info.txt"), "w", encoding="utf-8").write("\n".join(lines))
print("wrote 01_elf_info.txt lines=%d" % len(lines))
