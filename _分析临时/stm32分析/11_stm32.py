# -*- coding: utf-8 -*-
"""Step 11: STM32F103 firmware analysis: vector table, peripheral refs, frame constants."""
import os, struct
from capstone import *
from capstone.arm import *

OUT = os.path.dirname(os.path.abspath(__file__))
BIN = os.path.join(os.path.dirname(OUT), "brainApk分析", "6F", "assets_stm32_stm32.bin")
data = open(BIN, "rb").read()
BASE = 0x08000000
print("size", len(data), "first words:", ["0x%08x" % struct.unpack_from("<I", data, i)[0] for i in range(0, 16, 4)])

# vector table
vecs = [struct.unpack_from("<I", data, i)[0] for i in range(0, min(len(data), 0x200), 4)]
lines = ["=== VECTOR TABLE (index: value) ==="]
names = {0: "initial_sp", 1: "Reset", 2: "NMI", 3: "HardFault", 4: "MemManage", 5: "BusFault",
         6: "UsageFault", 11: "SVCall", 12: "DebugMon", 14: "PendSV", 15: "SysTick"}
for i, v in enumerate(vecs):
    if v == 0:
        continue
    nm = names.get(i, "IRQ%d" % (i - 16))
    lines.append("  [%3d] %-10s 0x%08x" % (i, nm, v))

# disassemble whole image from reset
md = Cs(CS_ARCH_ARM, CS_MODE_THUMB)
md.detail = True
code_off = 0x144
code = data[code_off:]
insns = list(md.disasm(code, BASE + code_off))
print("instructions:", len(insns))

# literals: map vaddr->value for 4-byte aligned words
lit = {}
for a in range(0, len(data) - 3, 4):
    v = struct.unpack_from("<I", data, a)[0]
    lit[BASE + a] = v

PERIPH = {
    0x40013800: "USART1", 0x40004400: "USART2", 0x40004800: "USART3", 0x40004C00: "UART4",
    0x40005000: "UART5", 0x40010800: "GPIOA", 0x40010C00: "GPIOB", 0x40011000: "GPIOC",
    0x40011400: "GPIOD", 0x40011800: "GPIOE", 0x40012400: "ADC1", 0x40022000: "FLASH_R",
    0x40005400: "I2C1", 0x40005800: "I2C2", 0x40000000: "TIM2", 0x40010000: "AFIO",
    0x40021000: "RCC", 0x40020000: "DMA1", 0xE000E000: "SCB", 0xE000E100: "NVIC",
    0x40006C00: "TIM?", 0x40000400: "TIM3", 0x40000800: "TIM4", 0x40013000: "SPI1",
}
# annotate: track register->literal value & then register+imm accesses
lines.append("")
lines.append("=== PERIPHERAL / NOTABLE LITERAL ACCESSES (approx dataflow) ===")
regval = {}
FUNC_START = BASE + code_off
for ins in insns:
    m = ins.mnemonic
    ops = ins.operands
    # ldr rX, [pc, #imm]
    if m == "ldr" and len(ops) == 2 and ops[1].type == ARM_OP_MEM and ops[1].mem.base == ARM_REG_PC:
        tgt = ins.address + 4 + ops[1].mem.disp
        if tgt in lit:
            val = lit[tgt]
            regval[ops[0].reg] = val
            if val in PERIPH or 0x40000000 <= val < 0x40030000 or val >= 0xE0000000:
                lines.append("0x%08x: ldr %-6s = 0x%08x %s" % (ins.address, ins.reg_name(ops[0].reg), val,
                                                                PERIPH.get(val, "")))
    # add rX, rY, #imm or add rX,pc
    elif m in ("add", "adds", "add.w") and len(ops) == 3 and ops[2].type == ARM_OP_IMM:
        pass
    # str/ldr with base register we know
    elif m in ("str", "ldr", "strb", "ldrb", "strh", "ldrh", "str.w", "ldr.w") and len(ops) >= 2:
        mem = None
        for o in ops:
            if o.type == ARM_OP_MEM:
                mem = o
        if mem is not None and mem.base in regval:
            base = regval[mem.base]
            disp = mem.disp
            if base in PERIPH:
                val = ops[0].reg if m.startswith("str") else None
                lines.append("0x%08x: %-8s %-30s ; %s+0x%x" % (ins.address, m, ins.op_str, PERIPH[base], disp))

open(os.path.join(OUT, "11_stm32_disasm_notes.txt"), "w", encoding="utf-8").write("\n".join(lines))
print("wrote 11_stm32_disasm_notes.txt lines", len(lines))

# full disasm to file for reference
lines2 = []
for ins in insns:
    lines2.append("0x%08x:  %-8s %s" % (ins.address, ins.mnemonic, ins.op_str))
open(os.path.join(OUT, "11_stm32_full_disasm.txt"), "w", encoding="utf-8").write("\n".join(lines2))

# search interesting constants in code bytes
lines3 = ["=== 16-bit immediate constants scan (cmp/sub/add with 0xAA/0x55/0xBB/0x66/0x24/0x12) ==="]
for ins in insns:
    if len(ins.operands) >= 2 and ins.operands[-1].type == ARM_OP_IMM:
        v = ins.operands[-1].imm
        if v in (0xAA, 0x55, 0xBB, 0x66, 0x24, 0x12, 0x1C, 0x0E, 0x04, 0x08):
            lines3.append("0x%08x: %-8s %s" % (ins.address, ins.mnemonic, ins.op_str))
open(os.path.join(OUT, "11_stm32_consts.txt"), "w", encoding="utf-8").write("\n".join(lines3))
print("done")
