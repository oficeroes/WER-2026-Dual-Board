# -*- coding: utf-8 -*-
"""
patch_browser_assets.py —— 「新建项目默认自带函数库」补丁脚本（管理员运行）
============================================================================

目标
----
让 AbilixScratch3.0 **新建项目**时，工作区自带 WER 函数库（函数定义 + 变量声明 + start 示例块），
用户一打开积木编程就能在「函数」分类里直接拖用。

原理（已由 C# 反编译源码 + 真实资源包实证）
--------------------------------------------
* 新建项目流程：C# `CreateNewProject` → JS `maingui.createProject()` → `workspace.clear()`
  → `maingui.importDefaultCode()`：
      var xml_text = maingui_init.getDefaultCode();          // = maingui_init.js 里的 defaultcode 字符串
      var xml_now  = Blockly.Xml.domToText(Blockly.Xml.workspaceToDom(workspace));
      var xml = Blockly.Xml.textToDom(xml_text + xml_now);   // 浏览器解析器容错：只取第一个 <xml> 根
      Blockly.Xml.domToWorkspace(xml, workspace);
  → 只要把「函数库片段」塞进 `maingui_init.js` 的 `var defaultcode = '...'`，新项目就会自带。
* Web 资源包 `browser_assets` 是自定义 `zfbRes_v1` 格式（C# 类 `StandaloneWebResources`）：
      BinaryWriter.Write("zfbRes_v1")           // .NET 7-bit 长度前缀 + UTF-8
      WriteInt32(count)
      每个条目: Write(name) + WriteInt64(offset) + WriteInt32(length)   // offset 为文件绝对偏移
      数据区：按索引顺序连续存放（无压缩、无对齐填充）
  → 本脚本按完全相同布局重新打包，可做到**除 maingui_init.js 外逐字节一致**。

本脚本做什么
------------
1. 校验原 `browser_assets` 格式；
2. **纯 roundtrip 自检**：解包→重新打包（不改任何内容）→ 与原文件逐字节比较（必须完全一致）；
3. 生成 defaultcode 片段：从 `WER函数库.srh`（或现成片段文件）抽取
   `<xml>` 根 + `<variables>` + 全部顶层 block（必须含 start 块）；
4. 解包 → 只改动 `Blockly_Code/maingui_init.js` 的 defaultcode 字符串（默认只改简中）→ 重新打包；
5. **打包后自检**：解包新包，逐条目 sha256 比较，要求除 `Blockly_Code/maingui_init.js`
   外全部与旧包一致（6644 个其它条目 sha256 完全不变）；
6. `--install` 时：检查管理员/写权限 → 把原文件备份为 `browser_assets.备份-<时间戳>` →
   写回安装目录 → 再校验最终文件 sha256。

⚠ 重要风险（详见同目录 `说明.md`）
--------------------------------
* 写回安装目录需要**管理员权限**（本机普通用户对安装目录只读）；
* **升级/重装软件会覆盖补丁**，升级后需要重新运行本脚本；
* 还原：运行 `还原默认模板.py --apply`（管理员）即可从 `<browser_assets>.备份-<时间戳>` 恢复；
* 本脚本只改 `Blockly_Code/maingui_init.js` 一个条目，其余 6644 个条目内容**逐字节不变**（自检强制校验）；
* 建议先关闭 IDE 再打补丁。

用法
----
    # 1) 只在副本上演练（推荐先做，不碰安装目录）
    python patch_browser_assets.py --assets _分析临时\\integration_work\\zfb_test\\browser_assets ^
        --library ..\\..\\WER函数库.srh --out _分析临时\\integration_work\\zfb_test\\browser_assets.patched

    # 2) 管理员真正安装（或用同目录 .cmd 一键管理员运行）
    python patch_browser_assets.py --install --library WER函数库.srh

    # 3) 只验证两个包之间的差异（用于复核）
    python patch_browser_assets.py --verify-only 原文件 新文件

作者：集成工具工程师（integration）。依赖：仅 Python 标准库 + 同目录上一级 `srhs工具.py`。
"""

from __future__ import annotations

import argparse
import ctypes
import importlib.util
import json
import os
import re
import shutil
import struct
import sys
import tempfile
import time
import xml.etree.ElementTree as ET
from typing import Any, Dict, List, Optional, Sequence, Tuple

_HERE = os.path.dirname(os.path.abspath(__file__))


def _load_srhs_tool():
    # 本脚本在 WER_函数库/工具/新建默认模板_可选/ 下，srhs工具.py 在上一级
    candidates = [
        os.path.join(os.path.dirname(_HERE), 'srhs工具.py'),
        os.path.join(_HERE, 'srhs工具.py'),
    ]
    for path in candidates:
        if os.path.isfile(path):
            spec = importlib.util.spec_from_file_location('srhs_tool', path)
            mod = importlib.util.module_from_spec(spec)
            assert spec.loader is not None
            spec.loader.exec_module(mod)
            return mod
    raise RuntimeError('找不到 srhs工具.py（应在 %s）' % candidates[0])


srhs_tool = _load_srhs_tool()

# ----------------------------------------------------------------------------
# 常量
# ----------------------------------------------------------------------------
ZFB_MAGIC = 'zfbRes_v1'
DEFAULT_ASSETS = r'D:\Program Files\AbilixScratch3.0\AbilixScratch3.0_Data\Resources\browser_assets'
MAINGUI_INIT_NAME = 'Blockly_Code/maingui_init.js'          # 索引里的条目名（带前导 '/'）
MAINGUI_INIT_KEY = '/' + MAINGUI_INIT_NAME
DEFAULT_LANGS = 'zh-hans'

#: defaultcode 变量名 <-> 语言
DEFAULTCODE_VARS = {
    'zh-hans': 'defaultcode',
    'zh-hant': 'defaultcodeTr',
    'en': 'defaultcodeEn',
}
DEFAULTCODE_RE = re.compile(r'^var\s+(defaultcode|defaultcodeTr|defaultcodeEn)\s*=\s*$')
BACKUP_PREFIX = 'browser_assets.备份-'


# ============================================================================
# 一、zfbRes_v1 二进制格式：读索引 / 读写
# ============================================================================

def _encode_string(text: str) -> bytes:
    """复刻 .NET BinaryWriter.Write(string)：7-bit 编码长度前缀 + UTF-8 字节。"""
    raw = text.encode('utf-8')
    n = len(raw)
    prefix = bytearray()
    while True:
        b = n & 0x7F
        n >>= 7
        if n:
            prefix.append(b | 0x80)
        else:
            prefix.append(b)
            break
    return bytes(prefix) + raw


def _decode_string(buf, pos: int) -> Tuple[str, int]:
    length = 0
    shift = 0
    while True:
        if pos >= len(buf):
            raise ValueError('索引越界（读取字符串长度时到达文件尾）')
        b = buf[pos]
        pos += 1
        length |= (b & 0x7F) << shift
        if not (b & 0x80):
            break
        shift += 7
        if shift > 63:
            raise ValueError('字符串长度前缀异常（7-bit 编码过长）')
    if pos + length > len(buf):
        raise ValueError('字符串内容越界（长度 %d 超出文件）' % length)
    try:
        text = buf[pos:pos + length].decode('utf-8')
    except UnicodeDecodeError as exc:
        raise ValueError('条目名不是 UTF-8：%s' % exc)
    return text, pos + length


def read_zfb_index(path: str, with_data: bool = False) -> Dict[str, Any]:
    """
    读取 browser_assets 的索引。返回：
        {'path','magic','count','entries':[{'name','offset','length'}],
         'index_end','file_size','data'(可选),'errors'}
    解析失败抛 ValueError（含中文说明）。
    """
    path = os.path.abspath(path)
    if not os.path.isfile(path):
        raise ValueError('文件不存在：%s' % path)
    file_size = os.path.getsize(path)
    # 索引长度可变，直接整体读入（85MB 内存充足，代码简单可靠）
    with open(path, 'rb') as f:
        data = f.read()
    magic, pos = _decode_string(data, 0)
    if magic != ZFB_MAGIC:
        raise ValueError('不是 zfbRes_v1 资源包（文件头为 %r）：%s' % (magic[:20], path))
    if pos + 4 > len(data):
        raise ValueError('文件过短，缺少条目数量')
    count = struct.unpack_from('<i', data, pos)[0]
    pos += 4
    if count < 0 or count > 10_000_000:
        raise ValueError('条目数量异常：%d' % count)
    entries: List[Dict[str, Any]] = []
    for i in range(count):
        name, pos = _decode_string(data, pos)
        if pos + 12 > len(data):
            raise ValueError('索引损坏：第 %d 个条目的 offset/length 越界' % i)
        offset = struct.unpack_from('<q', data, pos)[0]
        pos += 8
        length = struct.unpack_from('<i', data, pos)[0]
        pos += 4
        entries.append({'name': name, 'offset': offset, 'length': length})
    result: Dict[str, Any] = {
        'path': path,
        'magic': magic,
        'count': count,
        'entries': entries,
        'index_end': pos,
        'file_size': file_size,
        'errors': [],
    }
    if with_data:
        result['data'] = data
    return result


def validate_zfb(path: str) -> Dict[str, Any]:
    """校验 browser_assets 的索引/布局，返回报告（不抛异常）。"""
    errors: List[str] = []
    warnings: List[str] = []
    report: Dict[str, Any] = {'ok': False, 'path': os.path.abspath(path),
                              'errors': errors, 'warnings': warnings}
    try:
        info = read_zfb_index(path)
    except (ValueError, OSError) as exc:
        errors.append(str(exc))
        return report
    entries = info['entries']
    report.update({'count': info['count'], 'index_end': info['index_end'],
                   'file_size': info['file_size']})
    if not entries:
        errors.append('索引里没有任何条目')
        return report
    if entries[0]['offset'] < info['index_end']:
        errors.append('第一个条目 offset=%d 落在索引区内（index_end=%d）'
                      % (entries[0]['offset'], info['index_end']))
    seen = set()
    for i, e in enumerate(entries):
        if not e['name'].startswith('/'):
            warnings.append('条目 %r 不以 / 开头（IDE 以 URL 绝对路径查找，可能取不到）' % e['name'])
        if e['name'] in seen:
            errors.append('条目名重复：%r' % e['name'])
        seen.add(e['name'])
        if e['length'] < 0:
            errors.append('条目 %r 长度为负：%d' % (e['name'], e['length']))
        if e['offset'] < 0 or e['offset'] + e['length'] > info['file_size']:
            errors.append('条目 %r 数据越界：offset=%d len=%d file_size=%d'
                          % (e['name'], e['offset'], e['length'], info['file_size']))
        if i > 0:
            prev = entries[i - 1]
            if prev['offset'] + prev['length'] != e['offset']:
                # 真实文件要求连续（无填充）；只警告不判死
                warnings.append('条目 %r 与前一条目不连续（可能有对齐填充）' % e['name'])
                break
    last = entries[-1]
    if last['offset'] + last['length'] != info['file_size']:
        warnings.append('最后一个条目结束位置(%d) != 文件大小(%d)（可能有尾部数据）'
                        % (last['offset'] + last['length'], info['file_size']))
    report['ok'] = not errors
    return report


def _safe_rel_path(name: str) -> str:
    """把索引条目名转成安全相对路径（去掉前导 '/'，防止路径穿越）。"""
    rel = name.lstrip('/').replace('/', os.sep)
    if not rel or rel.startswith('..') or os.path.isabs(rel) or ':' in rel.split(os.sep)[0]:
        raise ValueError('条目名不安全，无法落盘：%r' % name)
    return rel


def unpack_zfb(src_path: str, out_dir: str, force: bool = False,
               index_out: Optional[str] = None,
               name_filter: Optional[Sequence[str]] = None) -> Dict[str, Any]:
    """
    解包 browser_assets 到目录（保留原始索引顺序与条目名）。

    返回 {'ok','out_dir','count','index','written','errors'}
    """
    info = read_zfb_index(src_path, with_data=True)
    data = info['data']
    out_dir = os.path.abspath(out_dir)
    if os.path.isdir(out_dir) and os.listdir(out_dir):
        if not force:
            raise FileExistsError('输出目录非空（加 --force 覆盖）：%s' % out_dir)
        shutil.rmtree(out_dir)
    os.makedirs(out_dir, exist_ok=True)
    written = 0
    for entry in info['entries']:
        if name_filter and entry['name'] not in name_filter:
            continue
        rel = _safe_rel_path(entry['name'])
        dest = os.path.join(out_dir, rel)
        os.makedirs(os.path.dirname(dest) or out_dir, exist_ok=True)
        with open(dest, 'wb') as f:
            f.write(data[entry['offset']:entry['offset'] + entry['length']])
        written += 1
    result = {
        'ok': True,
        'out_dir': out_dir,
        'count': info['count'],
        'written': written,
        'index_end': info['index_end'],
        'file_size': info['file_size'],
        'entries': [{'name': e['name'], 'length': e['length']} for e in info['entries']],
    }
    if index_out:
        os.makedirs(os.path.dirname(os.path.abspath(index_out)) or '.', exist_ok=True)
        with open(index_out, 'w', encoding='utf-8') as f:
            json.dump({'source': os.path.abspath(src_path),
                       'index_end': info['index_end'],
                       'file_size': info['file_size'],
                       'entries': info['entries']}, f, ensure_ascii=False, indent=2)
        result['index_out'] = os.path.abspath(index_out)
    return result


def repack_zfb(entries: Sequence[Dict[str, Any]], files_dir: str, out_path: str,
               progress: bool = False) -> Dict[str, Any]:
    """
    按索引顺序从 files_dir 读取每个条目文件，重新打包成 zfbRes_v1 格式。

    entries : [{'name','offset','length'}, ...]（原索引；offset/length 只用于对照，不用）
    """
    files_dir = os.path.abspath(files_dir)
    out_path = os.path.abspath(out_path)
    magic_bytes = _encode_string(ZFB_MAGIC)
    header = bytearray(magic_bytes)
    header += struct.pack('<i', len(entries))

    # 先读所有文件数据并计算偏移（索引区大小固定，数据区紧随其后）
    index_bytes = bytearray()
    blobs: List[bytes] = []
    total_data = 0
    for entry in entries:
        name = entry['name']
        rel = _safe_rel_path(name)
        src = os.path.join(files_dir, rel)
        if not os.path.isfile(src):
            raise ValueError('解包目录里缺少条目文件：%s（条目 %r）' % (src, name))
        with open(src, 'rb') as f:
            blob = f.read()
        blobs.append(blob)
        index_bytes += _encode_string(name)
        index_bytes += b'\x00' * 12  # 占位：int64 offset + int32 length，稍后填
        total_data += len(blob)

    first_offset = len(header) + len(index_bytes)
    out = bytearray(header)
    out += index_bytes
    # 写数据区，同时回填索引
    data_pos = first_offset
    idx_pos = len(header)
    for entry, blob in zip(entries, blobs):
        name_size = len(_encode_string(entry['name']))
        struct.pack_into('<q', out, idx_pos + name_size, data_pos)
        struct.pack_into('<i', out, idx_pos + name_size + 8, len(blob))
        idx_pos += name_size + 12
        out += blob
        data_pos += len(blob)
    os.makedirs(os.path.dirname(out_path) or '.', exist_ok=True)
    with open(out_path, 'wb') as f:
        f.write(out)
    return {
        'ok': True,
        'out_path': out_path,
        'count': len(entries),
        'bytes': len(out),
        'first_data_offset': first_offset,
        'sha256': srhs_tool.sha256_file(out_path),
    }


def read_zfb_entry_bytes(info: Dict[str, Any], name: str) -> bytes:
    """从 read_zfb_index(with_data=True) 结果里取某个条目内容。"""
    data = info.get('data')
    if data is None:
        raise ValueError('read_zfb_index 需要 with_data=True')
    for e in info['entries']:
        if e['name'] == name:
            return data[e['offset']:e['offset'] + e['length']]
    raise KeyError('条目不存在：%r' % name)


def compare_zfb_packages(old_path: str, new_path: str,
                         allowed_changed: Sequence[str] = (MAINGUI_INIT_KEY,)
                         ) -> Dict[str, Any]:
    """
    逐条目比较两个 browser_assets 包（按 sha256）。

    要求：条目数量/顺序/名字一致；除 allowed_changed 外所有条目内容必须完全一致；
    allowed_changed 里的条目必须确实发生变化。
    """
    old = read_zfb_index(old_path, with_data=True)
    new = read_zfb_index(new_path, with_data=True)
    report: Dict[str, Any] = {
        'ok': False,
        'old': os.path.abspath(old_path),
        'new': os.path.abspath(new_path),
        'old_count': old['count'],
        'new_count': new['count'],
        'changed': [],
        'missing': [],
        'extra': [],
        'order_mismatch': [],
        'unchanged_allowed': [],
        'errors': [],
        'warnings': [],
    }
    old_names = [e['name'] for e in old['entries']]
    new_names = [e['name'] for e in new['entries']]
    allowed = set(allowed_changed)
    if old_names != new_names:
        report['order_mismatch'] = [n for n in old_names if n not in set(new_names)]
        report['errors'].append('两个包的条目名/顺序不一致（旧 %d / 新 %d，第一个差异位置 %s）'
                                % (len(old_names), len(new_names),
                                   next((i for i, (a, b) in enumerate(zip(old_names, new_names)) if a != b), '长度不同')))
    else:
        old_map = {e['name']: e for e in old['entries']}
        new_map = {e['name']: e for e in new['entries']}
        for name in old_names:
            o, n = old_map[name], new_map[name]
            old_sha = srhs_tool.sha256_bytes(old['data'][o['offset']:o['offset'] + o['length']])
            new_sha = srhs_tool.sha256_bytes(new['data'][n['offset']:n['offset'] + n['length']])
            if old_sha == new_sha:
                if name in allowed:
                    report['unchanged_allowed'].append(name)
                    report['errors'].append('期望被修改的条目没有变化：%r' % name)
                continue
            if name in allowed:
                report['changed'].append({'name': name,
                                          'old_sha256': old_sha, 'new_sha256': new_sha,
                                          'old_len': o['length'], 'new_len': n['length']})
            else:
                report['errors'].append('不允许被修改的条目发生了变化：%r' % name)
    if report['errors']:
        report['ok'] = False
        return report
    report['ok'] = True
    return report


# ============================================================================
# 二、defaultcode 片段生成与 maingui_init.js 修改
# ============================================================================

def default_library_path() -> str:
    """本脚本默认函数库路径：优先 <WER_函数库>/我的函数库.srh(s)，其次 示例/WER函数库.srh(s)。"""
    lib_root = os.path.dirname(_HERE)          # WER_函数库/工具
    lib_root = os.path.dirname(lib_root)       # WER_函数库
    candidates = [
        os.path.join(lib_root, '我的函数库.srh'),
        os.path.join(lib_root, '我的函数库.srhs'),
        os.path.join(lib_root, '示例', 'WER函数库.srh'),
        os.path.join(lib_root, '示例', 'WER函数库.srhs'),
    ]
    for p in candidates:
        if os.path.isfile(p):
            return p
    return candidates[0]


def build_defaultcode_fragment(library_path: Optional[str] = None,
                               fragment_path: Optional[str] = None,
                               keep_variables: bool = True) -> Dict[str, Any]:
    """
    生成 defaultcode 片段（单行 XML 文本）。

    优先使用 fragment_path（现成片段文件）；否则从 library_path 自动抽取：
    `<xml>` 根 + `<variables>` + 全部顶层 block（必须含 start 块）。
    返回 {'fragment','source','top_blocks','start_blocks','variables','chars'}
    """
    if fragment_path:
        src = os.path.abspath(fragment_path)
        if not os.path.isfile(src):
            raise ValueError('片段文件不存在：%s' % src)
        fragment = srhs_tool.read_text_utf8(src).strip()
        source = src
    else:
        lib = os.path.abspath(library_path or default_library_path())
        if not os.path.isfile(lib):
            raise ValueError('函数库文件不存在：%s' % lib)
        srh = srhs_tool.read_project_file(lib)
        fragment = srhs_tool.extract_defaultcode(srh.project_xml,
                                                 keep_variables=keep_variables,
                                                 require_start=True)
        source = lib
    info = srhs_tool.validate_project_xml(fragment)
    if not info.get('ok'):
        raise ValueError('defaultcode 片段不是合法项目 XML：%s' % info.get('errors'))
    if not info.get('start_count'):
        raise ValueError('defaultcode 片段缺少 start 块（新建项目模板必须带 start）')
    return {
        'fragment': fragment,
        'source': source,
        'top_blocks': info.get('top_block_count', 0),
        'start_blocks': info.get('start_count', 0),
        'defnoreturn': len(info.get('defnoreturn_names', [])),
        'variables': len(info.get('variable_names', [])),
        'chars': len(fragment),
    }


def js_escape_js_string(content: str) -> str:
    """把内容转义成可放进 JS 单引号字符串的形式。"""
    return (content
            .replace('\\', '\\\\')
            .replace("'", "\\'")
            .replace('\r', '\\r')
            .replace('\n', '\\n')
            .replace('\t', '\\t')
            .replace('\u2028', '\\u2028')
            .replace('\u2029', '\\u2029'))


_JS_UNESCAPE_MAP = {'n': '\n', 'r': '\r', 't': '\t', "'": "'", '"': '"',
                    '\\': '\\', '/': '/', 'b': '\b', 'f': '\f'}


def js_unescape_js_string(literal: str) -> str:
    """把 JS 单引号字符串的**内容**（不含两侧引号）反转义成原文。"""
    out: List[str] = []
    i = 0
    n = len(literal)
    while i < n:
        c = literal[i]
        if c != '\\':
            out.append(c)
            i += 1
            continue
        i += 1
        if i >= n:
            out.append('\\')
            break
        e = literal[i]
        if e in _JS_UNESCAPE_MAP:
            out.append(_JS_UNESCAPE_MAP[e])
            i += 1
        elif e == 'u' and i + 4 < n:
            try:
                out.append(chr(int(literal[i + 1:i + 5], 16)))
                i += 5
            except ValueError:
                out.append('\\u')
                i += 1
        elif e == 'x' and i + 2 < n:
            try:
                out.append(chr(int(literal[i + 1:i + 3], 16)))
                i += 3
            except ValueError:
                out.append('\\x')
                i += 1
        else:
            out.append('\\' + e)
            i += 1
    return ''.join(out)


def _parse_js_string_literal(line: str, quote_pos: int) -> Tuple[str, int]:
    """从 line[quote_pos] 的引号开始解析一个 JS 字符串字面量，返回 (内容原文, 结束引号后位置)。"""
    quote = line[quote_pos]
    if quote not in "'\"":
        raise ValueError('不是字符串字面量起始位置：%r' % line[quote_pos:quote_pos + 20])
    i = quote_pos + 1
    n = len(line)
    while i < n:
        c = line[i]
        if c == '\\':
            i += 2
            continue
        if c == quote:
            return line[quote_pos + 1:i], i + 1
        i += 1
    raise ValueError('字符串字面量未闭合（从位置 %d 开始）' % quote_pos)


def find_defaultcode_line(text: str, var_name: str) -> Tuple[int, int, str]:
    """返回 (行号, 内容起始偏移, 原始内容)。找不到抛 ValueError。"""
    offset = 0
    prefix_re = re.compile(r'^\s*var\s+' + re.escape(var_name) + r'\s*=\s*')
    for lineno, line in enumerate(text.splitlines(keepends=True), 1):
        m = prefix_re.match(line)
        if m:
            quote_pos = line.find("'", m.end() - 1)
            if quote_pos < 0:
                quote_pos = line.find('"', m.end() - 1)
            if quote_pos < 0:
                raise ValueError('第 %d 行找到 var %s 但后面没有字符串' % (lineno, var_name))
            content, _end = _parse_js_string_literal(line, quote_pos)
            return lineno, offset + quote_pos + 1, content
        offset += len(line)
    raise ValueError('maingui_init.js 里找不到 var %s = \'...\' 行' % var_name)


def replace_js_string_in_text(text: str, var_name: str, new_content: str) -> Tuple[str, Dict[str, Any]]:
    """把 `var <var_name> = '...'` 里的字符串内容替换为 new_content（其它内容一个字节都不动）。"""
    lineno, content_start, _old_raw = find_defaultcode_line(text, var_name)
    quote_pos = content_start - 1
    quote = text[quote_pos]
    i = quote_pos + 1
    n = len(text)
    while i < n:
        c = text[i]
        if c == '\\':
            i += 2
            continue
        if c == quote:
            break
        i += 1
    else:
        raise ValueError('字符串字面量未闭合')
    old_content = js_unescape_js_string(text[quote_pos + 1:i])
    new_literal = js_escape_js_string(new_content)
    new_text = text[:quote_pos + 1] + new_literal + text[i:]
    return new_text, {
        'var_name': var_name,
        'line': lineno,
        'old_chars': len(old_content),
        'new_chars': len(new_content),
        'old_raw_len': i - quote_pos - 1,
        'new_raw_len': len(new_literal),
    }


def patch_maingui_init_text(text: str, fragment: str,
                            langs: Sequence[str] = (DEFAULT_LANGS,)
                            ) -> Dict[str, Any]:
    """修改 maingui_init.js 文本里指定语言的 defaultcode 变量。返回报告。"""
    report: Dict[str, Any] = {'patched': [], 'not_found': [], 'errors': []}
    new_text = text
    for lang in langs:
        var_name = DEFAULTCODE_VARS.get(lang)
        if not var_name:
            report['errors'].append('未知语言 %r（可选 %s）' % (lang, '/'.join(DEFAULTCODE_VARS)))
            continue
        try:
            new_text, info = replace_js_string_in_text(new_text, var_name, fragment)
            report['patched'].append(info)
        except ValueError as exc:
            report['not_found'].append({'lang': lang, 'var': var_name, 'error': str(exc)})
    if report['errors']:
        return report
    # 校验：重新读取，确认等于片段
    for lang in langs:
        var_name = DEFAULTCODE_VARS[lang]
        try:
            _lineno, _start, raw = find_defaultcode_line(new_text, var_name)
            decoded = js_unescape_js_string(raw)
            if decoded != fragment:
                report['errors'].append('替换后 %s 内容与片段不一致（%d vs %d 字符）'
                                        % (var_name, len(decoded), len(fragment)))
        except ValueError as exc:
            report['errors'].append('替换后回读 %s 失败：%s' % (var_name, exc))
    return report


# ============================================================================
# 三、主流程
# ============================================================================

def _is_admin() -> bool:
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:  # noqa: BLE001
        return False


def _can_write_dir(path: str) -> bool:
    """粗略判断目录是否可写（真正写入仍可能被 UAC 拒绝）。"""
    probe = os.path.join(path, '.write_test_%d' % os.getpid())
    try:
        with open(probe, 'wb') as f:
            f.write(b'x')
        os.remove(probe)
        return True
    except OSError:
        return False


def _timestamp() -> str:
    return time.strftime('%Y%m%d-%H%M%S')


def patch_assets(assets_path: str,
                 library_path: Optional[str] = None,
                 fragment_path: Optional[str] = None,
                 out_path: Optional[str] = None,
                 workdir: Optional[str] = None,
                 langs: Sequence[str] = (DEFAULT_LANGS,),
                 keep_variables: bool = True,
                 install: bool = False,
                 skip_identical_check: bool = False,
                 keep_work: bool = False,
                 progress: bool = True) -> Dict[str, Any]:
    """完整流程：校验格式 → 纯 roundtrip 自检 → 生成片段 → 解包 → 改 1 个条目 → 重打包 → 逐 sha256 自检 → (可选)安装。"""
    assets_path = os.path.abspath(assets_path)
    report: Dict[str, Any] = {
        'ok': False,
        'assets': assets_path,
        'dry_run': not install,
        'errors': [],
        'warnings': [],
        'steps': {},
        'installed': False,
    }

    def log(msg: str) -> None:
        if progress:
            print('[patch] ' + msg)
            sys.stdout.flush()

    # ---- 1) 原包格式校验 ----
    log('1/7 校验原资源包格式：%s' % assets_path)
    v = validate_zfb(assets_path)
    report['steps']['validate_original'] = v
    if not v.get('ok'):
        report['errors'].extend('原资源包校验失败：%s' % e for e in v.get('errors', []))
        return report
    report['original'] = {'count': v['count'], 'file_size': v['file_size'],
                          'sha256': srhs_tool.sha256_file(assets_path)}
    log('    条目数=%d，文件大小=%s' % (v['count'], srhs_tool._fmt_bytes(v['file_size'])))

    work_root = workdir or tempfile.mkdtemp(prefix='zfb_patch_')
    created_temp = workdir is None
    os.makedirs(work_root, exist_ok=True)
    report['workdir'] = os.path.abspath(work_root)
    unpack_dir = os.path.join(work_root, 'unpacked')
    try:
        # ---- 2) 纯 roundtrip 自检（不改任何内容，重新打包必须逐字节一致） ----
        log('2/7 纯 roundtrip 自检（解包 -> 原样重打包 -> 字节比较）')
        index = read_zfb_index(assets_path)
        unpack_zfb(assets_path, unpack_dir, force=True, index_out=os.path.join(work_root, 'index.json'))
        pure_repack = os.path.join(work_root, 'browser_assets.repack_only')
        repack_zfb(index['entries'], unpack_dir, pure_repack)
        identical = srhs_tool.sha256_file(assets_path) == srhs_tool.sha256_file(pure_repack)
        report['steps']['pure_roundtrip'] = {
            'ok': identical,
            'original_sha256': srhs_tool.sha256_file(assets_path),
            'repacked_sha256': srhs_tool.sha256_file(pure_repack),
            'identical': identical,
        }
        if not identical:
            msg = ('纯 roundtrip 后字节不一致！说明 zfbRes_v1 打包布局与原文件有差异，'
                   '不能安全改包。可用 --skip-identical-check 强制继续（不建议）。')
            if not skip_identical_check:
                report['errors'].append(msg)
                return report
            report['warnings'].append(msg + '（已按要求强制跳过）')
        else:
            log('    逐字节一致 ✓（%s）' % srhs_tool.sha256_file(assets_path)[:16])

        # ---- 3) 生成 defaultcode 片段 ----
        log('3/7 生成 defaultcode 片段')
        frag_info = build_defaultcode_fragment(library_path, fragment_path,
                                               keep_variables=keep_variables)
        report['steps']['fragment'] = {k: frag_info[k] for k in
                                       ('source', 'top_blocks', 'start_blocks',
                                        'defnoreturn', 'variables', 'chars')}
        log('    来源=%s  顶层块=%d (start=%d, 无返回函数=%d, 变量=%d)  片段=%d 字符'
            % (frag_info['source'], frag_info['top_blocks'], frag_info['start_blocks'],
               frag_info['defnoreturn'], frag_info['variables'], frag_info['chars']))

        # ---- 4) 修改解包目录里的 maingui_init.js ----
        log('4/7 修改 Blockly_Code/maingui_init.js（语言: %s）' % ','.join(langs))
        init_path = os.path.join(unpack_dir, MAINGUI_INIT_NAME.replace('/', os.sep))
        if not os.path.isfile(init_path):
            report['errors'].append('解包目录里找不到 %s' % init_path)
            return report
        with open(init_path, 'rb') as f:
            old_bytes = f.read()
        report['steps']['maingui_init'] = {
            'old_bytes': len(old_bytes),
            'old_sha256': srhs_tool.sha256_bytes(old_bytes),
        }
        old_text = srhs_tool.decode_utf8(old_bytes)
        # 先做一次“只验证不改写”的检查，再逐语言真正替换
        patch_check = patch_maingui_init_text(old_text, frag_info['fragment'], langs)
        report['steps']['defaultcode_patch'] = patch_check
        if patch_check['errors'] or patch_check.get('not_found'):
            report['errors'].append('修改 maingui_init.js 失败：%s'
                                    % (patch_check['errors'] or patch_check['not_found']))
            return report
        new_text = old_text
        for lang in langs:
            new_text, _info = replace_js_string_in_text(new_text, DEFAULTCODE_VARS[lang],
                                                        frag_info['fragment'])
        new_bytes = new_text.encode('utf-8')
        with open(init_path, 'wb') as f:
            f.write(new_bytes)
        report['steps']['maingui_init'].update({
            'new_bytes': len(new_bytes),
            'new_sha256': srhs_tool.sha256_bytes(new_bytes),
        })
        log('    %d -> %d 字节' % (len(old_bytes), len(new_bytes)))

        # ---- 5) 重新打包 ----
        log('5/7 重新打包 browser_assets')
        patched_pkg = os.path.join(work_root, 'browser_assets.patched')
        repack_zfb(index['entries'], unpack_dir, patched_pkg)
        report['patched'] = {
            'path': patched_pkg,
            'bytes': os.path.getsize(patched_pkg),
            'sha256': srhs_tool.sha256_file(patched_pkg),
        }
        log('    输出=%s (%s)' % (patched_pkg, srhs_tool._fmt_bytes(os.path.getsize(patched_pkg))))

        # ---- 6) 打包后自检：逐条目 sha256 ----
        log('6/7 打包后自检：逐条目 sha256 与旧包比较')
        cmp_report = compare_zfb_packages(assets_path, patched_pkg,
                                          allowed_changed=(MAINGUI_INIT_KEY,))
        report['steps']['compare'] = cmp_report
        if not cmp_report.get('ok'):
            report['errors'].extend('新包自检失败：%s' % e for e in cmp_report.get('errors', []))
            return report
        changed = cmp_report.get('changed') or []
        log('    其它 %d 个条目 sha256 全部一致 ✓；变化条目: %s'
            % (cmp_report['old_count'] - len(changed),
               ['%s (%d->%d 字节)' % (c['name'], c['old_len'], c['new_len']) for c in changed]))
        report['unchanged_entries'] = cmp_report['old_count'] - len(changed)

        # ---- 7) 输出/安装 ----
        if out_path:
            out_abs = os.path.abspath(out_path)
            os.makedirs(os.path.dirname(out_abs) or '.', exist_ok=True)
            shutil.copy2(patched_pkg, out_abs)
            report['out'] = out_abs
            log('7/7 已复制补丁包到：%s' % out_abs)
        else:
            report['out'] = patched_pkg
            if not keep_work and not install:
                report['warnings'].append('未指定 --out，补丁包在临时目录 %s（本次退出后会删除，'
                                          '正式安装请用 --install 或加 --out/--keep-work）'
                                          % patched_pkg)

        if install:
            log('7/7 安装到安装目录（需要管理员权限）')
            install_report = install_assets(patched_pkg, assets_path)
            report['steps']['install'] = install_report
            if not install_report.get('ok'):
                report['errors'].extend('安装失败：%s' % e for e in install_report.get('errors', []))
                return report
            report['installed'] = True
            report['backup'] = install_report.get('backup')
        report['ok'] = not report['errors']
        return report
    except (ValueError, OSError, RuntimeError, FileExistsError) as exc:
        report['errors'].append('处理失败：%s' % exc)
        return report
    finally:
        if created_temp and not keep_work:
            shutil.rmtree(work_root, ignore_errors=True)
        elif created_temp and keep_work:
            report['workdir'] = os.path.abspath(work_root)


def install_assets(new_assets: str, assets_path: str) -> Dict[str, Any]:
    """
    备份原 browser_assets 为 `browser_assets.备份-<时间戳>`，然后把 new_assets 复制过去。

    需要管理员权限/目录可写；返回 {'ok','backup','sha256','errors'}。
    """
    report: Dict[str, Any] = {'ok': False, 'backup': None, 'errors': [], 'warnings': []}
    assets_path = os.path.abspath(assets_path)
    new_assets = os.path.abspath(new_assets)
    if not os.path.isfile(new_assets):
        report['errors'].append('补丁包不存在：%s' % new_assets)
        return report
    if not os.path.isfile(assets_path):
        report['errors'].append('安装目录里的 browser_assets 不存在：%s' % assets_path)
        return report
    target_dir = os.path.dirname(assets_path)
    if not _can_write_dir(target_dir):
        report['errors'].append(
            '没有写入权限：%s\n'
            '  请以“管理员身份运行”本脚本（推荐用同目录的 一键应用补丁(管理员).cmd），'
            '或右键 PowerShell/命令行 → 以管理员身份运行后重试。\n'
            '  当前是否管理员：%s' % (target_dir, _is_admin()))
        return report
    backup = os.path.join(target_dir, BACKUP_PREFIX + _timestamp())
    n = 1
    while os.path.exists(backup):
        backup = os.path.join(target_dir, BACKUP_PREFIX + _timestamp() + '_%d' % n)
        n += 1
    shutil.copy2(assets_path, backup)
    # 校验备份完整性
    if srhs_tool.sha256_file(backup) != srhs_tool.sha256_file(assets_path):
        report['errors'].append('备份文件校验不一致（未做任何修改）：%s' % backup)
        return report
    report['backup'] = backup
    shutil.copy2(new_assets, assets_path)
    if srhs_tool.sha256_file(assets_path) != srhs_tool.sha256_file(new_assets):
        report['errors'].append('写入后的 browser_assets 与补丁包 sha256 不一致！'
                                '请立刻用还原脚本恢复（备份：%s）' % backup)
        return report
    report['ok'] = True
    report['sha256'] = srhs_tool.sha256_file(assets_path)
    return report


# ============================================================================
# 四、CLI
# ============================================================================

def _print_report(report: Dict[str, Any], as_json: bool = False) -> None:
    if as_json:
        print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
        return
    print('=' * 72)
    print('新建项目默认模板补丁 —— %s' % ('【安装到安装目录】' if report.get('installed')
                                       else '【仅生成补丁包，未安装】'))
    print('-' * 72)
    print('原资源包    : %s' % report.get('assets'))
    if report.get('original'):
        print('原包条目数  : %d   %s'
              % (report['original']['count'],
                 srhs_tool._fmt_bytes(report['original']['file_size'])))
        print('原包 sha256 : %s' % report['original']['sha256'])
    frag = (report.get('steps') or {}).get('fragment')
    if frag:
        print('defaultcode : 来源 %s' % frag['source'])
        print('              顶层块=%d (start=%d)  函数=%d  变量=%d  字符=%d'
              % (frag['top_blocks'], frag['start_blocks'], frag['defnoreturn'],
                 frag['variables'], frag['chars']))
    pure = (report.get('steps') or {}).get('pure_roundtrip')
    if pure:
        print('纯 roundtrip: %s' % ('逐字节一致 ✓' if pure['identical'] else '不一致 ✗'))
    cmp_r = (report.get('steps') or {}).get('compare')
    if cmp_r:
        print('打包后自检  : %s（条目 %d，变化 %d 个）'
              % ('通过 ✓' if cmp_r['ok'] else '失败 ✗', cmp_r['old_count'],
                 len(cmp_r.get('changed') or [])))
        for c in cmp_r.get('changed') or []:
            print('  变化条目: %s  %d -> %d 字节'
                  % (c['name'], c['old_len'], c['new_len']))
    if report.get('patched'):
        print('补丁包      : %s (%s)'
              % (report['patched']['path'], srhs_tool._fmt_bytes(report['patched']['bytes'])))
        print('补丁包sha256: %s' % report['patched']['sha256'])
    if report.get('out'):
        print('输出        : %s' % report['out'])
    if report.get('backup'):
        print('原文件备份  : %s' % report['backup'])
    if report.get('installed'):
        print('状态        : ✓ 已写入安装目录（重启 IDE 后新建项目即自带函数库）')
        print('还原命令    : python 还原默认模板.py --apply')
    elif report.get('ok'):
        print('状态        : 补丁包已生成，尚未安装（加 --install 由管理员安装）')
    for w in report.get('warnings') or []:
        print('[警告] %s' % w)
    for e in report.get('errors') or []:
        print('[错误] %s' % e)
    print('=' * 72)


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog='patch_browser_assets.py',
        description='给 AbilixScratch3.0 的 browser_assets 打补丁：新建项目自带 WER 函数库'
                    '（只改 Blockly_Code/maingui_init.js 一个条目，其余条目 sha256 不变）。',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='示例：\n'
               '  # 副本演练（不碰安装目录）\n'
               '  python patch_browser_assets.py --assets 副本\\browser_assets --out 副本\\patched\n'
               '  # 管理员安装\n'
               '  python patch_browser_assets.py --install\n'
               '  # 只比较两个包\n'
               '  python patch_browser_assets.py --verify-only 原包 新包\n')
    p.add_argument('--assets', default=None,
                   help='要打补丁的 browser_assets 路径（默认自动找安装目录）')
    p.add_argument('--library', default=None,
                   help='函数库项目文件 .srh/.srhs（默认 <WER_函数库>/WER函数库.srh）')
    p.add_argument('--fragment', default=None,
                   help='现成的 defaultcode 片段 XML 文件（给了则优先用它，不再从 --library 抽取）')
    p.add_argument('--out', default=None,
                   help='把生成的补丁包复制到该路径（可选；不给则保留在工作目录）')
    p.add_argument('--workdir', default=None, help='临时工作目录（默认系统临时目录，自动清理）')
    p.add_argument('--langs', default=DEFAULT_LANGS,
                   help='替换哪些语言的 defaultcode：zh-hans[,zh-hant,en] 或 all（默认 zh-hans）')
    p.add_argument('--drop-variables', action='store_true',
                   help='defaultcode 片段里去掉 <variables>（不建议；默认保留变量声明）')
    p.add_argument('--install', action='store_true',
                   help='把补丁包写回安装目录（会先备份原文件；需要管理员权限）')
    p.add_argument('--dry-run', action='store_true', help='只生成/自检补丁包，不安装（默认行为）')
    p.add_argument('--skip-identical-check', action='store_true',
                   help='跳过“纯 roundtrip 必须逐字节一致”的强制检查（不建议）')
    p.add_argument('--keep-work', action='store_true', help='保留临时工作目录（含解包文件/中间包）')
    p.add_argument('--verify-only', nargs=2, metavar=('OLD', 'NEW'), default=None,
                   help='只比较两个 browser_assets 包的逐条目 sha256（不生成/不安装）')
    p.add_argument('--json', action='store_true', help='输出 JSON 报告到标准输出')
    p.add_argument('--json-out', default=None, help='把 JSON 报告写到指定文件（用于留证据）')
    return p


def _parse_langs(value: str) -> List[str]:
    value = (value or '').strip().lower()
    if value in ('all', '*', '全部'):
        return list(DEFAULTCODE_VARS.keys())
    langs = [x.strip() for x in re.split(r'[,\s]+', value) if x.strip()]
    for lang in langs:
        if lang not in DEFAULTCODE_VARS:
            raise ValueError('未知语言 %r（可选: %s，或 all）'
                             % (lang, ', '.join(DEFAULTCODE_VARS)))
    return langs


def main(argv: Optional[Sequence[str]] = None) -> int:
    srhs_tool.setup_console()
    args = build_arg_parser().parse_args(argv)

    if args.verify_only:
        report = compare_zfb_packages(args.verify_only[0], args.verify_only[1])
        if args.json:
            print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
        else:
            print('=' * 72)
            print('逐条目比较：%s  vs  %s' % tuple(report['old'], report['new']))
            print('条目数 %d vs %d' % (report['old_count'], report['new_count']))
            print('结论: %s' % ('通过（只允许的条目发生变化）' if report['ok'] else '不通过'))
            for c in report['changed']:
                print('  变化: %s  %d -> %d 字节' % (c['name'], c['old_len'], c['new_len']))
            for e in report['errors']:
                print('[错误] %s' % e)
            print('=' * 72)
        return 0 if report['ok'] else 1

    try:
        langs = _parse_langs(args.langs)
    except ValueError as exc:
        sys.stderr.write('[错误] %s\n' % exc)
        return 2
    assets = args.assets or DEFAULT_ASSETS
    if not os.path.isfile(assets):
        sys.stderr.write('[错误] 找不到 browser_assets：%s\n'
                         '  可用 --assets 指定路径。\n' % assets)
        return 2
    install = bool(args.install and not args.dry_run)
    report = patch_assets(
        assets_path=assets,
        library_path=args.library,
        fragment_path=args.fragment,
        out_path=args.out,
        workdir=args.workdir,
        langs=langs,
        keep_variables=not args.drop_variables,
        install=install,
        skip_identical_check=args.skip_identical_check,
        keep_work=args.keep_work,
    )
    _print_report(report, args.json)
    if args.json_out:
        out_abs = os.path.abspath(args.json_out)
        os.makedirs(os.path.dirname(out_abs) or '.', exist_ok=True)
        with open(out_abs, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2, default=str)
        print('JSON 报告已写入：%s' % out_abs)
    return 0 if report.get('ok') else 1


if __name__ == '__main__':
    sys.exit(main())
