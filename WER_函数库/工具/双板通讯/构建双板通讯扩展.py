# -*- coding: utf-8 -*-
r"""构建「双板通讯」原生积木扩展补丁包。

输入
  · 本机原版资源包备份  工具/原生积木/备份/browser_assets.原始.df6db241752d.bin
  · 当前已安装的资源包  D:\Program Files\AbilixScratch3.0\...\browser_assets（读取其中的"我的函数"prelude）
  · 双板通讯 prelude    双板通讯研究/实验/实验19_双板通讯积木原型/wl_prelude.py

输出（默认写到 WER_函数库/安装包_双板通讯/）
  · browser_assets.patched        新补丁包（原版 4 条目补丁 + 3 个双板通讯积木 + prelude 追加）
  · install_dual.cmd / .ps1      安装脚本（自动请求管理员权限；先备份；失败自动回滚）
  · restore_dual.cmd / .ps1      还原脚本
  · 安装信息.txt                  本次构建的 sha256/大小/条目说明
用法
  py -3 构建双板通讯扩展.py [--assets <已安装路径>] [--orig <原版备份>] [--out <输出目录>]
"""
from __future__ import print_function

import argparse
import hashlib
import importlib.util
import json
import os
import re
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
TOOL_DIR = os.path.dirname(HERE)                       # WER_函数库/工具
LIB_ROOT = os.path.dirname(TOOL_DIR)                   # WER_函数库
REPO_ROOT = os.path.dirname(LIB_ROOT)                  # 工作区根
BOTTOM_DIR = os.path.join(TOOL_DIR, '底层')
NATIVE_DIR = os.path.join(TOOL_DIR, '原生积木')

DEFAULT_ORIG = os.path.join(NATIVE_DIR, '备份', 'browser_assets.原始.df6db241752d.bin')
DEFAULT_ASSETS = r'D:\Program Files\AbilixScratch3.0\AbilixScratch3.0_Data\Resources\browser_assets'
DEFAULT_OUT = os.path.join(LIB_ROOT, '安装包_双板通讯')
PRELUDE_FILE = os.path.join(REPO_ROOT, '双板通讯研究', '实验', '实验19_双板通讯积木原型', 'wl_prelude.py')
CORE_FILE = os.path.join(NATIVE_DIR, '原生积木核心.py')
PB_FILE = os.path.join(BOTTOM_DIR, 'patch_browser_assets.py')
LIBRARY_FILE = os.path.join(LIB_ROOT, '我的函数库.srhs')

CAT_NAME_DUAL = '双板通讯'
CAT_COLOUR_DUAL = '#FF6680'

DUAL_BLOCK_JS = r'''/* ===== 双板通讯（WER 双板通讯扩展，自动生成，勿手改）===== */
(function () {
  var DUAL_COLOUR = 210;

  Blockly.Blocks["abilixuf_dk_setip"] = {
    init: function () {
      this.appendDummyInput()
          .appendField("设置对方主板 IP")
          .appendField(new Blockly.FieldTextInput("192.168.1.103"), "IP");
      this.setPreviousStatement(true, null);
      this.setNextStatement(true, null);
      this.setColour(DUAL_COLOUR);
      this.setTooltip("双板通讯：设置对方主板的 IP 地址（只做配置，不发送数据）");
      this.setHelpUrl("");
    }
  };
  Blockly.Python["abilixuf_dk_setip"] = function (block) {
    var ip = String(block.getFieldValue("IP"));
    ip = ip.replace(/['"\\\r\n]/g, "");
    return "_wl_set_ip('" + ip + "')\n";
  };

  Blockly.Blocks["abilixuf_dk_send"] = {
    init: function () {
      this.appendValueInput("VAL").setCheck(null).appendField("发送");
      this.appendDummyInput()
          .appendField("到地址")
          .appendField(new Blockly.FieldTextInput("1"), "ADDR");
      this.setPreviousStatement(true, null);
      this.setNextStatement(true, null);
      this.setColour(DUAL_COLOUR);
      this.setTooltip("双板通讯：把信息发送到对方主板的指定地址（数字）");
      this.setHelpUrl("");
    }
  };
  Blockly.Python["abilixuf_dk_send"] = function (block) {
    var v = Blockly.Python.valueToCode(block, "VAL", Blockly.Python.ORDER_NONE) || "0";
    var a = String(block.getFieldValue("ADDR"));
    a = a.replace(/[^0-9]/g, "") || "0";
    return "_wl_send(" + a + ", " + v + ")\n";
  };

  Blockly.Blocks["abilixuf_dk_recv"] = {
    init: function () {
      this.appendDummyInput()
          .appendField("接收地址")
          .appendField(new Blockly.FieldTextInput("1"), "ADDR")
          .appendField("的信息");
      this.setOutput(true, null);
      this.setColour(DUAL_COLOUR);
      this.setTooltip("双板通讯：读取对方主板某个地址最新发来的信息（数字，没有收到时是 0）");
      this.setHelpUrl("");
    }
  };
  Blockly.Python["abilixuf_dk_recv"] = function (block) {
    var a = String(block.getFieldValue("ADDR"));
    a = a.replace(/[^0-9]/g, "") || "0";
    return ["_wl_recv(" + a + ")", Blockly.Python.ORDER_ATOMIC];
  };

  Blockly.Blocks["abilixuf_dk_save"] = {
    init: function () {
      this.appendDummyInput()
          .appendField("把地址")
          .appendField(new Blockly.FieldTextInput("1"), "ADDR")
          .appendField("的信息保存到读写数据");
      this.setPreviousStatement(true, null);
      this.setNextStatement(true, null);
      this.setColour(DUAL_COLOUR);
      this.setTooltip("双板通讯：把该地址当前的值写入主板的“读写数据”（掉电不丢）");
      this.setHelpUrl("");
    }
  };
  Blockly.Python["abilixuf_dk_save"] = function (block) {
    var a = String(block.getFieldValue("ADDR"));
    a = a.replace(/[^0-9]/g, "") || "0";
    return "_wl_save_ee(" + a + ")\n";
  };
})();
'''

DUAL_CAT_XML = '''   <category name="%s" colour="%s">
      <sep gap="8"></sep>
      <block type="abilixuf_dk_setip"><field name="IP">192.168.1.103</field></block>
      <sep gap="8"></sep>
      <block type="abilixuf_dk_send"><value name="VAL"><shadow type="math_number"><field name="NUM">0</field></shadow></value><field name="ADDR">1</field></block>
      <sep gap="8"></sep>
      <block type="abilixuf_dk_recv"><field name="ADDR">1</field></block>
      <sep gap="8"></sep>
      <block type="abilixuf_dk_save"><field name="ADDR">1</field></block>
      <sep gap="8"></sep>
   </category>''' % (CAT_NAME_DUAL, CAT_COLOUR_DUAL)

DUAL_DEFS = [
    {'name': 'dk_setip', 'args': [], 'blockType': 'abilixuf_dk_setip',
     'tip': '设置对方主板 IP（双板通讯）'},
    {'name': 'dk_send', 'args': ['信息'], 'blockType': 'abilixuf_dk_send',
     'tip': '发送信息到对方主板某地址（双板通讯）'},
    {'name': 'dk_recv', 'args': ['地址'], 'blockType': 'abilixuf_dk_recv',
     'tip': '接收对方主板某地址的信息（双板通讯）'},
    {'name': 'dk_save', 'args': ['地址'], 'blockType': 'abilixuf_dk_save',
     'tip': '把该地址当前值保存到“读写数据”（掉电不丢，双板通讯）'},
]


# ---------------------------------------------------------------------------
# 基础工具
# ---------------------------------------------------------------------------
def sha256_file(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def sha256_text(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def log(msg=''):
    print(msg)


# ---------------------------------------------------------------------------
# 读取「当前已安装补丁」里的 prelude / 函数元数据（复用用户已有的「我的函数」）
# ---------------------------------------------------------------------------
def read_userlib_from_assets(pb, assets_path):
    info = pb.read_zfb_index(assets_path, with_data=True)
    names = [e['name'] for e in info['entries']]

    def get(name):
        for e in info['entries']:
            if e['name'] == name:
                return info['data'][e['offset']:e['offset'] + e['length']]
        raise RuntimeError('资源包里没有条目 %s' % name)

    js = get('/Blockly_Code/abilix_userlib.js').decode('utf-8')
    m = re.search(r'var abilixUserLibPython = (.*?);\r?\nvar abilixUserLib = (.*?);\r?\n', js, re.S)
    if not m:
        raise RuntimeError('已安装补丁里找不到 abilixUserLibPython / abilixUserLib（不是本工具生成的补丁？）')
    prelude = json.loads(m.group(1).replace('<\\/', '</'))
    meta = json.loads(m.group(2).replace('<\\/', '</'))
    return prelude, meta, js


# ---------------------------------------------------------------------------
# 打补丁（只在原版资源包基础上改 2 个条目、新增 2 个条目）
# ---------------------------------------------------------------------------
def patch_html_dual(html, combined_category_xml):
    if core.SCRIPT_TAG in html:
        raise RuntimeError('maingui.html 里已经存在 abilix_userlib.js 脚本行：请用原版资源包作为基准。')
    if html.count(core.SCRIPT_ANCHOR) != 1:
        raise RuntimeError('maingui.html 里 myrobotpythoncode 脚本行数量异常：%d' % html.count(core.SCRIPT_ANCHOR))
    html = html.replace(core.SCRIPT_ANCHOR, core.SCRIPT_ANCHOR + '\n  ' + core.SCRIPT_TAG, 1)

    out = []
    pos = 0
    inserted = 0
    for m in re.finditer(r'<xml id="(toolbox_skcon\d)"[^>]*>', html):
        start = m.start()
        close = html.find('</xml>', start)
        if close < 0:
            # 原版 maingui.html 里 toolbox_skcon2 没有 </xml>（靠 </body> 前的 HTML 自动闭合），
            # 与官方工具 patch_html 一致：退回到 </body> 前插入，插入内容仍在未闭合的 <xml> 元素内部。
            close = html.find('</body>', start)
            if close < 0:
                raise RuntimeError('找不到工具箱 %s 的结束位置' % m.group(1))
        out.append(html[pos:close])
        out.append(combined_category_xml + '\n  ')
        pos = close
        inserted += 1
    out.append(html[pos:])
    if inserted != 3:
        raise RuntimeError('预期给 3 个机器人工具箱加分类，实际找到 %d 个' % inserted)
    patched = ''.join(out)
    if patched.count('name="%s"' % CAT_NAME_DUAL) != 3:
        raise RuntimeError('双板通讯分类插入数量异常')
    if patched.count('name="%s"' % core.CATEGORY_NAME) != 3:
        raise RuntimeError('我的函数分类插入数量异常')
    return patched


# ---------------------------------------------------------------------------
# 安装/还原脚本模板
# ---------------------------------------------------------------------------
INSTALL_PS1 = r'''# 双板通讯原生积木扩展 —— 安装脚本（自动生成，勿手改）
param([string]$Target = '__TARGET__')
$ErrorActionPreference = 'Stop'
$PATCH_DIR = Split-Path -Parent $MyInvocation.MyCommand.Path
$PREBUILT = Join-Path $PATCH_DIR 'browser_assets.patched'
$ORIG_SHA = '__ORIG_SHA__'
$OLD_SHA = '__OLD_SHA__'
$NEW_SHA = '__NEW_SHA__'
$BACKUP_DIR = Join-Path (Split-Path -Parent $PATCH_DIR) '工具\原生积木\备份'

function Stop-WithMessage([string]$msg) {
  Write-Host ''
  Write-Host $msg -ForegroundColor Yellow
  Write-Host ''
  Read-Host '按回车键关闭窗口' | Out-Null
  exit 1
}

$principal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
  Write-Host '需要管理员权限，正在请求提升…'
  $argline = '-NoProfile -ExecutionPolicy Bypass -File "{0}" -Target "{1}"' -f $MyInvocation.MyCommand.Path, $Target
  Start-Process powershell.exe -Verb RunAs -ArgumentList $argline | Out-Null
  exit 0
}

Write-Host '=========================================='
Write-Host '  双板通讯原生积木 · 安装'
Write-Host '=========================================='

$ide = @(Get-Process -ErrorAction SilentlyContinue | Where-Object { $_.ProcessName -like 'AbilixScratch*' })
if ($ide.Count -gt 0) {
  Stop-WithMessage ('请先完全关闭 AbilixScratch3.0 再安装（正在运行：' + (($ide | ForEach-Object { $_.ProcessName }) -join ', ') + '）')
}

if (-not (Test-Path $Target)) { Stop-WithMessage "找不到资源包：$Target" }
if (-not (Test-Path $PREBUILT)) { Stop-WithMessage "找不到补丁包：$PREBUILT" }

function Get-SHA256([string]$p) {
  $fs = [System.IO.File]::OpenRead($p)
  try {
    $sha = [System.Security.Cryptography.SHA256]::Create()
    $bytes = $sha.ComputeHash($fs)
    return ([System.BitConverter]::ToString($bytes) -replace '-', '').ToLower()
  } finally { $fs.Close() }
}

$cur = Get-SHA256 $Target
$new = Get-SHA256 $PREBUILT
Write-Host "当前资源包 sha256：$cur"
Write-Host "补丁包   sha256：$new"
if ($new -ne $NEW_SHA) { Stop-WithMessage '补丁包被改动过（sha 不符）。' }
if ($cur -eq $NEW_SHA) { Stop-WithMessage '当前已经装好双板通讯版本，无需重复安装。' }
if ($cur -ne $ORIG_SHA -and $cur -ne $OLD_SHA) {
  Stop-WithMessage ("当前资源包既不是原版也不是已知的旧补丁版，为安全起见已停止。" + [Environment]::NewLine +
                    "当前：$cur" + [Environment]::NewLine + "原版：$ORIG_SHA" + [Environment]::NewLine + "旧补丁：$OLD_SHA")
}

New-Item -ItemType Directory -Force -Path $BACKUP_DIR | Out-Null
$ts = Get-Date -Format 'yyyyMMdd_HHmmss'
$backup = Join-Path $BACKUP_DIR ("browser_assets.双板通讯前-{0}.bin" -f $ts)
Copy-Item $Target $backup -Force
Write-Host "已备份当前资源包 -> $backup"

Write-Host '正在写入新资源包…'
try {
  Copy-Item $PREBUILT $Target -Force
  $after = Get-SHA256 $Target
  if ($after -ne $NEW_SHA) { throw "安装后 sha256 不符：$after" }
} catch {
  Write-Host '安装失败，正在回滚…' -ForegroundColor Red
  Copy-Item $backup $Target -Force
  Stop-WithMessage ('安装失败：' + $_.Exception.Message + '（已回滚）')
}

Write-Host ''
Write-Host '安装成功！' -ForegroundColor Green
Write-Host '  打开 AbilixScratch3.0，左侧函数栏最上方会出现「双板通讯」分类（3 个积木）。'
Write-Host '  「我的函数」分类保留不变。'
Write-Host '  还原方法：双击「restore_dual.cmd」。'
Write-Host ''
Read-Host '按回车键关闭窗口' | Out-Null
'''

RESTORE_PS1 = r'''# 双板通讯原生积木扩展 —— 还原脚本（自动生成，勿手改）
param([string]$Target = '__TARGET__')
$ErrorActionPreference = 'Stop'
$PATCH_DIR = Split-Path -Parent $MyInvocation.MyCommand.Path
$ORIG_SHA = '__ORIG_SHA__'
$OLD_SHA = '__OLD_SHA__'
$NEW_SHA = '__NEW_SHA__'
$BACKUP_DIR = Join-Path (Split-Path -Parent $PATCH_DIR) '工具\原生积木\备份'
$ORIG_FILE = Join-Path $BACKUP_DIR 'browser_assets.原始.df6db241752d.bin'

function Stop-WithMessage([string]$msg) {
  Write-Host ''
  Write-Host $msg -ForegroundColor Yellow
  Write-Host ''
  Read-Host '按回车键关闭窗口' | Out-Null
  exit 1
}

$principal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
  Write-Host '需要管理员权限，正在请求提升…'
  $argline = '-NoProfile -ExecutionPolicy Bypass -File "{0}" -Target "{1}"' -f $MyInvocation.MyCommand.Path, $Target
  Start-Process powershell.exe -Verb RunAs -ArgumentList $argline | Out-Null
  exit 0
}

$ide = @(Get-Process -ErrorAction SilentlyContinue | Where-Object { $_.ProcessName -like 'AbilixScratch*' })
if ($ide.Count -gt 0) { Stop-WithMessage '请先完全关闭 AbilixScratch3.0 再还原。' }
if (-not (Test-Path $Target)) { Stop-WithMessage "找不到资源包：$Target" }

function Get-SHA256([string]$p) {
  $fs = [System.IO.File]::OpenRead($p)
  try {
    $sha = [System.Security.Cryptography.SHA256]::Create()
    $bytes = $sha.ComputeHash($fs)
    return ([System.BitConverter]::ToString($bytes) -replace '-', '').ToLower()
  } finally { $fs.Close() }
}

$src = $null
if (Test-Path $BACKUP_DIR) {
  $cand = @(Get-ChildItem -Path $BACKUP_DIR -Filter 'browser_assets.双板通讯前-*.bin' -ErrorAction SilentlyContinue |
            Sort-Object LastWriteTime -Descending)
  if ($cand.Count -gt 0) { $src = $cand[0].FullName }
}
if (-not $src) {
  if (Test-Path $ORIG_FILE) { $src = $ORIG_FILE }
}
if (-not $src) { Stop-WithMessage '找不到可还原的备份（browser_assets.双板通讯前-*.bin 或原版备份）。' }

$srcSha = Get-SHA256 $src
Write-Host "还原来源：$src"
Write-Host "来源 sha256：$srcSha"
if ($srcSha -ne $ORIG_SHA -and $srcSha -ne $OLD_SHA) { Stop-WithMessage '来源文件不是预期版本，已停止。' }

$cur = Get-SHA256 $Target
if ($cur -ne $NEW_SHA) { Write-Host '当前不是双板通讯版本，仍将按备份覆盖。' }

Copy-Item $src $Target -Force
$after = Get-SHA256 $Target
if ($after -ne $srcSha) { Stop-WithMessage ('还原后 sha256 不符：$after') }
Write-Host ''
Write-Host '还原成功。' -ForegroundColor Green
Write-Host '  已回到安装前的资源包。'
Write-Host ''
Read-Host '按回车键关闭窗口' | Out-Null
'''

INSTALL_CMD = '@echo off\r\nchcp 65001 >nul\r\npowershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0install_dual.ps1"\r\n'
RESTORE_CMD = '@echo off\r\nchcp 65001 >nul\r\npowershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0restore_dual.ps1"\r\n'


# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------
def main(argv=None):
    global core, pb
    ap = argparse.ArgumentParser(description='构建双板通讯原生积木扩展补丁包')
    ap.add_argument('--assets', default=DEFAULT_ASSETS, help='当前已安装的 browser_assets（读其中"我的函数"prelude）')
    ap.add_argument('--orig', default=DEFAULT_ORIG, help='原版 browser_assets 备份（打包基准）')
    ap.add_argument('--prelude', default=PRELUDE_FILE, help='双板通讯 prelude 源文件')
    ap.add_argument('--out', default=DEFAULT_OUT, help='输出目录')
    args = ap.parse_args(argv)

    sys.path.insert(0, BOTTOM_DIR)
    pb = load_module('pb_dual', PB_FILE)
    core = load_module('core_dual', CORE_FILE)

    orig = os.path.abspath(args.orig)
    assets = os.path.abspath(args.assets)
    prelude_file = os.path.abspath(args.prelude)
    out_dir = os.path.abspath(args.out)
    for p, what in ((orig, '原版资源包备份'), (assets, '当前已安装资源包'), (prelude_file, 'wl_prelude.py')):
        if not os.path.isfile(p):
            raise SystemExit('找不到%s：%s' % (what, p))

    log('=' * 72)
    log('构建「双板通讯」原生积木扩展')
    log('  原版资源包 : %s (%s)' % (orig, sha256_file(orig)[:16] + '…'))
    log('  已安装资源包: %s (%s)' % (assets, sha256_file(assets)[:16] + '…'))
    log('  双板 prelude: %s' % prelude_file)
    log('  输出目录   : %s' % out_dir)
    log('=' * 72)

    orig_sha = sha256_file(orig)
    old_sha = sha256_file(assets)
    if orig_sha.lower() != core.ORIGINAL_ASSETS_SHA.lower():
        log('⚠ 原版备份 sha 与工具记录不同，但格式合法，继续。')

    # 1) 现有「我的函数」prelude + 元数据
    prelude_old, meta_old, js_old_installed = read_userlib_from_assets(pb, assets)
    # 如果已安装的是旧版“双板通讯”补丁：去掉旧版双板 prelude 与 dk_* 块，只保留用户自己的“我的函数”
    marker = '# ===== 双板通讯 prelude'
    if marker in prelude_old:
        prelude_old = prelude_old.split(marker)[0].rstrip()
        log('检测到已安装旧版双板 prelude，已剥离后重新生成')
    meta_old = [d for d in meta_old if not str(d.get('name', '')).startswith('dk_')]
    log('读取已安装补丁：prelude %d 字符，函数 %s' % (len(prelude_old), '、'.join(d['name'] for d in meta_old)))

    # 2) 合成新 prelude
    wl = open(prelude_file, 'r', encoding='utf-8').read().strip()
    prelude_new = (prelude_old.rstrip() + '\n\n\n'
                   '# ===== 双板通讯 prelude（WER 双板通讯扩展，自动注入，勿手改）=====\n'
                   + wl + '\n')
    for d in meta_old:
        if not re.search(r'^def\s+%s\s*\(' % re.escape(d['name']), prelude_new, re.M):
            raise SystemExit('新 prelude 里缺少 def %s(...)' % d['name'])
    try:
        compile(prelude_new, '<prelude>', 'exec')
    except SyntaxError as exc:
        raise SystemExit('新 prelude 有 Python 语法错误：%r' % (exc,))

    # 3) 新 abilix_userlib.js + 分类 XML
    js_new = core.build_userlib_js({'defs': meta_old}, prelude_new) + '\n' + DUAL_BLOCK_JS
    cat_my = core.build_category_xml(meta_old)
    cat_combined = DUAL_CAT_XML + '\n' + cat_my

    # 4) 在原版资源包上打补丁
    info = pb.read_zfb_index(orig, with_data=True)
    names = [e['name'] for e in info['entries']]
    for key in (core.KEY_HTML, core.KEY_JS):
        if key not in names:
            raise SystemExit('原版资源包缺少 %s' % key)
    name_to_data = {e['name']: info['data'][e['offset']:e['offset'] + e['length']] for e in info['entries']}
    html_new = patch_html_dual(name_to_data[core.KEY_HTML].decode('utf-8'), cat_combined)
    js_patched = core.patch_js(name_to_data[core.KEY_JS].decode('utf-8'))
    name_to_data[core.KEY_HTML] = html_new.encode('utf-8')
    name_to_data[core.KEY_JS] = js_patched.encode('utf-8')
    name_to_data[core.KEY_USERLIB] = js_new.encode('utf-8')

    # 5) manifest（保留原工具字段，附加 dualComm 信息）
    lib_sha = sha256_file(LIBRARY_FILE) if os.path.isfile(LIBRARY_FILE) else ''
    lib_size = os.path.getsize(LIBRARY_FILE) if os.path.isfile(LIBRARY_FILE) else 0
    manifest = {
        'tool': 'WER双板通讯扩展',
        'toolVersion': '1.0.0',
        'builtAt': time.strftime('%Y-%m-%d %H:%M:%S'),
        'base': 'WER原生积木核心 1.0.0 补丁（保留原「我的函数」prelude）',
        'library': {
            'path': LIBRARY_FILE,
            'sha256': lib_sha,
            'size': lib_size,
            'robotType': 'SKCON9',
            'programName': 'MyFuncLib',
            'defs': [{'name': d['name'], 'args': d['args'], 'blockType': d['blockType']} for d in meta_old]
                    + [dict(d) for d in DUAL_DEFS],
        },
        'prelude': {'sha256': sha256_text(prelude_new), 'chars': len(prelude_new)},
        'sourceAssets': {'path': orig, 'sha256': orig_sha, 'size': os.path.getsize(orig)},
        'entries': {},
        'dualComm': {
            'category': CAT_NAME_DUAL,
            'colour': CAT_COLOUR_DUAL,
            'blocks': [d['blockType'] for d in DUAL_DEFS],
            'udpPort': 8990,
            'helper': '/data/data/com.abilix.controller/files/wlnet_helper',
            'note': 'prelude 末尾追加了双板通讯运行时（wl_prelude.py），只有工程里用了 abilixuf_ 积木才会注入',
        },
    }
    for key in (core.KEY_HTML, core.KEY_JS, core.KEY_USERLIB):
        data = name_to_data[key]
        manifest['entries'][key] = {'size': len(data), 'sha256': hashlib.sha256(data).hexdigest()}
    name_to_data[core.KEY_MANIFEST] = (json.dumps(manifest, ensure_ascii=False, indent=2) + '\n').encode('utf-8')

    # 6) 打包 + 自检
    entries = [dict(e) for e in info['entries']]
    entries.append({'name': core.KEY_USERLIB, 'offset': 0, 'length': 0})
    entries.append({'name': core.KEY_MANIFEST, 'offset': 0, 'length': 0})
    os.makedirs(out_dir, exist_ok=True)
    out_pkg = os.path.join(out_dir, 'browser_assets.patched')
    packed = core._pack_zfb(entries, name_to_data, out_pkg)
    check = core.verify_package(out_pkg, orig)
    if not check['ok']:
        raise SystemExit('补丁包自检失败：\n' + '\n'.join(check['errors']))
    log('补丁包：%s（%s，%d 条目）' % (out_pkg, packed['sha256'], packed['count']))
    for item in check['changed']:
        log('  修改 %s（%d -> %d 字节）' % (item['name'], item['old_len'], item['new_len']))
    for name in check['added']:
        log('  新增 %s（%d 字节）' % (name, len(name_to_data[name])))
    log('  其余 %d 个条目逐字节不变' % check['unchanged'])

    # 7) 输出安装/还原脚本 + 信息文件
    new_sha = packed['sha256']
    tpl = {
        '__TARGET__': DEFAULT_ASSETS,
        '__ORIG_SHA__': orig_sha,
        '__OLD_SHA__': old_sha,
        '__NEW_SHA__': new_sha,
    }
    def render(text):
        for k, v in tpl.items():
            text = text.replace(k, v)
        return text

    with open(os.path.join(out_dir, 'install_dual.ps1'), 'w', encoding='utf-8-sig', newline='\r\n') as f:
        f.write(render(INSTALL_PS1))
    with open(os.path.join(out_dir, 'restore_dual.ps1'), 'w', encoding='utf-8-sig', newline='\r\n') as f:
        f.write(render(RESTORE_PS1))
    with open(os.path.join(out_dir, 'install_dual.cmd'), 'w', encoding='ascii', newline='') as f:
        f.write(INSTALL_CMD)
    with open(os.path.join(out_dir, 'restore_dual.cmd'), 'w', encoding='ascii', newline='') as f:
        f.write(RESTORE_CMD)

    info_txt = []
    info_txt.append('# 双板通讯原生积木扩展 · 构建信息')
    info_txt.append('# 由 WER_函数库/工具/双板通讯/构建双板通讯扩展.py 生成')
    info_txt.append('')
    info_txt.append('构建时间 = %s' % manifest['builtAt'])
    info_txt.append('原版资源包 = %s' % orig)
    info_txt.append('原版资源包sha256 = %s' % orig_sha)
    info_txt.append('原版资源包大小 = %d' % os.path.getsize(orig))
    info_txt.append('安装前资源包sha256 = %s' % old_sha)
    info_txt.append('')
    info_txt.append('补丁包文件 = browser_assets.patched')
    info_txt.append('补丁包sha256 = %s' % new_sha)
    info_txt.append('补丁包大小 = %d' % packed['size'])
    info_txt.append('补丁包条目数 = %d' % packed['count'])
    info_txt.append('保留的我的函数 = %s' % '、'.join(d['name'] for d in meta_old))
    info_txt.append('新增双板通讯积木 = %s' % '、'.join(d['blockType'] for d in DUAL_DEFS))
    info_txt.append('双板通讯 prelude 字符数 = %d' % len(wl))
    info_txt.append('合并后 prelude 总字符数 = %d' % len(prelude_new))
    info_txt.append('')
    info_txt.append('安装目标 = %s' % DEFAULT_ASSETS)
    info_txt.append('')
    for item in check['changed']:
        info_txt.append('修改条目 %s（%d -> %d 字节）' % (item['name'], item['old_len'], item['new_len']))
    for name in check['added']:
        info_txt.append('新增条目 %s（%d 字节）' % (name, len(name_to_data[name])))
    info_txt.append('逐字节不变条目数 = %d' % check['unchanged'])
    with open(os.path.join(out_dir, '安装信息.txt'), 'w', encoding='utf-8', newline='\n') as f:
        f.write('\n'.join(info_txt) + '\n')

    log('')
    log('输出目录：%s' % out_dir)
    for fn in sorted(os.listdir(out_dir)):
        log('  %s（%d 字节）' % (fn, os.path.getsize(os.path.join(out_dir, fn))))
    log('')
    log('下一步：关闭 IDE → 以管理员身份运行「install_dual.cmd」。')
    return 0


# 供 import 时使用（build_userlib_js 等）
core = None
pb = None


if __name__ == '__main__':
    sys.exit(main())
