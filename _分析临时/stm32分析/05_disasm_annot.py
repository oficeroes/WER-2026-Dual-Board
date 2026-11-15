# -*- coding: utf-8 -*-
"""Step 5: disassemble libRobot.so with PIC/GOT annotation (strings + libc calls)."""
import os, sys, re, struct
from elftools.elf.elffile import ELFFile
from capstone import *

BASE = r"D:\UserData\Documents\WER\2026普级赛\_分析临时\brainApk分析\6F"
OUT  = r"D:\UserData\Documents\WER\2026普级赛\_分析临时\stm32分析"
PATH = os.path.join(BASE, "assets_program_c_libRobot.so")

with open(PATH, "rb") as f:
    e = ELFFile(f)
    text = e.get_section_by_name(".text"); tdata = text.data(); tbase = text["sh_addr"]
    got = e.get_section_by_name(".got"); gdata = got.data(); gbase = got["sh_addr"]
    dynsym = e.get_section_by_name(".dynsym"); symtab = e.get_section_by_name(".symtab")
    # strings
    strs = {}
    sec_ranges = []
    for secname in (".rodata", ".data"):
        sec = e.get_section_by_name(secname)
        if not sec: continue
        d = sec.data(); b = sec["sh_addr"]; sec_ranges.append((b, b+len(d)))
        for m in re.finditer(rb"[\x20-\x7e]{2,}", d):
            strs[b + m.start()] = m.group().decode("ascii")
    # got slot -> addend/string
    gotstr = {}
    for secname in (".rel.plt", ".rel.dyn"):
        sec = e.get_section_by_name(secname)
        if not sec: continue
        for rel in sec.iter_relocations():
            off = rel["r_offset"]; idx = rel["r_info_sym"]
            name = None
            if idx:
                name = dynsym.get_symbol(idx).name
            if name:
                gotstr[off] = "IMP:" + name
            else:
                # RELATIVE: addend stored in place (file content)
                if gbase <= off < gbase + len(gdata):
                    val = struct.unpack_from("<I", gdata, off - gbase)[0]
                    if val in strs:
                        gotstr[off] = "STR:%r" % strs[val]
                    elif any(lo <= val < hi for lo, hi in sec_ranges):
                        gotstr[off] = "RO:0x%x" % val
                    else:
                        gotstr[off] = "GOT_ADDEND:0x%x" % val
                else:
                    gotstr[off] = "RELOC(0x%x)" % off
    syms = {}
    for s in symtab.iter_symbols():
        if s.name and s["st_info"]["type"] == "STT_FUNC" and s["st_value"]:
            syms[s["st_value"] & ~1] = s.name
    # address->symbol sorted for lookup
    sym_list = sorted(syms.items())
    def sym_at(a):
        for v, n in sym_list:
            if v == a: return n
        return None

    def lit_target(ins_list, i, reg):
        """Detect ldr reg,[pc,#imm] ... add reg,pc then return got slot."""
        pass

    def dumprange(start, size, tag):
        entry = {"b": start, "t": "T" if (start & 1) else "A"}
        start &= ~1
        if not (tbase <= start < tbase + len(tdata)):
            return ["!! %s 0x%x out of text" % (tag, start)]
        code = tdata[start-tbase: start-tbase+size]
        md = Cs(CS_ARCH_ARM, CS_MODE_THUMB if entry["t"] == "T" else CS_MODE_ARM)
        md.detail = False
        out = []
        insns = list(md.disasm(code, start))
        for i, ins in enumerate(insns):
            note = ""
            # direct branch
            if ins.mnemonic in ("bl", "blx", "b", "b.w", "bl.w") and ins.op_str.startswith("#"):
                try: t = int(ins.op_str[1:], 0)
                except Exception: t = -1
                pl = gotstr.get(t)
                nm = sym_at(t) if t >= 0 else None
                if t >= 0:
                    note = "  ; -> %s" % (nm or ("PLT/0x%x" % t))
            # ldr reg, [pc, #imm]
            elif ins.mnemonic == "ldr" and "[pc" in ins.op_str:
                parts = ins.op_str.split(",")
                reg = parts[0].strip()
                imm = 0
                try: imm = int(parts[-1].split("#")[1].rstrip("]"), 0)
                except Exception: pass
                base = (ins.address + 4) & ~3
                lit = base + imm
                if tbase <= lit < tbase + len(tdata) - 3:
                    val = struct.unpack_from("<I", tdata, lit - tbase)[0]
                    note = "  ; lit@0x%x=0x%08x" % (lit, val)
                    # check add reg,pc next
                    if i + 1 < len(insns) and insns[i+1].mnemonic == "add" and insns[i+1].op_str == ("%s, pc" % reg):
                        tgt = val + insns[i+1].address + 4
                        g = gotstr.get(tgt, "")
                        note += " add->0x%x %s" % (tgt, g)
                    if val in strs:
                        note += " STR=%r" % strs[val]
            out.append("0x%08x:  %-8s %-42s%s" % (ins.address, ins.mnemonic, ins.op_str, note))
        return out

    FUNCS = sys.argv[1].split(",") if len(sys.argv) > 1 else ["CCJ_Interface"]
    lines = []
    for fn in FUNCS:
        s = None
        for secname in (".symtab", ".dynsym"):
            tb = e.get_section_by_name(secname)
            for sym in tb.iter_symbols():
                if sym.name == fn and sym["st_value"]:
                    s = sym; break
            if s: break
        if not s:
            lines.append("!! symbol %s not found" % fn); continue
        addr = s["st_value"]; size = s["st_size"] or 4
        lines.append("")
        lines.append("=" * 95)
        lines.append("FUNC %s @0x%08x size=%d" % (fn, addr & ~1, size))
        lines.append("=" * 95)
        lines.extend(dumprange(addr, size, fn))
    open(os.path.join(OUT, "05_disasm_annot.txt"), "w", encoding="utf-8").write("\n".join(lines))
    print("wrote 05_disasm_annot.txt lines=%d" % len(lines))
