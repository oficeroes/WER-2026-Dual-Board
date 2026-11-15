# -*- coding: utf-8 -*-
"""Step 11b: STM32F103 app firmware @0x08004000: peripherals, USART init, protocol constants."""
import os, struct
from capstone import *
from capstone.arm import *

OUT = os.path.dirname(os.path.abspath(__file__))
BIN = os.path.join(os.path.dirname(OUT), "brainApk分析", "6F", "assets_stm32_stm32.bin")
data = open(BIN, "rb").read()
BASE = 0x08004000
print("size", len(data), "base", hex(BASE), "end", hex(BASE + len(data)))

vecs = [struct.unpack_from("<I", data, i)[0] for i in range(0, 0x130, 4)]
def valid(a):
    return (BASE <= a < BASE + len(data)) or (a >= 0x20000000)
lines = ["=== VECTOR TABLE @0x%08x ===" % BASE]
for i, v in enumerate(vecs):
    if v:
        lines.append("  [%2d] 0x%08x %s" % (i, v, "" if valid(v) else "<-- OUT OF RANGE"))

md = Cs(CS_ARCH_ARM, CS_MODE_THUMB)
md.detail = True
code_off = 0x144
insns = list(md.disasm(data[code_off:], BASE + code_off))
print("instructions:", len(insns))

lit = {}
for a in range(0, len(data) - 3, 4):
    lit[BASE + a] = struct.unpack_from("<I", data, a)[0]

PERIPH = {0x40013800: "USART1", 0x40004400: "USART2", 0x40004800: "USART3", 0x40004C00: "UART4",
          0x40005000: "UART5", 0x40010800: "GPIOA", 0x40010C00: "GPIOB", 0x40011000: "GPIOC",
          0x40011400: "GPIOD", 0x40011800: "GPIOE", 0x40012400: "ADC1", 0x40022000: "FLASH_R",
          0x40005400: "I2C1", 0x40005800: "I2C2", 0x40000000: "TIM2", 0x40010000: "AFIO",
          0x40021000: "RCC", 0x40020000: "DMA1", 0xE000E000: "SCB", 0xE000E100: "NVIC",
          0x40000400: "TIM3", 0x40000800: "TIM4", 0x40013000: "SPI1", 0x40002800: "RTC",
          0x40007000: "PWR", 0x40003000: "IWDG", 0x40003400: "WWDG", 0x40010400: "EXTI"}
regval = {}
lines.append("")
lines.append("=== PERIPHERAL CONSTANTS + REGISTER ACCESSES ===")
for ins in insns:
    m = ins.mnemonic
    ops = ins.operands
    if m == "ldr" and len(ops) == 2 and ops[1].type == ARM_OP_MEM and ops[1].mem.base == ARM_REG_PC:
        tgt = ins.address + 4 + ops[1].mem.disp
        if tgt in lit:
            val = lit[tgt]
            regval[ops[0].reg] = val
            if val in PERIPH:
                lines.append("0x%08x: ldr %-6s = 0x%08x %s" % (ins.address, ins.reg_name(ops[0].reg), val, PERIPH[val]))
    elif m in ("str", "ldr", "strb", "ldrb", "strh", "ldrh") and len(ops) >= 2:
        mem = None
        for o in ops:
            if o.type == ARM_OP_MEM:
                mem = o
        if mem is not None and mem.mem.base in regval:
            base = regval[mem.mem.base]
            if base in PERIPH:
                lines.append("0x%08x: %-8s %-32s ; %s+0x%x" % (ins.address, m, ins.op_str, PERIPH[base], mem.mem.disp))
open(os.path.join(OUT, "11_stm32_notes.txt"), "w", encoding="utf-8").write("\n".join(lines))
print("wrote 11_stm32_notes.txt lines", len(lines))

# full disasm
open(os.path.join(OUT, "11_stm32_full_disasm.txt"), "w", encoding="utf-8").write(
    "\n".join("0x%08x:  %-8s %s" % (i.address, i.mnemonic, i.op_str) for i in insns))

# constants scan
lines3 = ["=== immediate constants of interest ==="]
KEYS = {0xAA: "0xAA", 0x55: "0x55", 0xBB: "0xBB", 0x66: "0x66", 0x24: "0x24(BRR?)", 0x12: "0x12",
        0x45670123: "FLASH_KEY1", 0xCDEF89AB: "FLASH_KEY2", 0x80: "0x80", 0x31: "0x31", 0x9F: "0x9f"}
for ins in insns:
    for o in ins.operands:
        if o.type == ARM_OP_IMM and o.imm in KEYS:
            lines3.append("0x%08x: %-8s %-40s ; %s" % (ins.address, ins.mnemonic, ins.op_str, KEYS[o.imm]))
            break
# also scan raw words for flash keys (movw/movt often)
for a in range(0, len(data) - 3, 4):
    v = struct.unpack_from("<I", data, a)[0]
    if v in (0x45670123, 0xCDEF89AB):
        lines3.append("RAW LITERAL @0x%08x = 0x%08x" % (BASE + a, v))
open(os.path.join(OUT, "11_stm32_consts.txt"), "w", encoding="utf-8").write("\n".join(lines3))
print("done")
