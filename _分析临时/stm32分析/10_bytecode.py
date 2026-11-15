# -*- coding: utf-8 -*-
"""Step 10: full bytecode + static-values dump for key classes."""
import sys, zipfile, os, traceback
try:
    from loguru import logger
    logger.remove()
except Exception:
    pass
from androguard.core.dex import DEX

APK = r"D:\Program Files\AbilixScratch3.0\AbilixScratch3.0_Data\StreamingAssets\standalonewindows\hot_update_dir\extenddatas\brainApk\6F\Controller_43.apk"
OUT = os.path.dirname(os.path.abspath(__file__))

TARGETS = [
    "com/abilix/controller/api/Protocol",
    "com/abilix/controller/api/Protocol$MasterUART",
    "com/abilix/controller/api/Protocol$TransUART",
    "com/abilix/controller/api/serial/BaseSerial",
    "com/abilix/controller/api/serial/MasterSerial",
    "com/abilix/controller/api/serial/TransSerial",
    "com/abilix/controller/api/serial/TransSerial$1",
    "com/abilix/controller/api/serial/OnSerialListener",
    "com/abilix/utils/SerialPort",
    "com/abilix/controller/conn/Datagram",
    "com/abilix/controller/api/Sensor",
    "com/abilix/controller/api/Sensor$AiType",
    "com/abilix/controller/api/Sensor$AIObj",
    "com/abilix/controller/bean/SensorData",
    "com/abilix/controller/api/ControllerApi",
    "com/abilix/controller/api/ControllerApi$TTLCmdType",
    "com/abilix/controller/api/ControllerApi$ControllerState",
]

with zipfile.ZipFile(APK) as z:
    dexes = [(n, DEX(z.read(n))) for n in ("classes.dex", "classes2.dex")]
bymap = {}
for n, d in dexes:
    for c in d.get_classes():
        bymap[c.get_name()[1:-1]] = c

# probe one method
probe = bymap["com/abilix/controller/api/serial/MasterSerial"]
pm = [m for m in probe.get_methods() if m.get_name() == "sendProtocol"][0]
code = pm.get_code()
bc = code.get_bc()
print("bc type", type(bc), [a for a in dir(bc) if not a.startswith("_")][:20])
try:
    ins = list(bc.get_instructions())
    print("instructions via bc.get_instructions:", len(ins), ins[0].get_name(), ins[0].get_output())
except Exception as ex:
    print("bc.get_instructions fail:", ex)
    try:
        ins = list(pm.get_instructions())
        print("instructions via method.get_instructions:", len(ins), ins[0].get_name(), ins[0].get_output())
    except Exception as ex2:
        print("method.get_instructions fail:", ex2)

lines = []
for t in TARGETS:
    c = bymap.get(t)
    if c is None:
        lines.append("!! class not found: %s" % t); continue
    lines.append("")
    lines.append("=" * 100)
    lines.append("CLASS %s  super=%s" % (t, c.get_superclassname()))
    lines.append("=" * 100)
    try:
        sv = c.get_static_values()
        lines.append("STATIC VALUES: %r" % (sv,))
    except Exception as ex:
        lines.append("static values fail: %r" % (ex,))
    for f in c.get_fields():
        lines.append("  FIELD %-28s %s flags=0x%x" % (f.get_name(), f.get_descriptor(), f.get_access_flags()))
    for m in c.get_methods():
        lines.append("")
        lines.append("---- METHOD %s %s access=0x%x ----" % (m.get_name(), m.get_descriptor(), m.get_access_flags()))
        try:
            code = m.get_code()
            if code is None:
                lines.append("   (no code)")
                continue
            insns = list(m.get_instructions())
            for i, ins in enumerate(insns):
                lines.append("   %4d  %-22s %s" % (i, ins.get_name(), ins.get_output()))
        except Exception as ex:
            lines.append("   !! disasm error: %r" % (ex,))
open(os.path.join(OUT, "10_keyclass_bytecode.txt"), "w", encoding="utf-8").write("\n".join(lines))
print("wrote 10_keyclass_bytecode.txt lines", len(lines))
