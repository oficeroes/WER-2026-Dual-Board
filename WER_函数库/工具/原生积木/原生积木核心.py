# -*- coding: utf-8 -*-
"""
原生积木核心工具（WER 函数库 -> AbilixScratch3.0 内部积木块）

把「我的函数库.srhs / .srh」编译成 IDE 内部的原生积木：
  - 在左侧工具箱里新增一个「我的函数」分类，里面每个函数一块，可以直接拖；
  - 拖进程序后，右侧 Python 面板会自动带上函数定义（不存在两个项目之间的复制粘贴）。

实现方式（不改 .srh 项目文件、不改新建项目默认模板）：
  1. 用 IDE 自带真实 Blockly 引擎（headless Chrome）把函数库工程生成 Python，
     截取「全局变量声明 + def 函数定义」作为 prelude；
  2. 新增资源条目 /Blockly_Code/abilix_userlib.js：注册 Blockly.Blocks / Blockly.Python
     块类型（abilixuf_*）、prelude 文本、函数元数据；
  3. 修改 maingui.html：3 个机器人工具箱各加一个「我的函数」分类，并加载新脚本；
  4. 修改 maingui.js 的 getPythonCode：仅当当前工程里用到原生块时，才把 prelude
     插到 workspaceToCode 之前（不用原生块的项目生成结果与官方逐字节一致）；
  5. 新增资源条目 /Blockly_Code/abilix_userlib.json：补丁清单（用于状态检查/更新）。

子命令：
  build    编译函数库 -> 输出打过补丁的 browser_assets（不写安装目录）
  install  备份并安装到真实 IDE（需要管理员，UAC 请用户双击运行）
  restore  用备份恢复原版 browser_assets
  status   只读检查：是否已打补丁、函数库是否变化、备份情况、IDE 是否在运行
  verify   校验一个补丁包（条目数/顺序/除预期条目外逐字节一致）

示例：
  python 原生积木核心.py status
  python 原生积木核心.py build --library "WER_函数库\\我的函数库.srhs" ^
      --source-assets "D:\\Program Files\\AbilixScratch3.0\\AbilixScratch3.0_Data\\Resources\\browser_assets" ^
      --out "_分析临时\\native_work\\browser_assets_patched.bin"
  python 原生积木核心.py install --library "WER_函数库\\我的函数库.srhs"
"""
from __future__ import annotations

import argparse
import ctypes
import hashlib
import json
import os
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import time
import zipfile
from typing import Any, Dict, List, Optional, Sequence, Tuple

HERE = os.path.dirname(os.path.abspath(__file__))            # WER_函数库/工具/原生积木
TOOL_DIR = os.path.dirname(HERE)                             # WER_函数库/工具
LIB_ROOT = os.path.dirname(TOOL_DIR)                         # WER_函数库
REPO_ROOT = os.path.dirname(LIB_ROOT)                        # 工作区根
BOTTOM_DIR = os.path.join(TOOL_DIR, '底层')
VERIFY_DIR = os.path.join(TOOL_DIR, '验证')
sys.path.insert(0, BOTTOM_DIR)

import patch_browser_assets as pb          # noqa: E402  (zfb 解包/重打包)
import srhs工具 as st                      # noqa: E402  (srh 解析/哈希/校验)

# ---------------------------------------------------------------------------
# 常量
# ---------------------------------------------------------------------------
TOOL_NAME = 'WER原生积木核心'
TOOL_VERSION = '1.0.0'

ORIGINAL_ASSETS_SHA = 'DF6DB241752D42BFF2995FCD24521E070ADF9EB5D96E870148F9DC51690EDC40'
ORIGINAL_ASSETS_SIZE = 85_271_033

DEFAULT_INSTALL = r'D:\Program Files\AbilixScratch3.0'
DEFAULT_ASSETS = os.path.join(DEFAULT_INSTALL, 'AbilixScratch3.0_Data', 'Resources', 'browser_assets')
DEFAULT_LIBRARY = os.path.join(LIB_ROOT, '我的函数库.srhs')
DEFAULT_BACKUP_DIR = os.path.join(HERE, '备份')
DEFAULT_WORK_PARENT = os.path.join(REPO_ROOT, '_分析临时', 'native_work', 'build')

KEY_HTML = '/Blockly_Code/maingui.html'
KEY_JS = '/Blockly_Code/maingui.js'
KEY_USERLIB = '/Blockly_Code/abilix_userlib.js'
KEY_MANIFEST = '/Blockly_Code/abilix_userlib.json'

SCRIPT_TAG = '<script src="abilix_userlib.js"></script>'
SCRIPT_ANCHOR = '<script src="generators\\myrobotpythoncode.js"></script>'
CATEGORY_NAME = '我的函数'
CATEGORY_COLOUR = '#9933FF'
BLOCK_TYPE_PREFIX = 'abilixuf_'

PY_MARKER = '\n\ndef main():'
PY_HEADER_ANCHOR = 'robot = Robot()\n'
NAME_RE = re.compile(r'^[A-Za-z_][A-Za-z0-9_]*$')
DEF_RE_TMPL = r'^def\s+%s\s*\('


# ---------------------------------------------------------------------------
# 基础工具
# ---------------------------------------------------------------------------
def log(msg: str = '') -> None:
    print(msg, flush=True)


def sha256_file(path: str) -> str:
    return st.sha256_file(path)


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def is_admin() -> bool:
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def ide_running() -> List[str]:
    """返回正在运行的 AbilixScratch3.0 进程名列表（用 tasklist，不依赖 psutil）。"""
    names: List[str] = []
    try:
        out = subprocess.run(['tasklist', '/FO', 'CSV', '/NH'],
                             capture_output=True, text=True, encoding='mbcs',
                             errors='replace', timeout=20).stdout
        for line in out.splitlines():
            low = line.lower()
            if 'abilixscratch' in low:
                first = line.split(',')[0].strip('"')
                if first:
                    names.append(first)
    except Exception:
        pass
    return names


def ensure_no_ide(force: bool) -> None:
    running = ide_running()
    if running and not force:
        raise RuntimeError('IDE 正在运行（%s）。请先关闭 AbilixScratch3.0 再操作；'
                           '如果确认要强制继续，加 --force。' % '、'.join(sorted(set(running))))


def fmt_size(n: int) -> str:
    for unit in ('B', 'KB', 'MB', 'GB'):
        if n < 1024 or unit == 'GB':
            return '%.1f %s' % (n, unit) if unit != 'B' else '%d B' % n
        n /= 1024.0
    return '%d B' % n


def rel(path: str) -> str:
    """尽量输出相对工作区路径，便于阅读。"""
    try:
        rp = os.path.relpath(os.path.abspath(path), REPO_ROOT)
        if not rp.startswith('..'):
            return rp
    except Exception:
        pass
    return path


def write_json(path: str, data: Any) -> None:
    os.makedirs(os.path.dirname(os.path.abspath(path)) or '.', exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write('\n')


def read_json(path: str) -> Optional[Any]:
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


# ---------------------------------------------------------------------------
# 函数库 -> 元数据 / prelude
# ---------------------------------------------------------------------------
def sanitize_block_suffix(name: str) -> str:
    return re.sub(r'[^A-Za-z0-9_]', '_', name)


def block_type_of(name: str) -> str:
    return BLOCK_TYPE_PREFIX + sanitize_block_suffix(name)


def annotation_text(raw_block_xml: str) -> str:
    """从函数定义块里抽取 annotation 注释文本（用作积木 tooltip）。"""
    tips: List[str] = []
    try:
        import xml.etree.ElementTree as ET
        el = ET.fromstring(raw_block_xml)
    except Exception:
        return ''
    for f in el.iter('field'):
        if f.get('name') == 'text' and f.text:
            t = ' '.join(f.text.split())
            if t:
                tips.append(t)
    return ' '.join(tips)


def load_library(lib_path: str) -> Dict[str, Any]:
    """解析函数库工程，返回函数元数据与工程信息。"""
    lib_path = os.path.abspath(lib_path)
    if not os.path.isfile(lib_path):
        raise RuntimeError('函数库文件不存在：%s' % lib_path)
    f = st.read_project_file(lib_path)
    defs_raw = st.find_def_blocks(f.project_xml)
    if not defs_raw:
        raise RuntimeError('函数库里没有函数定义（procedures_defnoreturn）。'
                           '请先在 IDE 里搭好至少一个函数，保存为：%s' % lib_path)
    defs: List[Dict[str, Any]] = []
    seen_names = set()
    seen_types = set()
    for d in defs_raw:
        name = (d.get('name') or '').strip()
        if not name:
            raise RuntimeError('函数库里有名字为空的函数定义。')
        if not NAME_RE.match(name):
            raise RuntimeError('函数名 %r 不是合法的 Python 标识符（只能用英文字母/数字/下划线，且不能以数字开头）。'
                               '请回到 IDE 里重命名后重新保存函数库。' % name)
        if name in seen_names:
            raise RuntimeError('函数库里有重名函数：%r' % name)
        seen_names.add(name)
        btype = block_type_of(name)
        if btype in seen_types:
            raise RuntimeError('函数名 %r 与另一个函数在积木类型上冲突（%s）。' % (name, btype))
        seen_types.add(btype)
        args = [str(a) for a in (d.get('args') or [])]
        bad_args = [a for a in args if not NAME_RE.match(a)]
        if bad_args:
            raise RuntimeError('函数 %s 的参数名不是合法 Python 标识符：%s。'
                               '请回到 IDE 里把参数改成英文后重新保存函数库。'
                               % (name, '、'.join(bad_args)))
        defs.append({
            'name': name,
            'args': args,
            'blockType': btype,
            'tip': annotation_text(d.get('raw') or ''),
            'raw': d.get('raw') or '',
        })
    return {
        'path': lib_path,
        'sha256': sha256_file(lib_path),
        'size': os.path.getsize(lib_path),
        'robotType': f.robot_type,
        'programName': f.download_program_name,
        'defs': defs,
    }


def call_run_validate(lib_path: str, web_root: str, out_py: str, out_json: str,
                      work_parent: Optional[str] = None, timeout: float = 300.0,
                      keep: bool = False) -> Dict[str, Any]:
    """调用真实引擎 harness，确认函数库本身可渲染/可生成。"""
    script = os.path.join(VERIFY_DIR, 'run_validate.py')
    if not os.path.isfile(script):
        raise RuntimeError('找不到验证工具：%s（原生积木需要它来调用 IDE 自带 Blockly 引擎）' % script)
    cmd = [sys.executable, script, lib_path,
           '--web-root', web_root,
           '--py', out_py,
           '--json', out_json,
           '--timeout', str(int(timeout)),
           '--window-size', '1600,1800']
    if work_parent:
        os.makedirs(work_parent, exist_ok=True)
        cmd += ['--work-dir', work_parent]
    if keep:
        cmd.append('--keep')
    log('  · 调用真实 Blockly 引擎生成函数库 Python …')
    r = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8',
                       errors='replace')
    report = read_json(out_json) or {}
    return {'returncode': r.returncode, 'stdout': r.stdout or '',
            'stderr': r.stderr or '', 'report': report}


def extract_prelude(generated_py: str, defs: Sequence[Dict[str, Any]]) -> str:
    """从函数库生成的完整 Python 中截取『变量声明 + 函数定义』。"""
    idx = generated_py.find(PY_MARKER)
    if idx < 0:
        raise RuntimeError('生成的 Python 里找不到 "def main():"，函数库工程可能损坏。')
    head = generated_py[:idx]
    ai = head.find(PY_HEADER_ANCHOR)
    if ai < 0:
        raise RuntimeError('生成的 Python 里找不到 "robot = Robot()"，不是预期的 IDE 生成格式。')
    prelude = head[ai + len(PY_HEADER_ANCHOR):idx].strip('\n')
    if not prelude:
        raise RuntimeError('函数库生成结果里没有任何函数定义（prelude 为空）。')
    # 防呆：不应再把 import/文件头带回来
    for ln in prelude.splitlines():
        if ln.startswith('import ') or ln.startswith('#<') or ln.startswith('robot = Robot()'):
            raise RuntimeError('prelude 提取异常，包含文件头/import 行：%r' % ln)
    for d in defs:
        pat = re.compile(DEF_RE_TMPL % re.escape(d['name']), re.M)
        if not pat.search(prelude):
            raise RuntimeError('生成结果里缺少函数定义 def %s(...)，请检查函数库工程。' % d['name'])
    # 语法自检
    try:
        compile(prelude + '\ndef _wer_probe_main():\n    pass\n_wer_probe_main()\n',
                '<wer_userlib_prelude>', 'exec')
    except SyntaxError as exc:
        raise RuntimeError('提取出的函数定义有语法错误：%s' % exc)
    return prelude + '\n\n'


def build_prelude(lib: Dict[str, Any], source_assets: str, workdir: str,
                  cache_file: Optional[str] = None,
                  timeout: float = 300.0) -> Tuple[str, Dict[str, Any]]:
    """解包原始资源 -> 真实引擎生成 -> 截取 prelude。"""
    os.makedirs(workdir, exist_ok=True)
    web_root = os.path.join(workdir, 'web')
    log('  · 解包原始资源包（约 80 MB / 6600 条目）…')
    t0 = time.time()
    pb.unpack_zfb(source_assets, web_root, force=True)
    log('    完成：%s（%.1f 秒）' % (web_root, time.time() - t0))

    gen_py = os.path.join(workdir, 'library_generated.py')
    gen_json = os.path.join(workdir, 'library_validate.json')
    work_parent = os.path.join(workdir, 'harness')
    res = call_run_validate(lib['path'], web_root, gen_py, gen_json,
                            work_parent=work_parent, timeout=timeout)
    if res['returncode'] != 0 or not os.path.isfile(gen_py):
        tail = '\n'.join((res['stdout'] + res['stderr']).strip().splitlines()[-25:])
        raise RuntimeError('真实引擎生成函数库 Python 失败（退出码 %s）。\n%s\n'
                           '提示：打补丁的电脑需要有 Chrome 或 Edge（本机两者其一即可）。'
                           % (res['returncode'], tail))
    generated = open(gen_py, 'r', encoding='utf-8').read()
    prelude = extract_prelude(generated, lib['defs'])
    if cache_file:
        os.makedirs(os.path.dirname(os.path.abspath(cache_file)) or '.', exist_ok=True)
        with open(cache_file, 'w', encoding='utf-8') as f:
            f.write(prelude)
    report = res.get('report') or {}
    meta = report.get('meta') if isinstance(report, dict) else None
    return prelude, {
        'webRoot': web_root,
        'generatedPy': gen_py,
        'usedRealSource': bool((meta or {}).get('usedRealSource')),
        'flyoutBlocks': (report.get('flyout') or {}).get('total') if isinstance(report, dict) else None,
    }


# ---------------------------------------------------------------------------
# 生成 abilix_userlib.js / 分类 XML / 补丁 maingui.html/js
# ---------------------------------------------------------------------------
def build_userlib_js(lib: Dict[str, Any], prelude: str) -> str:
    meta = [{'name': d['name'], 'args': d['args'], 'tip': d['tip'],
             'blockType': d['blockType']} for d in lib['defs']]
    prelude_js = json.dumps(prelude, ensure_ascii=False).replace('</', '<\\/')
    meta_js = json.dumps(meta, ensure_ascii=False).replace('</', '<\\/')
    return '''/* AbilixScratch3.0 原生函数积木 —— 由「WER_函数库/工具/原生积木/原生积木核心.py」自动生成，请勿手改。 */
var abilixUserLibPython = %(prelude)s;
var abilixUserLib = %(meta)s;
(function () {
  function label(s) { return String(s == null ? "" : s); }
  for (var i = 0; i < abilixUserLib.length; i++) {
    (function (fn) {
      var type = "abilixuf_" + fn.name.replace(/[^A-Za-z0-9_]/g, "_");
      fn.blockType = type;
      Blockly.Blocks[type] = {
        init: function () {
          this.appendDummyInput().appendField(label(fn.name));
          this.setPreviousStatement(true, null);
          this.setNextStatement(true, null);
          for (var a = 0; a < fn.args.length; a++) {
            this.appendValueInput("ARG" + a).setCheck(null).appendField(label(fn.args[a]));
          }
          this.setInputsInline(false);
          this.setColour(290);
          this.setTooltip(label(fn.tip || fn.name) + "（来自我的函数库）");
          this.setHelpUrl("");
        }
      };
      Blockly.Python[type] = function (block) {
        var parts = [];
        for (var a = 0; a < fn.args.length; a++) {
          parts.push(Blockly.Python.valueToCode(block, "ARG" + a, Blockly.Python.ORDER_NONE) || "");
        }
        return fn.name + "(" + parts.join(", ") + ")\\n";
      };
    })(abilixUserLib[i]);
  }
})();
''' % {'prelude': prelude_js, 'meta': meta_js}


def build_category_xml(defs: Sequence[Dict[str, Any]]) -> str:
    out: List[str] = []
    out.append('   <category name="%s" colour="%s">' % (CATEGORY_NAME, CATEGORY_COLOUR))
    out.append('      <sep gap="8"></sep>')
    for d in defs:
        out.append('      <block type="%s">' % d['blockType'])
        for a in range(len(d['args'])):
            out.append('        <value name="ARG%d"><shadow type="math_number">'
                       '<field name="NUM">0</field></shadow></value>' % a)
        out.append('      </block>')
        out.append('      <sep gap="8"></sep>')
    out.append('   </category>')
    return '\n'.join(out)


def patch_html(html: str, category_xml: str) -> str:
    if SCRIPT_TAG in html:
        raise RuntimeError('maingui.html 里已经存在 abilix_userlib.js 脚本行：源资源包可能已打过补丁。')
    if html.count(SCRIPT_ANCHOR) != 1:
        raise RuntimeError('maingui.html 里 myrobotpythoncode 脚本行数量异常：%d' % html.count(SCRIPT_ANCHOR))
    html = html.replace(SCRIPT_ANCHOR, SCRIPT_ANCHOR + '\n  ' + SCRIPT_TAG, 1)

    out: List[str] = []
    pos = 0
    inserted = 0
    for m in re.finditer(r'<xml id="(toolbox_skcon\d)"[^>]*>', html):
        start = m.start()
        close = html.find('</xml>', start)
        if close < 0:
            close = html.find('</body>', start)
            if close < 0:
                raise RuntimeError('找不到工具箱 %s 的结束位置' % m.group(1))
        out.append(html[pos:close])
        out.append(category_xml + '\n  ')
        pos = close
        inserted += 1
    out.append(html[pos:])
    if inserted != 3:
        raise RuntimeError('预期给 3 个机器人工具箱加分类，实际找到 %d 个' % inserted)
    patched = ''.join(out)
    if patched.count('name="%s"' % CATEGORY_NAME) != 3:
        raise RuntimeError('maingui.html 分类插入数量异常')
    return patched


def patch_js(js: str) -> str:
    old = '\t\tBlockly.Python.workspaceToCode(workspace) +'
    new = ('\t\t((typeof abilixUserLibPython !== "undefined" && workspace && workspace.getAllBlocks && '
           'workspace.getAllBlocks().some(function(b){return (b.type||"").indexOf("abilixuf_")===0;})) '
           '? abilixUserLibPython : "") +\n'
           '\t\tBlockly.Python.workspaceToCode(workspace) +')
    n = js.count(old)
    if n != 2:
        raise RuntimeError('maingui.js 里 workspaceToCode 行数异常：%d（源资源包可能已打过补丁）' % n)
    js = js.replace(old, new)
    if js.count('abilixUserLibPython') != 4:
        raise RuntimeError('maingui.js 补丁后检查失败（abilixUserLibPython 出现 %d 次，预期 4 次）'
                           % js.count('abilixUserLibPython'))
    return js


# ---------------------------------------------------------------------------
# zfb 打包 / 校验
# ---------------------------------------------------------------------------
def _pack_zfb(entries: Sequence[Dict[str, Any]], name_to_data: Dict[str, bytes],
              out_path: str) -> Dict[str, Any]:
    header = bytearray(pb._encode_string(pb.ZFB_MAGIC))
    header += struct.pack('<i', len(entries))
    index_bytes = bytearray()
    blobs: List[bytes] = []
    for e in entries:
        name = e['name']
        if name not in name_to_data:
            raise RuntimeError('打包缺少条目内容：%r' % name)
        blob = name_to_data[name]
        blobs.append(blob)
        index_bytes += pb._encode_string(name)
        index_bytes += b'\x00' * 12
    out = bytearray(header)
    out += index_bytes
    data_pos = len(out)
    idx_pos = len(header)
    for e, blob in zip(entries, blobs):
        name_size = len(pb._encode_string(e['name']))
        struct.pack_into('<q', out, idx_pos + name_size, data_pos)
        struct.pack_into('<i', out, idx_pos + name_size + 8, len(blob))
        idx_pos += name_size + 12
        out += blob
        data_pos += len(blob)
    os.makedirs(os.path.dirname(os.path.abspath(out_path)) or '.', exist_ok=True)
    tmp = out_path + '.tmp'
    with open(tmp, 'wb') as f:
        f.write(out)
    os.replace(tmp, out_path)
    return {'ok': True, 'path': os.path.abspath(out_path), 'size': len(out),
            'sha256': hashlib.sha256(out).hexdigest(), 'count': len(entries)}


def verify_package(patched_path: str, original_path: str) -> Dict[str, Any]:
    """校验补丁包：条目索引合法；在原始包基础上仅新增/修改预期条目。"""
    report: Dict[str, Any] = {'ok': False, 'errors': [], 'warnings': [],
                              'changed': [], 'added': [], 'removed': [], 'unchanged': 0}
    try:
        old = pb.read_zfb_index(original_path, with_data=True)
        new = pb.read_zfb_index(patched_path, with_data=True)
    except ValueError as exc:
        report['errors'].append(str(exc))
        return report
    report['original'] = {'path': os.path.abspath(original_path), 'count': old['count'],
                          'size': old['file_size'], 'sha256': sha256_file(original_path)}
    report['patched'] = {'path': os.path.abspath(patched_path), 'count': new['count'],
                         'size': new['file_size'], 'sha256': sha256_file(patched_path)}
    v = pb.validate_zfb(patched_path)
    if not v['ok']:
        report['errors'].extend(v['errors'])
    old_names = [e['name'] for e in old['entries']]
    new_names = [e['name'] for e in new['entries']]
    if new_names[:len(old_names)] != old_names:
        report['errors'].append('补丁包前半部分的条目名/顺序与原始包不一致')
    extra_names = new_names[len(old_names):]
    report['added'] = extra_names
    expect_added = {KEY_USERLIB, KEY_MANIFEST}
    if set(extra_names) != expect_added:
        report['errors'].append('新增条目不是预期的 %s：%s' % (sorted(expect_added), extra_names))
    old_map = {e['name']: e for e in old['entries']}
    new_map = {e['name']: e for e in new['entries']}
    expect_changed = {KEY_HTML, KEY_JS}
    for name in old_names:
        o, n = old_map[name], new_map[name]
        o_sha = hashlib.sha256(old['data'][o['offset']:o['offset'] + o['length']]).hexdigest()
        n_sha = hashlib.sha256(new['data'][n['offset']:n['offset'] + n['length']]).hexdigest()
        if o_sha == n_sha:
            if name in expect_changed:
                report['errors'].append('预期被修改的条目没有变化：%r' % name)
            else:
                report['unchanged'] += 1
            continue
        if name in expect_changed:
            report['changed'].append({'name': name, 'old_len': o['length'], 'new_len': n['length']})
        else:
            report['errors'].append('不允许变化的条目发生变化：%r' % name)
    if len(report['changed']) != 2:
        report['errors'].append('预期修改 2 个条目，实际 %d 个' % len(report['changed']))
    report['ok'] = not report['errors']
    return report


# ---------------------------------------------------------------------------
# 构建（核心）
# ---------------------------------------------------------------------------
def do_build(library: str, source_assets: str, out_assets: str,
             workdir: Optional[str] = None, keep_work: bool = False,
             prelude_cache: Optional[str] = None,
             prelude_in: Optional[str] = None,
             web_out: Optional[str] = None,
             json_out: Optional[str] = None,
             timeout: float = 300.0,
             write_manifest_path: bool = True) -> Dict[str, Any]:
    """编译函数库 -> 输出打过补丁的 browser_assets。"""
    t_start = time.time()
    library = os.path.abspath(library)
    source_assets = os.path.abspath(source_assets)
    out_assets = os.path.abspath(out_assets)

    log('=' * 78)
    log('原生积木：编译函数库')
    log('  函数库      : %s' % rel(library))
    log('  原始资源包  : %s' % rel(source_assets))
    log('  输出补丁包  : %s' % rel(out_assets))
    log('=' * 78)

    if not os.path.isfile(source_assets):
        raise RuntimeError('原始资源包不存在：%s' % source_assets)
    if os.path.abspath(source_assets) == os.path.abspath(out_assets):
        raise RuntimeError('输出路径不能与原始资源包相同（防止覆盖原版文件）。')

    info = pb.read_zfb_index(source_assets, with_data=True)
    names = [e['name'] for e in info['entries']]
    if KEY_MANIFEST in names or KEY_USERLIB in names:
        raise RuntimeError('这个资源包已经是打过原生积木补丁的版本。\n'
                           '请用备份的原始资源包（browser_assets.原始.*.bin）作为 --source-assets；'
                           '或先 restore 再 install。')
    for key in (KEY_HTML, KEY_JS):
        if key not in names:
            raise RuntimeError('原始资源包里缺少 %s，可能不是 AbilixScratch3.0 的 browser_assets。' % key)
    src_sha = sha256_file(source_assets)
    src_size = os.path.getsize(source_assets)
    log('  原始资源包校验：%s / %s' % (fmt_size(src_size), src_sha[:16] + '…'))
    if src_sha.lower() != ORIGINAL_ASSETS_SHA.lower():
        log('  ⚠ 注意：这不像本机记录的原始资源包（sha256 不同），但格式合法，继续编译。')

    lib = load_library(library)
    log('  函数库：%s（%d 个函数：%s）'
        % (lib['programName'] or '未命名', len(lib['defs']),
           '、'.join(d['name'] for d in lib['defs'])))

    temp_owner = None
    if workdir:
        workdir = os.path.abspath(workdir)
        if os.path.isdir(workdir) and os.listdir(workdir):
            shutil.rmtree(workdir)
        os.makedirs(workdir, exist_ok=True)
    else:
        temp_owner = tempfile.mkdtemp(prefix='wer_native_')
        workdir = temp_owner

    try:
        if prelude_in:
            if not os.path.isfile(prelude_in):
                raise RuntimeError('--prelude-in 指定的文件不存在：%s' % prelude_in)
            prelude = open(prelude_in, 'r', encoding='utf-8').read()
            for d in lib['defs']:
                if not re.search(DEF_RE_TMPL % re.escape(d['name']), prelude, re.M):
                    raise RuntimeError('--prelude-in 里缺少 def %s(...)，与函数库不匹配。' % d['name'])
            engine = {'usedRealSource': None, 'note': 'prelude 由 --prelude-in 提供'}
            log('  · 使用外部提供的 prelude：%s' % prelude_in)
        else:
            prelude, engine = build_prelude(lib, source_assets, workdir,
                                            cache_file=prelude_cache, timeout=timeout)

        js_text = build_userlib_js(lib, prelude)
        cat_text = build_category_xml(lib['defs'])

        name_to_data: Dict[str, bytes] = {
            e['name']: info['data'][e['offset']:e['offset'] + e['length']]
            for e in info['entries']
        }
        html_old = name_to_data[KEY_HTML].decode('utf-8')
        js_old = name_to_data[KEY_JS].decode('utf-8')
        html_new = patch_html(html_old, cat_text)
        js_new = patch_js(js_old)
        name_to_data[KEY_HTML] = html_new.encode('utf-8')
        name_to_data[KEY_JS] = js_new.encode('utf-8')
        name_to_data[KEY_USERLIB] = js_text.encode('utf-8')

        manifest = {
            'tool': TOOL_NAME,
            'toolVersion': TOOL_VERSION,
            'builtAt': time.strftime('%Y-%m-%d %H:%M:%S'),
            'library': {
                'path': lib['path'],
                'sha256': lib['sha256'],
                'size': lib['size'],
                'robotType': lib['robotType'],
                'programName': lib['programName'],
                'defs': [{'name': d['name'], 'args': d['args'],
                          'blockType': d['blockType']} for d in lib['defs']],
            },
            'prelude': {'sha256': sha256_text(prelude), 'chars': len(prelude)},
            'sourceAssets': {'path': source_assets, 'sha256': src_sha, 'size': src_size},
            'entries': {},
        }
        for key in (KEY_HTML, KEY_JS, KEY_USERLIB):
            data = name_to_data[key]
            manifest['entries'][key] = {'size': len(data),
                                        'sha256': hashlib.sha256(data).hexdigest()}
        manifest_text = json.dumps(manifest, ensure_ascii=False, indent=2) + '\n'
        name_to_data[KEY_MANIFEST] = manifest_text.encode('utf-8')

        entries = [dict(e) for e in info['entries']]
        entries.append({'name': KEY_USERLIB, 'offset': 0, 'length': 0})
        entries.append({'name': KEY_MANIFEST, 'offset': 0, 'length': 0})
        log('  · 打包补丁资源包 …')
        packed = _pack_zfb(entries, name_to_data, out_assets)

        log('  · 校验补丁包（只允许 2 改 + 2 增）…')
        check = verify_package(out_assets, source_assets)
        if not check['ok']:
            raise RuntimeError('补丁包自检失败：\n' + '\n'.join(check['errors']))
        for item in check['changed']:
            log('    修改 %s（%d -> %d 字节）' % (item['name'], item['old_len'], item['new_len']))
        for name in check['added']:
            log('    新增 %s（%d 字节）' % (name, len(name_to_data[name])))
        log('    其余 %d 个条目逐字节不变' % check['unchanged'])

        result = {
            'ok': True,
            'toolVersion': TOOL_VERSION,
            'builtAt': manifest['builtAt'],
            'library': {'path': lib['path'], 'sha256': lib['sha256'],
                        'defs': [{'name': d['name'], 'args': d['args']} for d in lib['defs']]},
            'sourceAssets': {'path': source_assets, 'sha256': src_sha, 'size': src_size},
            'patchedAssets': {'path': out_assets, 'size': packed['size'],
                              'sha256': packed['sha256'], 'count': packed['count']},
            'manifest': manifest,
            'verify': check,
            'engine': engine,
            'workdir': workdir,
            'elapsedSec': round(time.time() - t_start, 1),
        }

        if prelude_cache:
            log('  · prelude 已另存：%s' % rel(prelude_cache))
        if web_out:
            log('  · 解包补丁资源包到 web 目录（供验证工具用）：%s' % rel(web_out))
            if os.path.isdir(web_out) and os.listdir(web_out):
                shutil.rmtree(web_out)
            pb.unpack_zfb(out_assets, web_out, force=True)
            result['webOut'] = os.path.abspath(web_out)
        if json_out:
            write_json(json_out, result)
        if write_manifest_path:
            write_json(os.path.join(workdir, 'build_report.json'), result)

        log('')
        log('完成：%s' % rel(out_assets))
        log('  大小 %s（原始 %s，增加 %s）'
            % (fmt_size(packed['size']), fmt_size(src_size),
               fmt_size(packed['size'] - src_size)))
        log('  sha256 %s' % packed['sha256'])
        log('  函数 %d 个；prelude %d 字符' % (len(lib['defs']), len(prelude)))
        log('  用时 %.1f 秒' % result['elapsedSec'])
        if temp_owner and not keep_work:
            shutil.rmtree(temp_owner, ignore_errors=True)
        return result
    finally:
        if temp_owner and keep_work:
            log('  · 临时目录保留：%s' % temp_owner)


# ---------------------------------------------------------------------------
# 备份 / 安装 / 还原 / 状态
# ---------------------------------------------------------------------------
def list_backups(backup_dir: str) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    if not os.path.isdir(backup_dir):
        return out
    for name in sorted(os.listdir(backup_dir)):
        if not (name.startswith('browser_assets.原始.') and name.endswith('.bin')):
            continue
        path = os.path.join(backup_dir, name)
        try:
            out.append({'path': path, 'size': os.path.getsize(path),
                        'sha256': sha256_file(path),
                        'mtime': time.strftime('%Y-%m-%d %H:%M:%S',
                                               time.localtime(os.path.getmtime(path)))})
        except OSError:
            continue
    return out


def backup_original(assets: str, backup_dir: str) -> Dict[str, Any]:
    sha = sha256_file(assets)
    os.makedirs(backup_dir, exist_ok=True)
    dest = os.path.join(backup_dir, 'browser_assets.原始.%s.bin' % sha[:12])
    if os.path.isfile(dest):
        return {'path': dest, 'created': False, 'sha256': sha,
                'size': os.path.getsize(dest)}
    log('  · 备份当前资源包到：%s' % rel(dest))
    shutil.copy2(assets, dest)
    if sha256_file(dest) != sha:
        raise RuntimeError('备份校验失败：%s' % dest)
    return {'path': dest, 'created': True, 'sha256': sha,
            'size': os.path.getsize(dest)}


def find_original_backup(backup_dir: str, prefer_sha: Optional[str] = None) -> Optional[Dict[str, Any]]:
    items = list_backups(backup_dir)
    if prefer_sha:
        for it in items:
            if it['sha256'] == prefer_sha:
                return it
    for it in items:
        if it['sha256'].lower() == ORIGINAL_ASSETS_SHA.lower():
            return it
    return items[0] if items else None


def atomic_replace(new_path: str, target_path: str) -> None:
    """把 new_path 原子替换到 target_path（同一磁盘上 os.replace）。"""
    target_dir = os.path.dirname(os.path.abspath(target_path))
    tmp = os.path.join(target_dir, '.browser_assets.new.%d.tmp' % os.getpid())
    try:
        shutil.copy2(new_path, tmp)
        with open(tmp, 'rb+') as f:
            os.fsync(f.fileno())
        os.replace(tmp, target_path)
    finally:
        if os.path.exists(tmp):
            try:
                os.remove(tmp)
            except OSError:
                pass


def assets_manifest(assets: str) -> Optional[Dict[str, Any]]:
    try:
        info = pb.read_zfb_index(assets, with_data=True)
        for e in info['entries']:
            if e['name'] == KEY_MANIFEST:
                raw = info['data'][e['offset']:e['offset'] + e['length']]
                return json.loads(raw.decode('utf-8'))
    except (ValueError, OSError, KeyError):
        return None
    return None


def do_status(assets: Optional[str] = None, library: Optional[str] = None,
              backup_dir: Optional[str] = None, json_out: Optional[str] = None,
              as_json: bool = False) -> Dict[str, Any]:
    assets = os.path.abspath(assets or DEFAULT_ASSETS)
    library = os.path.abspath(library or DEFAULT_LIBRARY)
    backup_dir = os.path.abspath(backup_dir or DEFAULT_BACKUP_DIR)
    result: Dict[str, Any] = {
        'assets': assets, 'library': library, 'backupDir': backup_dir,
        'assetsExists': os.path.isfile(assets), 'admin': is_admin(),
        'ideRunning': sorted(set(ide_running())), 'patched': False,
        'needSync': None, 'recommend': '', 'errors': [],
    }
    manifest = None
    if result['assetsExists']:
        result['assetsSize'] = os.path.getsize(assets)
        result['assetsSha256'] = sha256_file(assets)
        result['original'] = (result['assetsSha256'].lower() == ORIGINAL_ASSETS_SHA.lower())
        manifest = assets_manifest(assets)
    else:
        result['errors'].append('资源包不存在：%s' % assets)
    backups = list_backups(backup_dir)
    result['backups'] = [{'path': b['path'], 'size': b['size'],
                          'sha256': b['sha256'], 'mtime': b['mtime']} for b in backups]

    if manifest:
        result['patched'] = True
        lib_meta = manifest.get('library') or {}
        result['manifest'] = manifest
        result['patchedLibrary'] = {'sha256': lib_meta.get('sha256'),
                                    'defs': [d.get('name') for d in lib_meta.get('defs') or []]}
        result['builtAt'] = manifest.get('builtAt')
        # 与当前函数库比较
        if os.path.isfile(library):
            cur_sha = sha256_file(library)
            result['libraryExists'] = True
            result['librarySha256'] = cur_sha
            same_sha = cur_sha == lib_meta.get('sha256')
            defs_diff = None
            try:
                cur_defs = [d['name'] for d in load_library(library)['defs']]
                old_defs = [d.get('name') for d in lib_meta.get('defs') or []]
                defs_diff = {'old': old_defs, 'current': cur_defs,
                             'same': old_defs == cur_defs}
            except RuntimeError as exc:
                defs_diff = {'error': str(exc)}
            result['defsDiff'] = defs_diff
            result['needSync'] = (not same_sha) or bool(defs_diff.get('same') is False)
        else:
            result['libraryExists'] = False
            result['needSync'] = True
    else:
        result['needSync'] = True

    # 推荐下一步
    recs: List[str] = []
    if not result['assetsExists']:
        recs.append('找不到 browser_assets，请检查 --assets 或先安装 AbilixScratch3.0。')
    elif result['original'] and not result['patched']:
        recs.append('当前是原版资源包，还没有原生积木。下一步：'
                    '以管理员运行「安装原生积木.cmd」或用便携版。')
    elif result['patched'] and result['needSync']:
        recs.append('已打补丁，但函数库有变化（新增/删除/改名/改内容）。下一步：'
                    '关闭 IDE 后以管理员运行「安装原生积木.cmd」重新编译安装。')
    elif result['patched'] and not result['needSync']:
        recs.append('已是最新（原生积木与函数库同步）。打开 IDE 即可在左侧「我的函数」分类里拖拽。')
    elif not result['original'] and not result['patched']:
        recs.append('资源包既不是原版也不是本工具补丁（可能被其他工具改过）。'
                    '建议用备份恢复，或确认来源后再操作。')
    if result['ideRunning']:
        recs.append('注意：IDE 正在运行（%s），安装/还原前请先关闭。'
                    % '、'.join(result['ideRunning']))
    if backups:
        recs.append('可用备份 %d 份（最新：%s）。' % (len(backups), rel(backups[0]['path'])))
    else:
        recs.append('还没有原始资源包备份；安装时会在 %s 自动创建。' % rel(backup_dir))
    if not result['admin']:
        recs.append('当前不是管理员：安装/还原需要管理员权限（UAC 弹窗需你点“是”）。')
    result['recommend'] = '\n'.join(recs)

    if json_out:
        write_json(json_out, result)
    if as_json:
        log(json.dumps(result, ensure_ascii=False, indent=2))
        return result

    log('=' * 78)
    log('原生积木状态')
    log('=' * 78)
    log('  资源包      : %s' % assets)
    if result['assetsExists']:
        log('  大小/hash   : %s / %s' % (fmt_size(result['assetsSize']),
                                        result['assetsSha256']))
    else:
        log('  大小/hash   : （文件不存在）')
    log('  管理员      : %s' % ('是' if result['admin'] else '否（安装/还原需要管理员）'))
    log('  IDE 运行    : %s' % ('、'.join(result['ideRunning']) if result['ideRunning'] else '否'))
    if result['patched']:
        lib_meta = (manifest or {}).get('library') or {}
        log('  原生积木    : 已打补丁  v%s  %s' % ((manifest or {}).get('toolVersion'),
                                                   (manifest or {}).get('builtAt')))
        log('  补丁时函数库: %s  hash=%s' % (lib_meta.get('path'),
                                            str(lib_meta.get('sha256'))[:16] + '…'))
        log('  补丁时函数  : %s' % '、'.join(d.get('name') for d in lib_meta.get('defs') or []))
        if result.get('libraryExists'):
            log('  当前函数库  : %s  hash=%s' % (library, result['librarySha256'][:16] + '…'))
            log('  是否需要重装: %s' % ('是（函数库有变化）' if result['needSync'] else '否（已同步）'))
            dd = result.get('defsDiff') or {}
            if dd.get('same') is False:
                log('    函数变化  : 原来 %s' % ('、'.join(dd['old']) or '（无）'))
                log('                现在 %s' % ('、'.join(dd['current']) or '（无）'))
            if dd.get('error'):
                log('    函数库解析: 失败：%s' % dd['error'])
        else:
            log('  当前函数库  : 不存在（%s）' % library)
    elif result['original']:
        log('  原生积木    : 未打补丁（原版资源包）')
    else:
        log('  原生积木    : 未识别（不是原版，也没有本工具清单）')
    log('  备份        : %d 份' % len(result['backups']))
    for b in result['backups'][:5]:
        log('    - %s  %s  %s' % (rel(b['path']), fmt_size(b['size']), b['sha256'][:16] + '…'))
    log('')
    log('建议：')
    for line in result['recommend'].splitlines():
        log('  ' + line)
    log('')
    return result


def _zfb_entry_bytes(info: Dict[str, Any], name: str) -> bytes:
    for e in info['entries']:
        if e['name'] == name:
            return info['data'][e['offset']:e['offset'] + e['length']]
    raise RuntimeError('补丁包里缺少条目：%s' % name)


def install_from_prebuilt(assets: str, prebuilt: str, backup_dir: str,
                          dry_run: bool = False,
                          json_out: Optional[str] = None) -> Dict[str, Any]:
    """用预编译好的补丁包完成安装（不调用浏览器，也不重新编译）。"""
    prebuilt = os.path.abspath(prebuilt)
    if not os.path.isfile(prebuilt):
        raise RuntimeError('找不到预编译补丁包：%s\n'
                           '请重新运行「安装原生积木.cmd」（它会先在普通权限下编译）。' % prebuilt)
    if assets_manifest(assets):
        raise RuntimeError('当前资源包已经打过补丁。\n'
                           '请先运行「还原原版.cmd」，再重新安装。')
    log('  · 预编译安装：跳过浏览器引擎，直接校验并替换。')
    log('    补丁包：%s（%s）' % (rel(prebuilt), fmt_size(os.path.getsize(prebuilt))))
    info = pb.read_zfb_index(prebuilt, with_data=True)
    names = [e['name'] for e in info['entries']]
    for key in (KEY_USERLIB, KEY_MANIFEST):
        if key not in names:
            raise RuntimeError('这不是本工具生成的补丁包（缺少 %s）。请重新编译。' % key)
    try:
        manifest = json.loads(_zfb_entry_bytes(info, KEY_MANIFEST).decode('utf-8'))
    except (ValueError, KeyError) as exc:
        raise RuntimeError('补丁包清单损坏：%s' % exc)
    target_sha = sha256_file(assets)
    src_sha = str((manifest.get('sourceAssets') or {}).get('sha256') or '')
    if src_sha.lower() != target_sha.lower():
        raise RuntimeError('补丁包与当前安装的资源包不匹配（补丁包基准 %s，当前 %s）。\n'
                           '请重新运行安装脚本，不要在别的电脑上使用这个补丁包。'
                           % (src_sha[:16] + '…', target_sha[:16] + '…'))
    v = verify_package(prebuilt, assets)
    if not v['ok']:
        raise RuntimeError('补丁包自检失败：' + '；'.join(v['errors']))
    backup = backup_original(assets, backup_dir)
    log('    备份：%s（%s）' % (rel(backup['path']), fmt_size(backup['size'])))
    log('  · 替换安装目录资源包（原子替换）…')
    atomic_replace(prebuilt, assets)
    new_sha = sha256_file(assets)
    if new_sha.lower() != sha256_file(prebuilt).lower():
        raise RuntimeError('安装后校验失败：目标文件 hash 与补丁包不一致。')
    if not assets_manifest(assets):
        raise RuntimeError('安装后校验失败：资源包里读不到补丁清单。')
    lib_meta = manifest.get('library') or {}
    defs = [d.get('name') for d in (lib_meta.get('defs') or [])]
    result = {
        'ok': True,
        'install': {
            'assets': assets,
            'dryRun': dry_run,
            'mode': 'prebuilt',
            'prebuilt': prebuilt,
            'beforeSha256': target_sha,
            'afterSha256': new_sha,
            'manifestReadBack': True,
            'backupDir': backup_dir,
        },
        'library': lib_meta,
        'patchedAssets': {'path': assets, 'size': os.path.getsize(assets),
                          'sha256': new_sha},
    }
    log('')
    log('安装完成 ✔' + ('（演练：未改动真实安装目录）' if dry_run else ''))
    log('  资源包：%s' % rel(assets))
    log('  大小  ：%s' % fmt_size(os.path.getsize(assets)))
    log('  sha256：%s' % new_sha)
    log('  函数  ：%d 个（%s）' % (len(defs), '、'.join(defs)))
    log('  打开 IDE → 左侧「我的函数」分类 → 拖积木。')
    log('  还原方法：以管理员运行「还原原版.cmd」（备份在 %s）。' % rel(backup_dir))
    if json_out:
        write_json(json_out, result)
    return result


def do_install(assets: str, library: str, backup_dir: str,
               source_assets: Optional[str] = None,
               workdir: Optional[str] = None, force: bool = False,
               json_out: Optional[str] = None,
               prelude_in: Optional[str] = None,
               dry_run: bool = False,
               compile_only: Optional[str] = None,
               prebuilt: Optional[str] = None) -> Dict[str, Any]:
    assets = os.path.abspath(assets)
    library = os.path.abspath(library)
    backup_dir = os.path.abspath(backup_dir)
    log('=' * 78)
    log('原生积木：安装到 IDE' + ('（演练 dry-run，不改安装目录）' if dry_run else ''))
    log('=' * 78)
    real_assets = assets
    if os.name != 'nt':
        raise RuntimeError('安装步骤只支持 Windows。')
    if not dry_run and not compile_only and not is_admin():
        raise RuntimeError('需要管理员权限。\n'
                           '请右键「安装原生积木.cmd」→ 以管理员身份运行；'
                           '或在开始菜单搜索“命令提示符”→“以管理员身份运行”后执行。')
    if not os.path.isfile(assets):
        raise RuntimeError('找不到资源包：%s\n请确认 AbilixScratch3.0 安装路径（--assets）。' % assets)
    if dry_run:
        dry_dir = tempfile.mkdtemp(prefix='wer_native_install_dry_')
        os.makedirs(dry_dir, exist_ok=True)
        assets = os.path.join(dry_dir, 'browser_assets')
        log('  · 演练：复制资源包到临时目录 %s' % assets)
        shutil.copy2(real_assets, assets)
        backup_dir = os.path.join(dry_dir, 'backup')
        workdir = workdir or os.path.join(dry_dir, 'work')
    else:
        ensure_no_ide(force)

    if prebuilt:
        return install_from_prebuilt(assets=assets, prebuilt=prebuilt,
                                     backup_dir=backup_dir, dry_run=dry_run,
                                     json_out=json_out)

    existing = assets_manifest(assets)
    if existing:
        # 已打过补丁：用备份的原始包重新编译，避免二次打补丁
        if source_assets:
            src = os.path.abspath(source_assets)
        else:
            b = find_original_backup(backup_dir)
            if not b and not force:
                raise RuntimeError('当前资源包已打过补丁，却找不到原始包备份（%s）。\n'
                                   '请用 --source-assets 指定原始 browser_assets，或 restore 后再装。'
                                   % backup_dir)
            src = b['path'] if b else None
        log('  · 当前已是补丁版；将以原始包为基准重新编译：%s' % rel(src))
    else:
        src = os.path.abspath(source_assets) if source_assets else assets
        log('  · 当前是未打补丁的资源包；先备份再编译。')
        backup = backup_original(src, backup_dir)
        log('    备份：%s（%s）' % (rel(backup['path']), fmt_size(backup['size'])))

    if compile_only:
        out = os.path.abspath(compile_only)
        os.makedirs(os.path.dirname(out) or '.', exist_ok=True)
        result = do_build(library=library, source_assets=src, out_assets=out,
                          workdir=workdir or os.path.join(DEFAULT_WORK_PARENT,
                                                          'prepare_%s' % time.strftime('%Y%m%d_%H%M%S')),
                          prelude_in=prelude_in, write_manifest_path=True)
        log('')
        log('补丁包已生成 ✔（未写入安装目录）')
        log('  补丁包：%s' % rel(out))
        log('  大小  ：%s' % fmt_size(os.path.getsize(out)))
        log('  sha256：%s' % result['patchedAssets']['sha256'])
        log('  函数  ：%d 个（%s）' % (len(result['library']['defs']),
                                      '、'.join(d['name'] for d in result['library']['defs'])))
        if json_out:
            write_json(json_out, result)
        return result

    temp_out = os.path.join(os.path.dirname(assets), '.browser_assets.wer_native.%d.tmp'
                            % os.getpid())
    try:
        result = do_build(library=library, source_assets=src, out_assets=temp_out,
                          workdir=workdir or os.path.join(DEFAULT_WORK_PARENT,
                                                          'install_%s' % time.strftime('%Y%m%d_%H%M%S')),
                          prelude_in=prelude_in, write_manifest_path=True)
        old_sha = sha256_file(assets)
        log('  · 替换安装目录资源包（原子替换）…')
        atomic_replace(temp_out, assets)
        new_sha = sha256_file(assets)
        if new_sha != result['patchedAssets']['sha256']:
            raise RuntimeError('安装后校验失败：目标文件 hash 与补丁包不一致。')
        manifest = assets_manifest(assets)
        if not manifest:
            raise RuntimeError('安装后校验失败：资源包里读不到补丁清单。')
        result['install'] = {
            'assets': assets,
            'realAssets': real_assets,
            'dryRun': dry_run,
            'beforeSha256': old_sha,
            'afterSha256': new_sha,
            'manifestReadBack': True,
            'backupDir': backup_dir,
        }
        log('')
        log('安装完成 ✔' + ('（演练：未改动真实安装目录）' if dry_run else ''))
        log('  资源包：%s' % rel(assets))
        log('  大小  ：%s' % fmt_size(os.path.getsize(assets)))
        log('  sha256：%s' % new_sha)
        log('  函数  ：%d 个（%s）' % (len(result['library']['defs']),
                                      '、'.join(d['name'] for d in result['library']['defs'])))
        log('  打开 IDE → 左侧「我的函数」分类 → 拖积木。')
        log('  还原方法：以管理员运行「还原原版.cmd」（备份在 %s）。' % rel(backup_dir))
        if json_out:
            write_json(json_out, result)
        if dry_run:
            shutil.rmtree(dry_dir, ignore_errors=True)
            log('  （演练临时目录已清理：%s）' % dry_dir)
        return result
    finally:
        if os.path.exists(temp_out):
            try:
                os.remove(temp_out)
            except OSError:
                pass


def do_restore(assets: str, backup_dir: str, force: bool = False,
               json_out: Optional[str] = None,
               from_backup: Optional[str] = None,
               dry_run: bool = False) -> Dict[str, Any]:
    assets = os.path.abspath(assets)
    backup_dir = os.path.abspath(backup_dir)
    log('=' * 78)
    log('原生积木：还原原版资源包' + ('（演练 dry-run，不改安装目录）' if dry_run else ''))
    log('=' * 78)
    real_assets = assets
    if os.name != 'nt':
        raise RuntimeError('还原步骤只支持 Windows。')
    if not dry_run and not is_admin():
        raise RuntimeError('需要管理员权限。请右键「还原原版.cmd」→ 以管理员身份运行。')
    if not os.path.isfile(assets):
        raise RuntimeError('找不到资源包：%s' % assets)
    if dry_run:
        dry_dir = tempfile.mkdtemp(prefix='wer_native_restore_dry_')
        assets = os.path.join(dry_dir, 'browser_assets')
        shutil.copy2(real_assets, assets)
        if not from_backup:
            backup_dir = os.path.join(dry_dir, 'backup')
        log('  · 演练：复制资源包到临时目录 %s' % assets)
    else:
        ensure_no_ide(force)
    if from_backup:
        src = os.path.abspath(from_backup)
        if not os.path.isfile(src):
            raise RuntimeError('指定的备份不存在：%s' % src)
    else:
        b = find_original_backup(backup_dir)
        if not b:
            raise RuntimeError('没有找到原始资源包备份（%s）。\n'
                               '如果安装过本工具，备份应在 %s；也可以 --from-backup 指定。'
                               % (backup_dir, backup_dir))
        src = b['path']
    src_sha = sha256_file(src)
    if src_sha.lower() != ORIGINAL_ASSETS_SHA.lower() and not force:
        raise RuntimeError('这份备份的 hash 与本机记录的原始资源包不一致（%s）。\n'
                           '如果确认它就是你想要的版本，加 --force。' % src_sha[:16])
    old_sha = sha256_file(assets)
    log('  · 用备份替换：%s' % rel(src))
    atomic_replace(src, assets)
    new_sha = sha256_file(assets)
    result = {'ok': True, 'assets': assets, 'realAssets': real_assets,
              'dryRun': dry_run, 'beforeSha256': old_sha,
              'afterSha256': new_sha, 'from': src,
              'restoredOriginal': new_sha.lower() == ORIGINAL_ASSETS_SHA.lower()}
    log('还原完成 ✔' + ('（演练：未改动真实安装目录）' if dry_run else ''))
    log('  资源包：%s' % rel(assets))
    log('  sha256：%s %s' % (new_sha, '（与本机记录的原始包一致）'
                              if result['restoredOriginal'] else '（⚠ 不是记录的原始包）'))
    if json_out:
        write_json(json_out, result)
    if dry_run:
        shutil.rmtree(dry_dir, ignore_errors=True)
        log('  （演练临时目录已清理：%s）' % dry_dir)
    return result


# ---------------------------------------------------------------------------
# 便携版辅助：导出最小引擎（可选）
# ---------------------------------------------------------------------------
def do_extract_web(assets: str, out_dir: str) -> Dict[str, Any]:
    assets = os.path.abspath(assets)
    out_dir = os.path.abspath(out_dir)
    log('解包资源包：%s -> %s' % (rel(assets), rel(out_dir)))
    info = pb.unpack_zfb(assets, out_dir, force=True)
    log('完成：%d 个条目' % info['written'])
    return info


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def add_common_paths(p: argparse.ArgumentParser) -> None:
    p.add_argument('--assets', default=DEFAULT_ASSETS,
                   help='browser_assets 路径（默认：%s）' % DEFAULT_ASSETS)
    p.add_argument('--library', default=DEFAULT_LIBRARY,
                   help='函数库 .srhs/.srh 路径（默认：%s）' % DEFAULT_LIBRARY)
    p.add_argument('--backup-dir', default=DEFAULT_BACKUP_DIR,
                   help='原始资源包备份目录（默认：%s）' % DEFAULT_BACKUP_DIR)
    p.add_argument('--json-out', help='把结果 JSON 写到该文件')
    p.add_argument('--json', dest='as_json', action='store_true',
                   help='在标准输出打印 JSON')


def build_arg_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        prog='原生积木核心.py',
        description='把 WER 函数库编译成 AbilixScratch3.0 内部的原生积木块。',
        formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='command', required=True, metavar='<命令>')

    p = sub.add_parser('build', help='编译函数库 -> 输出打过补丁的 browser_assets')
    p.add_argument('--library', default=DEFAULT_LIBRARY, help='函数库 .srhs/.srh')
    p.add_argument('--source-assets', required=True,
                   help='原始（未打补丁的）browser_assets 路径')
    p.add_argument('--out', required=True, help='输出补丁包路径（.bin）')
    p.add_argument('--workdir', help='临时工作目录（默认建在 %s）' % DEFAULT_WORK_PARENT)
    p.add_argument('--keep-work', action='store_true', help='保留临时工作目录')
    p.add_argument('--prelude-out', help='把提取出的函数定义 prelude 另存到该文件')
    p.add_argument('--prelude-in', help='跳过真实引擎，直接使用该 prelude 文件（高级用法）')
    p.add_argument('--web-out', help='把补丁资源包解包到该目录（给验证工具/调试用）')
    p.add_argument('--json-out', help='把构建结果 JSON 写到该文件')
    p.add_argument('--timeout', type=float, default=300.0, help='单次 Chrome 超时秒数')

    p = sub.add_parser('install', help='备份并安装到真实 IDE（需要管理员）')
    add_common_paths(p)
    p.add_argument('--source-assets', help='原始资源包路径（默认自动使用备份）')
    p.add_argument('--workdir', help='临时工作目录')
    p.add_argument('--prelude-in', help='直接使用该 prelude 文件（高级用法）')
    p.add_argument('--force', action='store_true', help='IDE 在运行时也强制继续')
    p.add_argument('--dry-run', action='store_true',
                   help='演练：在临时副本上走完整安装流程，不碰真实安装目录')
    p.add_argument('--compile-only', metavar='输出补丁包',
                   help='只编译出补丁包，不写入安装目录（普通权限即可）')
    p.add_argument('--prebuilt', metavar='补丁包',
                   help='用预编译补丁包直接安装（跳过编译与浏览器；两段式安装脚本使用）')

    p = sub.add_parser('restore', help='用备份恢复原版资源包（需要管理员）')
    add_common_paths(p)
    p.add_argument('--from-backup', help='指定要恢复的备份文件')
    p.add_argument('--force', action='store_true',
                   help='备份 hash 与记录不一致/IDE 在运行时也继续')
    p.add_argument('--dry-run', action='store_true',
                   help='演练：在临时副本上走完整还原流程，不碰真实安装目录')

    p = sub.add_parser('status', help='检查补丁状态、是否需要重装、备份情况')
    add_common_paths(p)

    p = sub.add_parser('verify', help='校验补丁包只改了预期条目')
    p.add_argument('--file', required=True, help='补丁包 browser_assets')
    p.add_argument('--original', required=True, help='原始 browser_assets')
    p.add_argument('--json-out', help='把结果 JSON 写到该文件')
    p.add_argument('--json', dest='as_json', action='store_true', help='打印 JSON')

    p = sub.add_parser('extract-web', help='把资源包解包成 web 目录（调试/验证用）')
    p.add_argument('--assets', default=DEFAULT_ASSETS)
    p.add_argument('--out', required=True)

    return ap


def main(argv: Optional[Sequence[str]] = None) -> int:
    st.setup_console()
    ap = build_arg_parser()
    args = ap.parse_args(argv)
    try:
        if args.command == 'build':
            do_build(library=args.library, source_assets=args.source_assets,
                     out_assets=args.out, workdir=args.workdir,
                     keep_work=args.keep_work, prelude_cache=args.prelude_out,
                     prelude_in=args.prelude_in, web_out=args.web_out,
                     json_out=args.json_out, timeout=args.timeout)
            return 0
        if args.command == 'install':
            do_install(assets=args.assets, library=args.library,
                       backup_dir=args.backup_dir, source_assets=args.source_assets,
                       workdir=args.workdir, force=args.force,
                       json_out=args.json_out, prelude_in=args.prelude_in,
                       dry_run=args.dry_run, compile_only=args.compile_only,
                       prebuilt=args.prebuilt)
            return 0
        if args.command == 'restore':
            do_restore(assets=args.assets, backup_dir=args.backup_dir,
                       force=args.force, json_out=args.json_out,
                       from_backup=args.from_backup, dry_run=args.dry_run)
            return 0
        if args.command == 'status':
            r = do_status(assets=args.assets, library=args.library,
                          backup_dir=args.backup_dir, json_out=args.json_out,
                          as_json=args.as_json)
            return 0 if not r['errors'] else 1
        if args.command == 'verify':
            r = verify_package(args.file, args.original)
            if args.json_out:
                write_json(args.json_out, r)
            if args.as_json:
                log(json.dumps(r, ensure_ascii=False, indent=2))
            else:
                log('校验结果：%s' % ('通过 ✔' if r['ok'] else '失败 ✘'))
                for line in r['errors']:
                    log('  ✘ ' + line)
                for item in r['changed']:
                    log('  修改 %s（%d -> %d 字节）'
                        % (item['name'], item['old_len'], item['new_len']))
                for name in r['added']:
                    log('  新增 %s' % name)
                log('  其余 %d 个条目逐字节不变' % r['unchanged'])
            return 0 if r['ok'] else 1
        if args.command == 'extract-web':
            do_extract_web(args.assets, args.out)
            return 0
        ap.error('未知命令')
        return 2
    except (RuntimeError, ValueError, OSError) as exc:
        log('')
        log('✘ 失败：%s' % exc)
        return 2


if __name__ == '__main__':
    sys.exit(main())
