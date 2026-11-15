# -*- coding: utf-8 -*-
"""Step 3: disassemble libRobot.so functions with capstone, annotate PLT calls."""
import os, sys
from elftools.elf.elffile import ELFFile
from capstone import *

BASE = r"D:\UserData\Documents\WER\2026普级赛\_分析临时\brainApk分析\6F"
OUT  = r"D:\UserData\Documents\WER\2026普级赛\_分析临时\stm32分析"
PATH = os.path.join(BASE, "assets_program_c_libRobot.so")

with open(PATH, "rb") as f:
    data = f.read()
    f.seek(0)
    e = ELFFile(f)
    text = e.get_section_by_name(".text")
    tdata = text.data(); tbase = text["sh_addr"]
    # Build GOT slot -> symbol map from .rel.plt and .rel.dyn
    got2sym = {}
    for secname in (".rel.plt", ".rel.dyn"):
        sec = e.get_section_by_name(secname)
        if not sec: continue
        symtab = e.get_section(sec["sh_link"])
        for rel in sec.iter_relocations():
            off = rel["r_offset"]
            idx = rel["r_info_sym"]
            name = symtab.get_symbol(idx).name
            got2sym[off] = name or ("<sym%d>" % idx)
    # PLT: disassemble each 4-byte-aligned slot to find 'add r12, pc, #x' then 'ldr pc,[r12,#y]'
    plt = e.get_section_by_name(".plt")
    pdata = plt.data(); pbase = plt["sh_addr"]
    md_arm = Cs(CS_ARCH_ARM, CS_MODE_ARM)
    plt_map = {}   # plt_addr -> symname
    cur_r12 = None
    for ins in md_arm.disasm(pdata, pbase):
        if ins.mnemonic == "add" and ins.op_str.startswith("r12, pc"):
            # r12 = ins.address + 8 + imm
            try:
                imm = int(ins.op_str.split("#")[1], 0)
            except Exception:
                imm = 0
            cur_r12 = ins.address + 8 + imm
        elif ins.mnemonic == "ldr" and ins.op_str.startswith("pc, [r12"):
            off = 0
            if "#" in ins.op_str:
                try: off = int(ins.op_str.split("#")[1].rstrip("]"), 0)
                except Exception: off = 0
            if cur_r12 is not None:
                got = cur_r12 + off
                plt_map[ins.address - 8 if False else None] = None
                # PLT slot start = address of add instruction
                pass
    # redo: track slot starts explicitly
    slot_addr = None
    for ins in md_arm.disasm(pdata, pbase):
        if ins.mnemonic in ("add","ldr") :
            pass
    # simpler: PLT slot starts at pbase+? We record last 'add r12,pc' address as slot start
    slot_starts = {}
    last_add = None
    for ins in md_arm.disasm(pdata, pbase):
        if ins.mnemonic == "add" and ins.op_str.startswith("r12, pc"):
            try: imm = int(ins.op_str.split("#")[1], 0)
            except Exception: imm = 0
            last_add = (ins.address, ins.address + 8 + imm)
        elif ins.mnemonic == "ldr" and ins.op_str.startswith("pc, [r12") and last_add:
            off = 0
            if "#" in ins.op_str:
                try: off = int(ins.op_str.split("#")[1].rstrip("]"), 0)
                except Exception: off = 0
            got = last_add[1] + off
            sym = got2sym.get(got, "got_0x%x" % got)
            slot_starts[last_add[0]] = sym
    for a, s in sorted(slot_starts.items()):
        plt_map[a] = s
    # resolve any branch target into plt slots (thumb: target & ~1)
    def resolve_plt(t):
        t = t & ~1
        if t in plt_map: return plt_map[t]
        for a in sorted(plt_map):
            if a <= t < a + 0x10:
                return plt_map[a] + "(+%d)" % (t-a)
        return None

# functions to dump
FUNCS = sys.argv[1].split(",")
with open(PATH, "rb") as f:
    e = ELFFile(f)
    symtab = e.get_section_by_name(".symtab")
    syms = {s.name: s for s in symtab.iter_symbols() if s.name}
    text = e.get_section_by_name(".text")
    tdata = text.data(); tbase = text["sh_addr"]
    lines = []
    for fn in FUNCS:
        s = syms.get(fn)
        if not s:
            lines.append("!! symbol %s not found" % fn); continue
        addr = s["st_value"]; size = s["st_size"]
        is_thumb = bool(addr & 1)
        start = addr & ~1
        code = tdata[start - tbase: start - tbase + max(size, 4)]
        md = Cs(CS_ARCH_ARM, CS_MODE_THUMB if is_thumb else CS_MODE_ARM)
        md.detail = True
        lines.append("")
        lines.append("=" * 90)
        lines.append("FUNC %s  @0x%08x size=%d mode=%s" % (fn, start, size, "THUMB" if is_thumb else "ARM"))
        lines.append("=" * 90)
        for ins in md.disasm(code, start):
            note = ""
            if ins.mnemonic in ("bl", "blx", "b", "bx", "b.w", "bl.w") and ins.op_str.startswith("#"):
                try: t = int(ins.op_str[1:], 0)
                except Exception: t = -1
                pl = resolve_plt(t)
                if pl: note = "  ; -> %s" % pl
            lines.append("0x%08x:  %-8s %-40s%s" % (ins.address, ins.mnemonic, ins.op_str, note))
open(os.path.join(OUT, "03_disasm_libRobot.txt"), "w", encoding="utf-8").write("\n".join(lines))
print("wrote 03_disasm_libRobot.txt lines=%d" % len(lines))
