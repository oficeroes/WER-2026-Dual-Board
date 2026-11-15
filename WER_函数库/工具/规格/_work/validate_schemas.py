# -*- coding: utf-8 -*-
"""校验 block_schemas.json 的完整性与行号/XML 合法性。"""
import json
import os
import xml.etree.ElementTree as ET

ROOT = r"D:\UserData\Documents\WER\2026普级赛"
HERE = os.path.join(ROOT, "WER_函数库", "工具", "规格")
SRC = os.path.join(ROOT, "_分析临时", "blockly_utf8")
d = json.load(open(os.path.join(HERE, "block_schemas.json"), encoding="utf-8"))
B = d["blocks"]
req = ["type", "block_def", "append_fields", "fields", "inputs", "connection",
       "generator", "python", "evidence", "xml_min"]
problems = []
line_cache = {}


def lines_of(rel):
    if rel not in line_cache:
        line_cache[rel] = open(os.path.join(SRC, rel), "rb").read().decode("utf-8", "replace").count("\n") + 1
    return line_cache[rel]


for t, b in B.items():
    for k in req:
        if k not in b:
            problems.append((t, "missing key " + k))
    bd = b.get("block_def") or {}
    for k in ("file", "start_line", "end_line"):
        if k not in bd:
            problems.append((t, "block_def missing " + k))
            break
    else:
        n = lines_of(bd["file"]) if os.path.exists(os.path.join(SRC, bd["file"])) else None
        if n is None:
            problems.append((t, "block_def file not found"))
        elif not (1 <= bd["start_line"] < bd["end_line"] <= n + 1):
            problems.append((t, "block_def line range invalid %r/%r" % (bd["start_line"], bd["end_line"])))
    g = b.get("generator") or {}
    if "file" in g:
        n = lines_of(g["file"]) if os.path.exists(os.path.join(SRC, g["file"])) else None
        if n is None:
            problems.append((t, "generator file not found"))
        elif not (1 <= g["start_line"] < g["end_line"] <= n + 1):
            problems.append((t, "generator line range invalid %r/%r" % (g["start_line"], g["end_line"])))
    try:
        ET.fromstring('<xml xmlns="http://www.w3.org/1999/xhtml">' + b["xml_min"] + "</xml>")
    except Exception as e:
        problems.append((t, "xml_min invalid: %r" % (e,)))
    if "xml_real" in b:
        try:
            ET.fromstring('<xml xmlns="http://www.w3.org/1999/xhtml">' + b["xml_real"]["xml"] + "</xml>")
        except Exception as e:
            problems.append((t, "xml_real invalid: %r" % (e,)))
    # append_fields 第一个字段/输入应出现在 fields/inputs 中
    fields = set(b.get("fields") or {})
    for seg in b.get("append_fields") or []:
        if seg.get("kind", "").startswith("field_") and seg.get("field") and seg["field"] not in fields:
            problems.append((t, "append field %s not in fields" % seg["field"]))
        if seg.get("kind") == "input_value" and seg.get("name") not in (b["inputs"]["value"] if "value" in b["inputs"] else {}):
            problems.append((t, "input_value %s not in inputs" % seg.get("name")))
        if seg.get("kind") == "input_statement" and seg.get("name") not in (b["inputs"]["statement"] if "statement" in b["inputs"] else {}):
            problems.append((t, "input_statement %s not in inputs" % seg.get("name")))

print("block_schemas.json blocks:", len(B))
print("problem count:", len(problems))
for p in problems[:40]:
    print("  ", p)
