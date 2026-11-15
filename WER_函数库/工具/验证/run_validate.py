#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
run_validate.py —— WER/AbilixScratch3.0 项目 headless 验证工具

用**软件自带的真实 Blockly 引擎 + Python 生成器**（不是重写生成器）验证一个项目文件：
  * 项目 XML 能否被 Blockly.Xml.domToWorkspace 正常加载
  * 顶层块数 / procedures 定义清单（函数名 + 参数）
  * Blockly.Procedures.flyoutCategory(workspace) 实际生成的“函数”分类块清单
    （并真正把函数分类 flyout 打开一次，列出 flyout 里实际实例化出来的块）
  * 按 IDE maingui.getPythonCode 的方式生成完整 Python
  * 用 PC Python 做 py_compile 语法检查
  * 可选截图

用法示例：
    python run_validate.py 项目.srh
    python run_validate.py 项目.srhs --json result.json --py generated.py
    python run_validate.py 项目.srh --compare-ref 逆向资料/样本程序/PI.py --diff-out diff.txt
    python run_validate.py --param-test --evidence-dir out_param     # 内置“带参数函数”最小用例
    python run_validate.py 项目.srh --native-test --web-root _分析临时/native_work/patched_web --screenshot
                                       # 原生函数块：真实“我的函数”分类 flyout 拖出并验证生成
    python run_validate.py 项目.srh --screenshot shot.png

原理：
  1. 用 http.server 把 `_分析临时/blockly_web` 目录（Blockly_Code + closure-library）以只读方式
     起在 127.0.0.1 的随机端口上（不修改原目录；仅对唯一一个 GBK 文件 blocks/procedures.js
     在响应时做 GBK→UTF-8 转码，代码内容不变）。
  2. 服务器在 /Blockly_Code/__harness__.html 动态提供 harness 页面：按 maingui.html 的真实
     script 加载顺序加载 blockly_uncompressed.js、基础积木、真实函数生成器、myrobotpythoncode.js
     等；从 maingui.html 中原样抠出 toolbox_skcon9 作为工具箱（真数据，非重写）。
  3. harness 页面里：Blockly.inject → 加载项目 XML → 跳过 UI/CodeMirror，直接调用真实
     Blockly.Procedures.flyoutCategory / 真实 flyout / 真实 maingui.getPythonCode（从 maingui.js
     抠出的原始源码 eval 执行）→ 结果 JSON 通过同步 XHR POST 回服务器。
  4. Chrome `--headless=new --dump-dom` 跑页面；结果以 POST 数据为准，DOM 里的
     `<pre id="harness-result">` 作为兜底。可选第二次 Chrome `--screenshot` 截图。

退出码：0 = 验证通过；2 = 验证/断言失败；3 = harness 运行失败（工具/环境问题）。
"""

from __future__ import annotations

import argparse
import difflib
import hashlib
import html as html_mod
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
import traceback
import zipfile
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path, PurePosixPath
from urllib.parse import urlparse

# --------------------------------------------------------------------------------------
# 常量 / 默认路径
# --------------------------------------------------------------------------------------

TOOL_VERSION = "1.0"
SCRIPT_DIR = Path(__file__).resolve().parent            # WER_函数库/工具/验证
PROJECT_ROOT = SCRIPT_DIR.parents[2]                    # 2026普级赛
DEFAULT_WEB_ROOT = PROJECT_ROOT / "_分析临时" / "blockly_web"
DEFAULT_CHROME = Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe")
DEFAULT_EDGE = Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe")

HARNESS_URL_PATH = "/Blockly_Code/__harness__.html"
HARNESS_SOURCE_PATH = "/Blockly_Code"                   # BLOCKLY_DIR 检测用

ZIP_COMMENT_TO_ROBOT = {112: "SKCON2", 110: "SKCON5", 111: "SKCON9"}
ROBOT_TO_TOOLBOX = {
    "SKCON9": "toolbox_skcon9",
    "SKCON5": "toolbox_skcon5",
    "SKCON2": "toolbox_skcon2",
}

# --------------------------------------------------------------------------------------
# 原生函数块（“我的函数”库）补丁支持
#   WER_函数库 的补丁工具会在 web_root/Blockly_Code 下额外生成 abilix_userlib.js：
#     var abilixUserLibPython = "...";   // 注入到生成代码里的函数定义（prelude）
#     var abilixUserLib = [{"name": "...", "args": [...], ...}];
#   并把块定义为 Blockly.Blocks["abilixuf_<函数名>"]。
#   原版资源包没有这个文件，所以下面的逻辑一律“文件存在才启用”，保证向后兼容。
# --------------------------------------------------------------------------------------
USERLIB_REL_PATH = Path("Blockly_Code") / "abilix_userlib.js"
NATIVE_BLOCK_PREFIX = "abilixuf_"
NATIVE_CATEGORY_NAME = "我的函数"

INFO_RE = re.compile(r"<Abilix\.ScratchProject\.Info>(.*?)</Abilix\.ScratchProject\.Info>", re.S)
STRING_RE = re.compile(
    r"<Abilix\.ScratchProject\.ProjectString>(.*?)</Abilix\.ScratchProject\.ProjectString>", re.S
)

# IDE maingui.html 里加载的脚本（去掉 layui / codemirror / maingui.js / custom-dialog.js 等纯 UI 依赖）
# 顺序与 maingui.html line 6~43 保持一致。
HARNESS_SCRIPTS = [
    "blockly_uncompressed.js",
    "javascript_compressed.js",
    "generators/python.js",
    "generators/python/logic.js",
    "generators/python/loops.js",
    "generators/python/math.js",
    "generators/python/text.js",
    "generators/python/lists.js",
    "generators/python/colour.js",
    "generators/python/variables.js",
    "generators/python/procedures.js",
    "clike_compressed.js",
    "blocks/colour.js",
    "blocks/lists.js",
    "blocks/logic.js",
    "blocks/loops.js",
    "blocks/math.js",
    "blocks/procedures.js",
    "blocks/text.js",
    "blocks/variables.js",
    "maingui_init.js",
    "blocks/myrobotrun.js",
    "blocks/PlayList.js",
    "generators/myrobotpythoncode.js",
    "generators/myrobotjscode.js",
    "generators/myrobotclikecode.js",
    "project_config.js",
    "filesave.js",
]

# --------------------------------------------------------------------------------------
# 内置“带参数函数”最小测试项目 XML
#   - def func_MoveCm(cm)：mutation 带一个 arg；函数体用 variables_get 引用参数 cm，
#     先变量赋值（强制出现 global 行，用来验证参数被排除在 global 之外），再 wait(cm)。
#   - main 里两次调用 func_MoveCm，ARG0 分别给 10 / 20（math_number）。
# --------------------------------------------------------------------------------------
PARAM_TEST_XML = """<xml xmlns="http://www.w3.org/1999/xhtml">
  <variables>
    <variable type="" id="param_cm_id">cm</variable>
    <variable type="" id="var_last_cm_id">var_last_cm</variable>
  </variables>
  <block type="procedures_defnoreturn" id="def_block" x="40" y="40">
    <mutation><arg name="cm" varid="param_cm_id"></arg></mutation>
    <field name="NAME">func_MoveCm</field>
    <statement name="STACK">
      <block type="variables_set" id="set_block">
        <field name="VAR" id="var_last_cm_id" variabletype="">var_last_cm</field>
        <value name="VALUE">
          <block type="variables_get" id="get_param_1">
            <field name="VAR" id="param_cm_id" variabletype="">cm</field>
          </block>
        </value>
        <next>
          <block type="wait" id="wait_block">
            <value name="time">
              <block type="variables_get" id="get_param_2">
                <field name="VAR" id="param_cm_id" variabletype="">cm</field>
              </block>
            </value>
          </block>
        </next>
      </block>
    </statement>
  </block>
  <block type="start" id="start_block" deletable="false" x="40" y="460">
    <statement name="code">
      <block type="procedures_callnoreturn" id="call_1">
        <mutation name="func_MoveCm"><arg name="cm"></arg></mutation>
        <value name="ARG0">
          <block type="math_number" id="num10"><field name="NUM">10</field></block>
        </value>
        <next>
          <block type="procedures_callnoreturn" id="call_2">
            <mutation name="func_MoveCm"><arg name="cm"></arg></mutation>
            <value name="ARG0">
              <block type="math_number" id="num20"><field name="NUM">20</field></block>
            </value>
          </block>
        </next>
      </block>
    </statement>
  </block>
</xml>
"""

# --------------------------------------------------------------------------------------
# harness 页面模板
#   @@CONFIG_JSON@@  -> JSON 配置（含项目 XML、getPythonCode 源码）
#   @@TOOLBOX_XML@@  -> 从 maingui.html 原样抠出的 toolbox_skcon9
#   @@SCRIPT_TAGS@@  -> 按 IDE 顺序生成的 <script src=...>
# --------------------------------------------------------------------------------------
HARNESS_TEMPLATE = r"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>WER Blockly harness</title>
<script type="application/json" id="harness-config">@@CONFIG_JSON@@</script>
<script>
/* 早期错误钩子：必须在 Blockly 之前安装，任何脚本加载/执行错误都会被记录 */
window.__HARNESS_WINDOW_ERRORS__ = [];
window.__HARNESS_CONSOLE_ERRORS__ = [];
window.onerror = function (msg, src, line, col, err) {
  try {
    window.__HARNESS_WINDOW_ERRORS__.push({
      message: String(msg),
      source: src ? String(src).replace(location.origin, '') : '',
      line: line, col: col,
      stack: err && err.stack ? String(err.stack) : ''
    });
  } catch (e) {}
  return false;
};
window.addEventListener('unhandledrejection', function (ev) {
  try { window.__HARNESS_WINDOW_ERRORS__.push({message: 'unhandledrejection: ' + String(ev.reason)}); } catch (e) {}
});
(function () {
  var origError = console.error;
  console.error = function () {
    try {
      var parts = [];
      for (var i = 0; i < arguments.length; i++) {
        var a = arguments[i];
        parts.push(a instanceof Error ? String(a.stack || a) : String(a));
      }
      window.__HARNESS_CONSOLE_ERRORS__.push(parts.join(' '));
    } catch (e) {}
    if (origError) { origError.apply(console, arguments); }
  };
})();
/* maingui 全局（真实 maingui.js 不加载；生成器 myrobotpythoncode.js 依赖 maingui.robotType） */
var __HARNESS_CFG__ = JSON.parse(document.getElementById('harness-config').textContent);
var maingui = {
  robotType: __HARNESS_CFG__.robotType,
  connectionType: __HARNESS_CFG__.connectionType,
  isAudioOn: false
};
</script>
@@SCRIPT_TAGS@@
<style>
  html, body { margin: 0; padding: 0; height: 100%; overflow: hidden; background: #f4f4f4; }
  #blocklyDiv { position: absolute; left: 0; top: 0; width: 100%; height: 100%; }
</style>
</head>
<body>
<!-- 真实工具箱：从 maingui.html 原样抠出 -->
@@TOOLBOX_XML@@
<div id="blocklyDiv"></div>
<script>
(function () {
  'use strict';
  var cfg = JSON.parse(document.getElementById('harness-config').textContent);
  if (location.search.indexOf('shot=1') >= 0) { cfg.mode = 'shot'; }
  /* 原生块截图：?shot=1&nativeShot=page|flyout|drag|python（只在 --native-test 截图时使用） */
  var __nativeShotMatch = /(?:[?&])nativeShot=([^&]+)/.exec(location.search || '');
  if (__nativeShotMatch) { cfg.nativeShot = decodeURIComponent(__nativeShotMatch[1]); }
  document.getElementById('harness-config').textContent = '';
  var R = {
    ok: false,
    tool: 'wer-blockly-harness',
    harnessVersion: '@@TOOL_VERSION@@',
    startedAt: new Date().toISOString(),
    config: {
      mode: cfg.mode, robotType: cfg.robotType, connectionType: cfg.connectionType,
      programName: cfg.programName, projectXmlLength: (cfg.projectXml || '').length
    },
    steps: [],
    windowErrors: window.__HARNESS_WINDOW_ERRORS__ || [],
    consoleErrors: window.__HARNESS_CONSOLE_ERRORS__ || []
  };

  function step(name, fn) {
    var t = performance.now();
    var v = fn();
    R.steps.push({ name: name, ok: true, ms: Math.round((performance.now() - t) * 10) / 10 });
    return v;
  }
  /* 非致命步骤：失败只记录，不中断 */
  function safeStep(name, fn) {
    var t = performance.now();
    try {
      var v = fn();
      R.steps.push({ name: name, ok: true, ms: Math.round((performance.now() - t) * 10) / 10 });
      return { ok: true, value: v };
    } catch (e) {
      R.steps.push({
        name: name, ok: false, ms: Math.round((performance.now() - t) * 10) / 10,
        error: String(e && (e.stack || e))
      });
      return { ok: false, error: String(e && (e.stack || e)) };
    }
  }
  function describeFlyoutXmlEl(el) {
    var out = { tag: (el.tagName || '').toLowerCase(), type: el.getAttribute ? el.getAttribute('type') : null };
    try {
      var mut = el.getElementsByTagName('mutation')[0];
      if (mut) {
        out.mutationName = mut.getAttribute('name');
        out.args = [];
        var args = mut.getElementsByTagName('arg');
        for (var i = 0; i < args.length; i++) { out.args.push(args[i].getAttribute('name')); }
      }
      var fields = el.getElementsByTagName('field');
      for (var j = 0; j < fields.length; j++) {
        if (fields[j].getAttribute('name') === 'NAME') { out.fieldName = fields[j].textContent; }
      }
    } catch (e) { out.describeError = String(e); }
    return out;
  }
  function describeBlock(b) {
    var o = { type: b.type, isInFlyout: !!b.isInFlyout };
    try { if (b.getFieldValue && b.getFieldValue('NAME')) { o.name = b.getFieldValue('NAME'); } } catch (e) {}
    try { if (b.getProcedureCall) { o.callName = b.getProcedureCall(); } } catch (e) {}
    try { if (b.arguments_) { o.args = b.arguments_.slice(); } } catch (e) {}
    try { o.inputs = b.inputList ? b.inputList.map(function (i) { return i.name; }) : []; } catch (e) {}
    try {
      var hw = b.getHeightWidth ? b.getHeightWidth() : null;
      if (hw) { o.width = Math.round(hw.width); o.height = Math.round(hw.height); }
    } catch (e) {}
    return o;
  }
  function countByType(blocks) {
    var d = {};
    for (var i = 0; i < blocks.length; i++) { d[blocks[i].type] = (d[blocks[i].type] || 0) + 1; }
    return d;
  }

  var workspace = null;
  R.load = { success: false, error: null, ms: null };
  R.workspace = { topBlockCount: 0, totalBlockCount: 0, variableCount: 0, topBlocksByType: {}, topBlocks: [] };
  R.procedures = { defnoreturn: [], defreturn: [], allProceduresSorted: { defnoreturn: [], defreturn: [] } };
  R.flyout = { categoryXml: null, instantiate: null };
  /* 原生函数块（abilix_userlib.js，--native-test / 原生块截图）：分类 / flyout / 真实拖出 */
  R.native = { attempted: false, ok: false, error: null, category: {}, flyout: {}, drag: {} };
  R.generation = { success: false, usedRealSource: false, evalError: null, error: null, code: null };

  try {
    var tLoad = performance.now();
    try {
      workspace = step('inject', function () {
        return Blockly.inject('blocklyDiv', {
          media: 'media/',
          toolbox: document.getElementById('@@TOOLBOX_ID@@'),
          zoom: { controls: true, wheel: true, startScale: 1.0, maxScale: 3, minScale: 0.3, scaleSpeed: 1.2 },
          trashcan: false
        });
      });
      window.workspace = workspace;
      step('clear', function () { workspace.clear(); });
      var xmlDom = step('textToDom', function () { return Blockly.Xml.textToDom(cfg.projectXml); });
      step('domToWorkspace', function () { Blockly.Xml.domToWorkspace(xmlDom, workspace); });
      R.load.success = true;
    } catch (e) {
      R.load.error = String(e && (e.stack || e));
    }
    R.load.ms = Math.round((performance.now() - tLoad) * 10) / 10;

    /* ---- 工作区统计（含渲染健康度检查） ---- */
    var s = safeStep('workspaceStats', function () {
      var top = workspace.getTopBlocks(false);
      var all = workspace.getAllBlocks(false);
      var vars = workspace.getAllVariables();
      var rendered = 0, svgOk = 0, zeroSize = 0, warnings = [], disabled = 0;
      all.forEach(function (b) {
        try { if (b.rendered) { rendered++; } } catch (e) {}
        try {
          var root = b.getSvgRoot ? b.getSvgRoot() : null;
          if (root && root.childNodes && root.childNodes.length > 0) { svgOk++; }
        } catch (e) {}
        try {
          var hw = b.getHeightWidth ? b.getHeightWidth() : null;
          if (!hw || !(hw.width > 0) || !(hw.height > 0)) { zeroSize++; }
        } catch (e) { zeroSize++; }
        try { var w = b.getWarningText ? b.getWarningText() : null; if (w) { warnings.push({type: b.type, text: String(w)}); } } catch (e) {}
        try { if (b.disabled) { disabled++; } } catch (e) {}
      });
      return {
        topBlockCount: top.length,
        totalBlockCount: all.length,
        variableCount: vars.length,
        variableNames: vars.map(function (v) { return v.name; }),
        topBlocksByType: countByType(top),
        allBlocksByType: countByType(all),
        topBlocks: top.map(function (b) {
          var xy = b.getRelativeToSurfaceXY();
          return { type: b.type, xy: [Math.round(xy.x), Math.round(xy.y)], id: b.id };
        }),
        render: {
          renderedBlockCount: rendered,
          renderedSvgRootCount: svgOk,
          zeroSizeBlockCount: zeroSize,
          warningCount: warnings.length,
          warnings: warnings.slice(0, 20),
          disabledBlockCount: disabled,
          mainWorkspaceIsThis: !!(Blockly.getMainWorkspace && Blockly.getMainWorkspace() === workspace),
          blocklyBlockCanvasCount: document.querySelectorAll('.blocklyBlockCanvas').length,
          injectionDivCount: document.querySelectorAll('.injectionDiv').length,
          svgCount: document.querySelectorAll('svg.blocklySvg').length
        }
      };
    });
    if (s.ok) { R.workspace = s.value; }

    /* ---- procedures 定义清单（含参数） ---- */
    var p = safeStep('procedures', function () {
      var noRet = [], ret = [];
      workspace.getAllBlocks(false).forEach(function (b) {
        if (!b.getProcedureDef) { return; }
        var d = null;
        try { d = b.getProcedureDef(); } catch (e) { return; }
        if (!d) { return; }
        var rec = { name: d[0], args: (d[1] || []).slice(), blockType: b.type, id: b.id };
        if (d[2]) { ret.push(rec); } else { noRet.push(rec); }
      });
      var tuple = Blockly.Procedures.allProcedures(workspace);
      return {
        defnoreturn: noRet,
        defreturn: ret,
        allProceduresSorted: {
          defnoreturn: tuple[0].map(function (t) { return { name: t[0], args: (t[1] || []).slice() }; }),
          defreturn: tuple[1].map(function (t) { return { name: t[0], args: (t[1] || []).slice() }; })
        }
      };
    });
    if (p.ok) { R.procedures = p.value; }

    /* ---- 函数分类 flyout：真实 Blockly.Procedures.flyoutCategory(workspace) ---- */
    var fx = safeStep('flyoutCategory', function () {
      var list = Blockly.Procedures.flyoutCategory(workspace);
      if (!Array.isArray(list)) { throw new Error('flyoutCategory 返回值不是数组'); }
      return {
        count: list.length,
        xml: list.map(function (el) { return new XMLSerializer().serializeToString(el); }),
        blocks: list.map(describeFlyoutXmlEl)
      };
    });
    R.flyout.categoryXml = fx.ok ? fx.value : { error: fx.error };

    /* ---- 函数分类 flyout：真正实例化（等价于在 IDE 里点开“函数”分类） ----
       原生积木模式（--native-test / 原生块截图）不碰 PROCEDURE 分类，避免 flyout 状态互相干扰 */
    var inst;
    if (!cfg.nativeTest && !cfg.nativeShot) {
    inst = safeStep('flyoutInstantiate', function () {
      var tb = workspace.getToolbox();
      if (!tb || !tb.flyout_) { throw new Error('workspace.getToolbox()/flyout_ 不可用'); }
      var found = null;
      function walk(node) {
        if (!node || found) { return; }
        var kids = [];
        try { kids = node.getChildren ? (node.getChildren() || []) : []; } catch (e) { kids = []; }
        for (var i = 0; i < kids.length; i++) {
          if (kids[i].blocks === 'PROCEDURE') { found = kids[i]; return; }
          walk(kids[i]);
          if (found) { return; }
        }
      }
      if (tb.tree_) { walk(tb.tree_); }
      var viaTree = false;
      if (found) {
        tb.tree_.setSelectedItem(found);   // 真实路径：Toolbox.TreeControl.setSelectedItem -> flyout_.show('PROCEDURE')
        viaTree = true;
      } else {
        tb.flyout_.show('PROCEDURE');      // 兜底：与 toolbox 选择走的同一个 flyout.show
      }
      var fw = tb.flyout_.workspace_;
      var blocks = fw.getTopBlocks(true);
      var fRendered = 0, fSvgOk = 0, fZeroSize = 0;
      blocks.forEach(function (b) {
        try { if (b.rendered) { fRendered++; } } catch (e) {}
        try {
          var root = b.getSvgRoot ? b.getSvgRoot() : null;
          if (root && root.childNodes && root.childNodes.length > 0) { fSvgOk++; }
        } catch (e) {}
        try {
          var hw = b.getHeightWidth ? b.getHeightWidth() : null;
          if (!hw || !(hw.width > 0) || !(hw.height > 0)) { fZeroSize++; }
        } catch (e) { fZeroSize++; }
      });
      var result = {
        viaTreeSelection: viaTree,
        flyoutVisible: !!tb.flyout_.isVisible(),
        blockCount: blocks.length,
        blocks: blocks.map(describeBlock),
        render: {
          renderedBlockCount: fRendered,
          renderedSvgRootCount: fSvgOk,
          zeroSizeBlockCount: fZeroSize
        }
      };
      if (cfg.mode !== 'shot') {
        tb.flyout_.hide();
        if (found && tb.tree_) { tb.tree_.setSelectedItem(null); }
      }
      return result;
    });
    } else {
      inst = { ok: true, value: { skipped: true, reason: '原生块模式不实例化 PROCEDURE 分类' } };
    }
    R.flyout.instantiate = inst.ok ? inst.value : { error: inst.error };

    /* ---- “从函数分类拖出调用块”等价路径验证（--drag-test） ----
       1) 打开函数分类 flyout（真实 Toolbox 选中路径）
       2) 对 flyout 里每个 procedures_callnoreturn 调用 Blockly.Flyout.prototype.createBlock
          —— 这正是 IDE 里鼠标拖拽松手时执行的同一个函数
       3) 给参数输入填值（文本参数填 text 块，其余填 math_number 7）
       4) 把拖出的调用块依次接到 start 积木的 code 语句链末尾
       5) 之后照常生成 Python 并检查（服务端断言） */
    R.drag = { attempted: false, ok: false, error: null, created: [], argFillRules: {} };
    if (cfg.mode === 'drag') {
      var d = safeStep('dragFromFlyout', function () {
        R.drag.attempted = true;
        var tb = workspace.getToolbox();
        if (!tb || !tb.flyout_) { throw new Error('workspace.getToolbox()/flyout_ 不可用'); }
        var found = null;
        (function walk(node) {
          if (!node || found) { return; }
          var kids = [];
          try { kids = node.getChildren ? (node.getChildren() || []) : []; } catch (e) { kids = []; }
          for (var i = 0; i < kids.length; i++) {
            if (kids[i].blocks === 'PROCEDURE') { found = kids[i]; return; }
            walk(kids[i]);
            if (found) { return; }
          }
        })(tb.tree_);
        if (found) { tb.tree_.setSelectedItem(found); } else { tb.flyout_.show('PROCEDURE'); }
        var flyBlocks = tb.flyout_.workspace_.getTopBlocks(true);
        var callBlocks = flyBlocks.filter(function (b) { return b.type === 'procedures_callnoreturn'; });
        if (!callBlocks.length) { throw new Error('函数分类 flyout 里没有 procedures_callnoreturn 调用块'); }
        var mathXml = '<xml xmlns="http://www.w3.org/1999/xhtml"><block type="math_number"><field name="NUM">7</field></block></xml>';
        var textXml = '<xml xmlns="http://www.w3.org/1999/xhtml"><block type="text"><field name="TEXT">hello</field></block></xml>';
        function makeValueBlock(kind) {
          var dom = Blockly.Xml.textToDom(kind === 'text' ? textXml : mathXml);
          var blockEl = dom.getElementsByTagName ? dom.getElementsByTagName('block')[0] :
              dom.firstChild;
          return Blockly.Xml.domToBlock(blockEl, workspace);
        }
        var created = [];
        callBlocks.forEach(function (fb) {
          var callName = fb.getProcedureCall ? fb.getProcedureCall() : '(?)';
          var nb = tb.flyout_.createBlock(fb);   /* ← IDE 拖拽落地的同一条代码路径 */
          if (!nb) { throw new Error('Flyout.createBlock 返回空: ' + callName); }
          var args = (nb.arguments_ || []).slice();
          var rec = { name: callName, args: args, argValues: [] };
          for (var i = 0; i < args.length; i++) {
            var argName = args[i];
            var isText = /(^|_)(text|msg|string|str|s)$/i.test(argName) || /Show|Text/i.test(callName);
            var vb = makeValueBlock(isText ? 'text' : 'math_number');
            var input = nb.getInput('ARG' + i);
            if (!input) { throw new Error(callName + ' 缺少 ARG' + i + ' 输入'); }
            input.connection.connect(vb.outputConnection);
            rec.argValues.push(isText ? "'hello'" : '7');
            R.drag.argFillRules[callName + ':ARG' + i] = isText ? 'text:hello' : 'math_number:7';
          }
          created.push({ rec: rec, block: nb });
        });
        var startBlock = workspace.getTopBlocks(false).filter(function (b) { return b.type === 'start'; })[0];
        if (!startBlock) { throw new Error('项目没有 start 积木，无法接入拖出的调用块'); }
        var codeInput = startBlock.getInput('code');
        if (!codeInput) { throw new Error('start 积木没有 code 语句输入'); }
        var tail = codeInput.connection.targetBlock();
        if (tail) { while (tail.getNextBlock()) { tail = tail.getNextBlock(); } }
        created.forEach(function (item) {
          var nb = item.block;
          if (tail) { tail.nextConnection.connect(nb.previousConnection); }
          else { codeInput.connection.connect(nb.previousConnection); }
          tail = nb;
          try { item.rec.rendered = !!nb.rendered; } catch (e) { item.rec.rendered = false; }
          try {
            var root = nb.getSvgRoot ? nb.getSvgRoot() : null;
            item.rec.svgOk = !!(root && root.childNodes && root.childNodes.length > 0);
          } catch (e) { item.rec.svgOk = false; }
        });
        R.drag.ok = true;
        R.drag.viaTreeSelection = !!found;
        R.drag.createdCount = created.length;
        R.drag.created = created.map(function (item) { return item.rec; });
        R.drag.startBlockId = startBlock.id;
        R.drag.workspaceTopBlockCountAfter = workspace.getTopBlocks(false).length;
        R.drag.workspaceTotalBlockCountAfter = workspace.getAllBlocks(false).length;
        var mainGeneratedOk = true;
        return true;
      });
      if (!d.ok) { R.drag.error = d.error; }
    }

    /* ---- 原生函数块（abilix_userlib.js 补丁）：--native-test / 原生块截图 ----
       1) 在真实工具箱树里找“我的函数”静态分类：分类节点的 blocks 是 <block> DOM 数组，
          块类型前缀 abilixuf_（由 abilix_userlib.js 动态注册）
       2) 走真实路径 Toolbox.TreeControl.setSelectedItem(分类节点) → flyout_.show(分类块数组)，
          等价于在 IDE 里点开“我的函数”分类
       3) 对 flyout 里每个原生块调用 Flyout.prototype.createBlock —— IDE 里鼠标拖拽松手时
          执行的同一个函数；带参函数的 ARG 输入填 math_number 值
       4) 把拖出的块依次接到 start 积木的 code 语句链末尾；之后照常走真实生成流程 */
    var nativeCategoryNode = null;
    if (cfg.nativeTest || cfg.nativeShot) {
      var natCat = safeStep('nativeCategory', function () {
        var tb = workspace.getToolbox();
        if (!tb || !tb.tree_) { throw new Error('workspace.getToolbox()/tree_ 不可用'); }
        var prefix = (cfg.nativeTest && cfg.nativeTest.blockPrefix) || 'abilixuf_';
        var catName = (cfg.nativeTest && cfg.nativeTest.categoryName) || '我的函数';
        function walk(node) {
          if (!node || nativeCategoryNode) { return; }
          var list = null;
          try { list = node.blocks; } catch (e) { list = null; }
          if (Object.prototype.toString.call(list) === '[object Array]' && list.length) {
            var firstType = (list[0] && list[0].getAttribute) ? (list[0].getAttribute('type') || '') : '';
            if (firstType.indexOf(prefix) === 0) { nativeCategoryNode = node; return; }
          }
          var kids = [];
          try { kids = node.getChildren ? (node.getChildren() || []) : []; } catch (e) { kids = []; }
          for (var i = 0; i < kids.length; i++) { walk(kids[i]); if (nativeCategoryNode) { return; } }
        }
        walk(tb.tree_);
        R.native.attempted = true;
        R.native.category = { found: !!nativeCategoryNode, name: null, viaTreeSelection: false,
                              blockCount: 0, blockTypes: [] };
        if (!nativeCategoryNode) {
          throw new Error('工具箱树里找不到“' + catName + '”分类（web_root 是否包含 abilix_userlib.js 补丁？）');
        }
        try {
          R.native.category.name = nativeCategoryNode.getText ? nativeCategoryNode.getText()
              : (nativeCategoryNode.getHtml ? nativeCategoryNode.getHtml() : null);
        } catch (e) { R.native.category.name = null; }
        var list = nativeCategoryNode.blocks;
        R.native.category.blockCount = list.length;
        R.native.category.blockTypes = list.map(function (el) {
          return (el && el.getAttribute) ? el.getAttribute('type') : null;
        });
        return true;
      });
      if (!natCat.ok) { R.native.error = natCat.error; }

      /* 'page' 截图只看工具箱初始状态，不打开分类 */
      if (natCat.ok && cfg.nativeShot !== 'page') {
        var natFly = safeStep('nativeFlyout', function () {
          var tb = workspace.getToolbox();
          tb.tree_.setSelectedItem(nativeCategoryNode);   /* 真实路径：点开“我的函数”分类 */
          R.native.category.viaTreeSelection = true;
          var fw = tb.flyout_.workspace_;
          var blocks = fw.getTopBlocks(true);
          var fRendered = 0, fSvgOk = 0, fZeroSize = 0;
          blocks.forEach(function (b) {
            try { if (b.rendered) { fRendered++; } } catch (e) {}
            try {
              var root = b.getSvgRoot ? b.getSvgRoot() : null;
              if (root && root.childNodes && root.childNodes.length > 0) { fSvgOk++; }
            } catch (e) {}
            try {
              var hw = b.getHeightWidth ? b.getHeightWidth() : null;
              if (!hw || !(hw.width > 0) || !(hw.height > 0)) { fZeroSize++; }
            } catch (e) { fZeroSize++; }
          });
          R.native.flyout = {
            visible: !!tb.flyout_.isVisible(),
            blockCount: blocks.length,
            blockTypes: blocks.map(function (b) { return b.type; }),
            blocks: blocks.map(describeBlock),
            render: { renderedBlockCount: fRendered, renderedSvgRootCount: fSvgOk, zeroSizeBlockCount: fZeroSize }
          };
          return true;
        });
        if (!natFly.ok) { R.native.error = natFly.error; }

        /* 拖拽：非截图模式必做；nativeShot=drag/python 时也做（用于截图证据） */
        if (natFly.ok && (!cfg.nativeShot || cfg.nativeShot === 'drag' || cfg.nativeShot === 'python')) {
          var natDrag = safeStep('nativeDragFromFlyout', function () {
            var tb = workspace.getToolbox();
            var base = (cfg.nativeTest && cfg.nativeTest.argValueBase) || 10;
            R.native.drag = { attempted: true, ok: false, error: null, createdCount: 0, created: [],
                              removedCount: 0, removedTypes: [], startBlockId: null, chainLength: 0 };
            /* 移除项目里原有的原生块：生成内容将全部来自本次真实拖出（避免重复调用/干扰断言） */
            var removed = [];
            workspace.getAllBlocks(false).slice().forEach(function (b) {
              if ((b.type || '').indexOf('abilixuf_') === 0) {
                removed.push(b.type);
                try { b.dispose(false, false); } catch (e) {}
              }
            });
            var flyCount = tb.flyout_.workspace_.getTopBlocks(true).length;
            if (!flyCount) { throw new Error('“我的函数”分类 flyout 里没有块'); }
            var created = [];
            for (var idx = 0; idx < flyCount; idx++) {
              if (!tb.flyout_.isVisible()) { tb.flyout_.show(nativeCategoryNode.blocks); }
              var blocksNow = tb.flyout_.workspace_.getTopBlocks(true);
              var fb = blocksNow[idx] || blocksNow[blocksNow.length - 1];
              var nb = tb.flyout_.createBlock(fb);   /* ← IDE 拖拽落地的同一条代码路径 */
              if (!nb) { throw new Error('Flyout.createBlock 返回空: ' + (fb && fb.type)); }
              var inputNames = (nb.inputList || []).map(function (i) { return i.name; });
              var argInputs = [], argValues = [];
              inputNames.forEach(function (name) {
                if (!/^ARG\d+$/.test(name)) { return; }
                var ai = argInputs.length;
                var value = base * (idx + 1) + ai;
                var mathXml = '<xml xmlns="http://www.w3.org/1999/xhtml"><block type="math_number">' +
                    '<field name="NUM">' + value + '</field></block></xml>';
                var dom = Blockly.Xml.textToDom(mathXml);
                var blockEl = dom.getElementsByTagName ? dom.getElementsByTagName('block')[0] : dom.firstChild;
                var vb = Blockly.Xml.domToBlock(blockEl, workspace);
                var input = nb.getInput(name);
                if (!input) { throw new Error(nb.type + ' 缺少输入 ' + name); }
                input.connection.connect(vb.outputConnection);
                argInputs.push(name + ':math_number');
                argValues.push(String(value));
              });
              var nbRendered = false, nbSvgOk = false;
              try { nbRendered = !!nb.rendered; } catch (e) {}
              try {
                var root = nb.getSvgRoot ? nb.getSvgRoot() : null;
                nbSvgOk = !!(root && root.childNodes && root.childNodes.length > 0);
              } catch (e) {}
              created.push({ type: nb.type, flyoutIndex: idx, argInputs: argInputs,
                             argValues: argValues, rendered: nbRendered, svgOk: nbSvgOk, block: nb });
            }
            var startBlock = workspace.getTopBlocks(false).filter(function (b) { return b.type === 'start'; })[0];
            if (!startBlock) { throw new Error('项目没有 start 积木，无法接入拖出的原生块'); }
            var codeInput = startBlock.getInput('code');
            if (!codeInput) { throw new Error('start 积木没有 code 语句输入'); }
            var tail = codeInput.connection.targetBlock();
            if (tail) { while (tail.getNextBlock()) { tail = tail.getNextBlock(); } }
            created.forEach(function (item) {
              if (tail) { tail.nextConnection.connect(item.block.previousConnection); }
              else { codeInput.connection.connect(item.block.previousConnection); }
              tail = item.block;
            });
            var chainBlocks = 0;
            var cb = codeInput.connection.targetBlock();
            while (cb) { chainBlocks += 1; cb = cb.getNextBlock(); }
            R.native.drag = {
              attempted: true, ok: true, error: null,
              viaTreeSelection: true,
              removedCount: removed.length, removedTypes: removed,
              createdCount: created.length,
              created: created.map(function (item) {
                return { type: item.type, flyoutIndex: item.flyoutIndex, argInputs: item.argInputs,
                         argValues: item.argValues, rendered: item.rendered, svgOk: item.svgOk };
              }),
              startBlockId: startBlock.id, chainLength: chainBlocks,
              workspaceTopBlockCountAfter: workspace.getTopBlocks(false).length,
              workspaceTotalBlockCountAfter: workspace.getAllBlocks(false).length
            };
            return true;
          });
          if (!natDrag.ok) { R.native.drag.error = natDrag.error; R.native.error = natDrag.error; }
          if (natDrag.ok) { R.native.ok = true; }
        }

        /* 非 'flyout' 截图/普通断言运行：收起 flyout，让工作区可见（'flyout' 截图保持打开） */
        if (cfg.nativeShot !== 'flyout') {
          try { tb.flyout_.hide(); } catch (e) {}
          try { tb.tree_.setSelectedItem(null); } catch (e) {}
        }
      }
    }

    /* ---- 生成 Python：eval 真实 maingui.js 中 getPythonCode 的原始源码 ----
       'python' 原生块截图也要真实生成（其它 shot 截图不需要生成） */
    if (cfg.mode !== 'shot' || cfg.nativeShot === 'python') {
      var genT0 = performance.now();
      try {
        try {
          if (cfg.getPythonCodeSource) {
            eval(cfg.getPythonCodeSource);   // 原始源码形如：maingui.getPythonCode = function (...) {...}
          }
        } catch (e) {
          R.generation.evalError = String(e && (e.stack || e));
        }
        R.generation.usedRealSource = (typeof maingui.getPythonCode === 'function');
        if (R.generation.usedRealSource) {
          R.generation.code = maingui.getPythonCode(cfg.robotType, cfg.connectionType, cfg.programName);
        } else {
          /* 兜底：与 maingui.getPythonCode 非 SKCON2 分支逐字等价 */
          var head = (cfg.robotType === 'SKCON2')
            ? 'import robot\n\n'
            : '#<' + cfg.robotType + '><' + cfg.connectionType + '><' + cfg.programName + '>\n\n' +
              'import threading\nimport time\nimport libstarpy\n\nrobot = Robot()\n\n';
          R.generation.code = head + Blockly.Python.workspaceToCode(workspace) + '\nmain()#program entry';
        }
        R.generation.success = (typeof R.generation.code === 'string');
      } catch (e) {
        R.generation.error = String(e && (e.stack || e));
      }
      R.generation.ms = Math.round((performance.now() - genT0) * 10) / 10;

      /* 生成结果的轻量结构分析（供人看，完整分析在 Python 侧做） */
      try {
        var code = R.generation.code || '';
        var defs = [];
        var reDef = /^def\s+([A-Za-z_]\w*)\s*\(([^)]*)\)\s*:/gm;
        var m;
        while ((m = reDef.exec(code)) !== null) { defs.push({ name: m[1], args: m[2] }); }
        R.generation.analysis = {
          codeLength: code.length,
          codeLines: code.split('\n').length,
          headerLine: (code.split('\n')[0] || ''),
          defCount: defs.length,
          defs: defs,
          hasMainCall: /\nmain\(\)#program entry\s*$/.test(code)
        };
      } catch (e) { R.generation.analysis = { error: String(e) }; }
    }

    /* ---- 截图模式：按 nativeShot 类型摆好画面后停手 ----
       page=工具箱初始状态 / flyout=“我的函数”分类展开 / drag=真实拖出后的工作区 /
       python=工作区 + 右侧真实生成代码面板（一张图同时看到积木与生成结果） */
    if (cfg.mode === 'shot') {
      safeStep('shotPrepare', function () {
        try {
          if (cfg.nativeShot === 'python' && R.generation.code) {
            var panel = document.createElement('pre');
            panel.id = 'harness-code-panel';
            panel.textContent = R.generation.code;
            panel.style.cssText = 'position:fixed;right:0;top:0;width:44%;height:100%;margin:0;' +
                'padding:8px;box-sizing:border-box;overflow:auto;background:#1e1e1e;color:#d4d4d4;' +
                'font:12px/1.35 Consolas,monospace;white-space:pre;z-index:9999;border-left:2px solid #555;';
            document.body.appendChild(panel);
            document.getElementById('blocklyDiv').style.width = '56%';
          }
          /* 分阶段证据图左上角标注（page / flyout / drag 三种），说明该图拍的是哪一步 */
          if (cfg.nativeShot === 'page' || cfg.nativeShot === 'flyout' || cfg.nativeShot === 'drag') {
            var nc = R.native.category || {}, nf = R.native.flyout || {}, nd = R.native.drag || {};
            var txt = '';
            if (cfg.nativeShot === 'page') {
              txt = '原生块证据 1/4：页面初始状态。左侧工具箱可见“我的函数”分类（' +
                  (nc.found ? (nc.blockCount + ' 个原生块') : '未找到') + '），尚未打开分类。';
            } else if (cfg.nativeShot === 'flyout') {
              txt = '原生块证据 2/4：已通过真实工具箱树选中“' + (nc.name || '我的函数') + '”分类，' +
                  'flyout 真实实例化 ' + (nf.blockCount || 0) + ' 块：' +
                  (((nf.blockTypes || []).join(', ')) || '无');
            } else {
              var madeTypes = (nd.created || []).map(function (c) {
                return c.type + '(' + (c.argValues || []).join(', ') + ')';
              });
              txt = '原生块证据 3/4：对 flyout 里每个原生块调用 Flyout.createBlock 真实拖出 ' +
                  (nd.createdCount || 0) + ' 块并接入 start（移除项目原有原生块 ' + (nd.removedCount || 0) +
                  ' 块）：' + ((madeTypes.join('  ')) || '无');
            }
            var label = document.createElement('div');
            label.id = 'harness-native-label';
            label.textContent = txt;
            label.style.cssText = 'position:fixed;left:108px;top:6px;max-width:72%;padding:6px 10px;' +
                'background:rgba(255,255,255,0.94);border:1px solid #9933ff;border-radius:4px;' +
                'color:#333;font:13px/1.5 "Microsoft YaHei",sans-serif;z-index:9998;white-space:pre-wrap;';
            document.body.appendChild(label);
          }
          try { Blockly.svgResize(workspace); } catch (e) {}
          try { workspace.scrollCenter(); } catch (e) {}
        } catch (e) {}
        return true;
      });
    }
  } catch (e) {
    R.fatal = String(e && (e.stack || e));
  }

  R.windowErrors = window.__HARNESS_WINDOW_ERRORS__ || [];
  R.consoleErrors = window.__HARNESS_CONSOLE_ERRORS__ || [];
  R.ok = !R.fatal && !!R.load.success && (cfg.mode === 'shot' ? true : !!R.generation.success);
  R.finishedAt = new Date().toISOString();

  if (cfg.mode === 'shot') {
    document.title = 'HARNESS_SHOT';
    return;
  }

  /* 提交结果：POST 为准，DOM 兜底；然后清空大 DOM 让 --dump-dom 输出很小 */
  var payload = JSON.stringify(R);
  try {
    var xhr = new XMLHttpRequest();
    xhr.open('POST', '/__api__/result', false);
    xhr.setRequestHeader('Content-Type', 'application/json; charset=utf-8');
    xhr.send(payload);
    R.postStatus = xhr.status;
  } catch (e) {
    R.postStatus = -1;
  }
  try { document.body.innerHTML = ''; } catch (e) {}
  try {
    var pre = document.createElement('pre');
    pre.id = 'harness-result';
    pre.textContent = JSON.stringify(R);
    document.body.appendChild(pre);
  } catch (e) {}
  document.title = R.ok ? 'HARNESS_OK' : 'HARNESS_FAIL';
})();
</script>
</body>
</html>
"""


# --------------------------------------------------------------------------------------
# 小工具
# --------------------------------------------------------------------------------------

def log(msg: str = "") -> None:
    try:
        print(msg, flush=True)
    except UnicodeEncodeError:
        print(msg.encode("utf-8", "replace").decode("utf-8", "replace"), flush=True)


def now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S")


def decode_bytes(data: bytes) -> tuple[str, str]:
    """返回 (text, encoding)。项目/参考文件多为 UTF-8，少量历史文件为 GBK。"""
    for enc in ("utf-8-sig", "utf-8", "gb18030"):
        try:
            return data.decode(enc), enc
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", "replace"), "utf-8(replace)"


def localname(tag: str) -> str:
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag


def json_for_script(obj) -> str:
    """安全的 JSON 字符串（避免 HTML <script> 提前结束）。"""
    return json.dumps(obj, ensure_ascii=False).replace("</", "<\\/")


def find_python_exe() -> str:
    if sys.executable and Path(sys.executable).exists():
        return sys.executable
    return shutil.which("python") or "python"


def find_chrome(explicit: str | None) -> str:
    cands = []
    if explicit:
        cands.append(explicit)
    env = os.environ.get("CHROME_PATH")
    if env:
        cands.append(env)
    cands += [str(DEFAULT_CHROME), str(DEFAULT_EDGE), shutil.which("chrome") or "", shutil.which("msedge") or ""]
    for c in cands:
        if c and Path(c).exists():
            return str(c)
    raise SystemExit("找不到 Chrome/Edge，请用 --chrome 指定浏览器可执行文件路径")


def free_port() -> int:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


# --------------------------------------------------------------------------------------
# 项目文件读取
# --------------------------------------------------------------------------------------

def load_project(path: Path, *, robot_type: str | None, program_name: str | None,
                 connection_type: str | None) -> dict:
    warnings: list[str] = []
    raw: bytes
    fmt = "xml"
    zip_robot = None
    if path.suffix.lower() == ".srhs":
        fmt = "srhs"
        with zipfile.ZipFile(path) as zf:
            names = zf.namelist()
            target = None
            for n in names:
                if PurePosixPath(n).name.lower() == "abilixproject.srh":
                    target = n
                    break
            if target is None:
                raise SystemExit(f"[错误] {path} 内未找到 abilixProject.srh，条目：{names}")
            if len(names) > 1:
                warnings.append(f".srhs 内有 {len(names)} 个条目（预期 1 个）：{names}")
            raw = zf.read(target)
            try:
                zc = zf.comment.decode("ascii").strip()
                zip_robot = ZIP_COMMENT_TO_ROBOT.get(int(zc))
                if zip_robot is None:
                    warnings.append(f".srhs zip 注释 = {zc}（未知机器人枚举）")
            except Exception:
                warnings.append(".srhs zip 注释无法解析为机器人枚举数字")
    elif path.suffix.lower() in (".srh",):
        fmt = "srh"
        raw = path.read_bytes()
    else:
        fmt = "xml"
        raw = path.read_bytes()

    text, encoding = decode_bytes(raw)
    info: dict = {}
    info_raw = None
    m = INFO_RE.search(text)
    if m:
        info_raw = m.group(1)
        for k, v in re.findall(r"<([A-Za-z_][\w.]*)>([^<]*)</\1>", info_raw):
            info[k] = v.strip()
    else:
        warnings.append("未找到 <Abilix.ScratchProject.Info> 段（按纯项目 XML 处理）")

    project_xml = None
    ms = STRING_RE.search(text)
    if ms:
        project_xml = ms.group(1).strip()
    else:
        t = text.lstrip("\ufeff").strip()
        if t.startswith("<xml"):
            project_xml = t
            warnings.append("未找到 <Abilix.ScratchProject.ProjectString> 段，按整文件项目 XML 处理")
        else:
            raise SystemExit(f"[错误] {path} 既不是带标记的 .srh 也不是以 <xml 开头的项目 XML")

    if not project_xml:
        raise SystemExit("[错误] 项目 XML 为空")

    rt = (robot_type or info.get("RobotType") or zip_robot or "SKCON9").strip()
    pn = (program_name or info.get("DownloadProgramName") or path.stem).strip() or "ProgramA"
    ct = (connection_type or info.get("ConnectionType") or "USB").strip()

    # 静态 XML 校验 + 静态统计（浏览器之外的第一道检查）
    static = load_project_static(project_xml)

    return {
        "inputPath": str(path),
        "format": fmt,
        "encoding": encoding,
        "info": info,
        "infoRaw": info_raw,
        "zipRobotType": zip_robot,
        "robotType": rt,
        "connectionType": ct,
        "programName": pn,
        "projectXml": project_xml,
        "static": static,
        "warnings": warnings,
    }


# --------------------------------------------------------------------------------------
# 从真实 maingui.js / maingui.html 中抠出所需内容
# --------------------------------------------------------------------------------------

def _skip_js_string(src: str, i: int) -> int:
    """src[i] 是引号，返回字符串结束后的位置（跳过转义）。"""
    quote = src[i]
    i += 1
    n = len(src)
    while i < n:
        c = src[i]
        if c == "\\":
            i += 2
            continue
        if c == quote:
            return i + 1
        i += 1
    return n


def extract_js_function(src: str, marker: str) -> str | None:
    """从 JS 源码中抠出 `marker = function(...) {...}` 的完整赋值语句源码。"""
    idx = src.find(marker)
    if idx < 0:
        return None
    line_start = src.rfind("\n", 0, idx) + 1
    brace = src.find("{", idx)
    if brace < 0:
        return None
    depth = 0
    i = brace
    n = len(src)
    while i < n:
        c = src[i]
        if c == "{":
            depth += 1
            i += 1
        elif c == "}":
            depth -= 1
            i += 1
            if depth == 0:
                break
        elif c in ("'", '"', "`"):
            i = _skip_js_string(src, i)
        elif c == "/" and i + 1 < n and src[i + 1] == "/":
            j = src.find("\n", i)
            if j < 0:
                break
            i = j + 1
        elif c == "/" and i + 1 < n and src[i + 1] == "*":
            j = src.find("*/", i + 2)
            i = n if j < 0 else j + 2
        else:
            i += 1
    return src[line_start:i].strip()


def extract_toolbox(html_text: str, toolbox_id: str) -> str | None:
    """从 maingui.html 原样抠出 toolbox_xxx 的 XML。找不到/未闭合时返回 None 或补一个 </xml>。"""
    start = html_text.find('<xml id="%s"' % toolbox_id)
    if start < 0:
        return None
    end = html_text.find("</xml>", start)
    if end < 0:
        # 真实 maingui.html 里 toolbox_skcon2 恰好漏了 </xml>（浏览器会自动闭合），按 </body> 截断补齐
        end_body = html_text.find("</body>", start)
        if end_body < 0:
            end_body = len(html_text)
        return html_text[start:end_body].rstrip() + "\n</xml>"
    return html_text[start:end + len("</xml>")]


def load_ide_sources(web_root: Path) -> dict:
    blockly_code = web_root / "Blockly_Code"
    maingui_html_path = blockly_code / "maingui.html"
    maingui_js_path = blockly_code / "maingui.js"
    for p in (blockly_code, maingui_html_path, maingui_js_path):
        if not p.exists():
            raise SystemExit(f"[错误] 找不到 IDE Web 资源：{p}\n"
                             f"      （用 --web-root 指定 blockly_web 目录；默认 {DEFAULT_WEB_ROOT}）")
    html_text, _ = decode_bytes(maingui_html_path.read_bytes())
    js_text, _ = decode_bytes(maingui_js_path.read_bytes())
    get_python_src = extract_js_function(js_text, "maingui.getPythonCode = function")
    if not get_python_src:
        log("[警告] 未能从 maingui.js 抠出 getPythonCode，将使用等价兜底实现")
    toolboxes = {}
    for rid in set(ROBOT_TO_TOOLBOX.values()):
        tb = extract_toolbox(html_text, rid)
        if tb:
            toolboxes[rid] = tb
        else:
            log(f"[警告] maingui.html 中找不到工具箱 {rid}")
    return {"toolboxes": toolboxes, "getPythonCodeSource": get_python_src}


# --------------------------------------------------------------------------------------
# harness HTTP 服务
# --------------------------------------------------------------------------------------

class HarnessHandler(SimpleHTTPRequestHandler):
    server_version = "WERValidateHarness/" + TOOL_VERSION

    def log_message(self, fmt, *args):  # 静默
        pass

    def _send_bytes(self, data: bytes, content_type: str) -> None:
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        try:
            self.wfile.write(data)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def do_GET(self):
        p = urlparse(self.path).path
        if p == HARNESS_URL_PATH:
            self._send_bytes(self.server.harness_html, "text/html; charset=utf-8")
            return
        # 唯一一个 GBK 源文件：读取真实文件后仅做编码转换（代码内容一字不改）
        if p == "/Blockly_Code/blocks/procedures.js":
            try:
                raw = (Path(self.server.web_root) / "Blockly_Code" / "blocks" / "procedures.js").read_bytes()
                txt = raw.decode("gb18030")
            except Exception as e:  # pragma: no cover
                self.send_error(500, f"transcode failed: {e}")
                return
            self._send_bytes(txt.encode("utf-8"), "text/javascript; charset=utf-8")
            return
        if p == "/__api__/ping":
            self._send_bytes(b"ok", "text/plain")
            return
        super().do_GET()

    def do_POST(self):
        p = urlparse(self.path).path
        if p == "/__api__/result":
            length = int(self.headers.get("Content-Length") or 0)
            body = self.rfile.read(length) if length else b""
            try:
                data = json.loads(body.decode("utf-8"))
            except Exception as e:
                data = {"__postParseError": str(e), "rawLength": len(body)}
            with self.server.lock:
                self.server.results.append(data)
            self._send_bytes(b'{"ok":true}', "application/json; charset=utf-8")
            return
        self.send_error(404)


class HarnessServer:
    def __init__(self, web_root: Path, harness_html: str):
        handler = partial(HarnessHandler, directory=str(web_root))
        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        self.httpd.daemon_threads = True
        self.httpd.web_root = str(web_root)
        self.httpd.harness_html = harness_html.encode("utf-8")
        self.httpd.results = []
        self.httpd.lock = threading.Lock()
        self.port = self.httpd.server_address[1]
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, *exc):
        try:
            self.httpd.shutdown()
        except Exception:
            pass
        try:
            self.httpd.server_close()
        except Exception:
            pass

    @property
    def results(self):
        with self.httpd.lock:
            return list(self.httpd.results)

    @property
    def url(self):
        return f"http://127.0.0.1:{self.port}{HARNESS_URL_PATH}"


# --------------------------------------------------------------------------------------
# Chrome 调用 / 结果解析
# --------------------------------------------------------------------------------------

def run_chrome(browser: str, url: str, extra_args: list[str], profile_dir: Path,
               timeout: float, window_size: str = "1600,1000") -> dict:
    cmd = [
        browser,
        "--headless=new",
        "--disable-gpu",
        "--disable-dev-shm-usage",
        "--no-first-run",
        "--no-default-browser-check",
        "--disable-extensions",
        "--disable-background-networking",
        "--mute-audio",
        "--hide-scrollbars",
        f"--window-size={window_size}",
        f"--user-data-dir={profile_dir}",
    ] + extra_args + [url]
    t0 = time.time()
    info = {"cmd": cmd, "returncode": None, "timedOut": False, "stdout": "", "stderr": "",
            "elapsedMs": None}
    try:
        proc = subprocess.run(cmd, capture_output=True, timeout=timeout)
        info["returncode"] = proc.returncode
        info["stdout"] = proc.stdout.decode("utf-8", "replace")
        info["stderr"] = proc.stderr.decode("utf-8", "replace")
    except subprocess.TimeoutExpired as e:
        info["timedOut"] = True
        info["returncode"] = -999
        info["stdout"] = (e.stdout or b"").decode("utf-8", "replace") if isinstance(e.stdout, bytes) else (e.stdout or "")
        info["stderr"] = (e.stderr or b"").decode("utf-8", "replace") if isinstance(e.stderr, bytes) else (e.stderr or "")
    info["elapsedMs"] = round((time.time() - t0) * 1000)
    return info


RESULT_PRE_RE = re.compile(
    r"<pre[^>]*id=[\"']harness-result[\"'][^>]*>(.*?)</pre>", re.S | re.I
)


def parse_dom_result(dom: str) -> dict | None:
    m = RESULT_PRE_RE.search(dom)
    if not m:
        return None
    text = html_mod.unescape(m.group(1))
    try:
        return json.loads(text)
    except Exception:
        return None


def tail(text: str, n: int = 4000) -> str:
    return text if len(text) <= n else "...(截断)...\n" + text[-n:]


# --------------------------------------------------------------------------------------
# 生成 Python 的结构分析 / 对比
# --------------------------------------------------------------------------------------

DEF_RE = re.compile(r"^def\s+([A-Za-z_]\w*)\s*\(([^)]*)\)\s*:\s*$")
VAR_DECL_RE = re.compile(r"^([A-Za-z_]\w*)\s*=\s*None\s*$")
IMPORT_RE = re.compile(r"^(?:from\s+\S+\s+)?import\s+\S+")


def strip_python_comment(line: str) -> str:
    """去掉行内 Python 注释（引号内的 # 不动）。"""
    out = []
    quote = None
    i = 0
    n = len(line)
    while i < n:
        c = line[i]
        if quote:
            out.append(c)
            if c == "\\" and i + 1 < n:
                out.append(line[i + 1])
                i += 2
                continue
            if c == quote:
                quote = None
            i += 1
            continue
        if c in ("'", '"'):
            quote = c
            out.append(c)
            i += 1
            continue
        if c == "#":
            break
        out.append(c)
        i += 1
    return "".join(out)


def analyze_python_structure(text: str) -> dict:
    """把生成/参考 Python 拆成：preamble + 函数定义序列 + 尾部顶层语句。"""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = text.split("\n")
    funcs: list[dict] = []
    preamble: list[str] = []
    tail_lines: list[str] = []
    i = 0
    n = len(lines)
    current = None
    while i < n:
        line = lines[i]
        m = DEF_RE.match(line)
        if m:
            if current:
                funcs.append(current)
            current = {"name": m.group(1), "args": m.group(2).strip(),
                       "lines": [], "rawLines": [], "startLine": i + 1}
            i += 1
            continue
        if current is not None:
            is_indented = (line[:1] in (" ", "\t"))
            if line.strip() == "" or is_indented:
                current["rawLines"].append(line)
                i += 1
                continue
            funcs.append(current)
            current = None
            continue
        # 还没有进入任何函数：preamble
        preamble.append(line)
        i += 1
    if current:
        funcs.append(current)

    # 分离尾部：preamble 里最后一个非空行若在函数之后（被上面的流程算进 preamble 的只可能是文件头），
    # 这里按“首个 def 之前的内容”为 preamble，其余顶层行进入 tail。
    # analyze 的流程已保证进入函数后遇到顶层行会结束 current 并落到 else 分支之外的循环继续，
    # 但该顶层行会被丢弃 -> 重新扫描一遍顶部/尾部结构更稳妥。
    def_lines = [(idx, ln) for idx, ln in enumerate(lines) if DEF_RE.match(ln)]
    if def_lines:
        first_def = def_lines[0][0]
        preamble = lines[:first_def]
        # 找最后一个函数体的结束行：从末尾向前跳过空行，只要没有缩进就是尾部顶层行
        j = n - 1
        while j >= 0 and lines[j].strip() == "":
            j -= 1
        tail_start = n
        while j >= 0:
            ln = lines[j]
            if ln.strip() == "":
                j -= 1
                continue
            if ln[:1] in (" ", "\t") or DEF_RE.match(ln):
                break
            tail_start = j
            j -= 1
        # 函数区 = preamble 之后 ~ tail_start
        funcs = []
        cur = None
        for k in range(first_def, tail_start):
            ln = lines[k]
            m = DEF_RE.match(ln)
            if m:
                if cur:
                    funcs.append(cur)
                cur = {"name": m.group(1), "args": m.group(2).strip(),
                       "lines": [], "rawLines": [], "startLine": k + 1}
                continue
            if cur is not None:
                cur["rawLines"].append(ln)
        if cur:
            funcs.append(cur)
        tail_lines = lines[tail_start:]
    else:
        preamble = lines
        tail_lines = []

    # 归一化每个函数体
    out_funcs = []
    for f in funcs:
        norm = []
        raw_kept = []
        globals_line = None
        for ln in f["rawLines"]:
            s = strip_python_comment(ln).strip()
            if not s:
                continue
            if s.startswith("global "):
                globals_line = s
            norm.append(s)
            raw_kept.append(s)
        out_funcs.append({
            "name": f["name"],
            "args": f["args"],
            "startLine": f["startLine"],
            "body": norm,
            "globalLine": globals_line,
        })

    # preamble 解析
    header = None
    imports = []
    robot_init = []
    var_decls = []
    other = []
    for ln in preamble:
        raw = ln.strip()
        if not raw:
            continue
        if raw.startswith("#<"):
            header = raw
            continue
        s = strip_python_comment(ln).strip()
        if not s:
            continue
        if IMPORT_RE.match(s):
            imports.append(s)
        elif re.match(r"^robot\s*=\s*Robot\(\)\s*$", s):
            robot_init.append(s)
        elif VAR_DECL_RE.match(s):
            var_decls.append(VAR_DECL_RE.match(s).group(1))
        else:
            other.append(s)
    tail = [l.strip() for l in tail_lines if l.strip()]

    return {
        "header": header,
        "imports": imports,
        "robotInit": robot_init,
        "varDecls": var_decls,
        "otherPreamble": other,
        "functions": out_funcs,
        "functionNames": [f["name"] for f in out_funcs],
        "tail": tail,
        "lineCount": len(lines),
        "_lines": lines,
    }


def _first_diff(a: list[str], b: list[str]) -> dict | None:
    limit = min(len(a), len(b))
    for i in range(limit):
        if a[i] != b[i]:
            return {"index": i + 1, "ref": a[i], "gen": b[i]}
    if len(a) != len(b):
        return {"index": limit + 1,
                "ref": a[limit] if limit < len(a) else "<缺少该行>",
                "gen": b[limit] if limit < len(b) else "<缺少该行>"}
    return None


def compare_python(ref_text: str, gen_text: str, ref_name: str) -> dict:
    ref = analyze_python_structure(ref_text)
    gen = analyze_python_structure(gen_text)
    ref_funcs = {f["name"]: f for f in ref["functions"]}
    gen_funcs = {f["name"]: f for f in gen["functions"]}

    details = []
    identical = 0
    for name in ref["functionNames"]:
        rf = ref_funcs[name]
        gf = gen_funcs.get(name)
        if gf is None:
            details.append({"name": name, "status": "missing_in_generated"})
            continue
        args_equal = rf["args"] == gf["args"]
        body_equal = rf["body"] == gf["body"]
        rec = {"name": name, "argsEqual": args_equal, "bodyEqual": body_equal,
               "refArgs": rf["args"], "genArgs": gf["args"],
               "refBodyLines": len(rf["body"]), "genBodyLines": len(gf["body"])}
        if args_equal and body_equal:
            rec["status"] = "identical"
            identical += 1
        else:
            rec["status"] = "different"
            rec["firstDiff"] = _first_diff(rf["body"], gf["body"])
        details.append(rec)

    extra = [n for n in gen["functionNames"] if n not in ref_funcs]
    ref_count = len(ref["functionNames"])
    gen_count = len(gen["functionNames"])
    ref_user = [n for n in ref["functionNames"] if n != "main"]
    user_identical = sum(1 for d in details if d["status"] == "identical" and d["name"] != "main")
    main_detail = next((d for d in details if d["name"] == "main"), None)

    preamble = {
        "headerEqual": ref["header"] == gen["header"],
        "refHeader": ref["header"],
        "genHeader": gen["header"],
        "importsEqual": sorted(ref["imports"]) == sorted(gen["imports"]),
        "refImports": ref["imports"],
        "genImports": gen["imports"],
        "robotInitEqual": ref["robotInit"] == gen["robotInit"],
        "varDeclsSetEqual": set(ref["varDecls"]) == set(gen["varDecls"]),
        "varDeclsOrderEqual": ref["varDecls"] == gen["varDecls"],
        "refVarDeclCount": len(ref["varDecls"]),
        "genVarDeclCount": len(gen["varDecls"]),
        "varDeclsOnlyInRef": sorted(set(ref["varDecls"]) - set(gen["varDecls"])),
        "varDeclsOnlyInGen": sorted(set(gen["varDecls"]) - set(ref["varDecls"])),
        "otherPreambleEqual": ref["otherPreamble"] == gen["otherPreamble"],
        "refOtherPreamble": ref["otherPreamble"],
        "genOtherPreamble": gen["otherPreamble"],
        "tailEqual": ref["tail"] == gen["tail"],
        "refTail": ref["tail"],
        "genTail": gen["tail"],
    }

    # 归一化全文 diff（函数体 + 头部），用于人工复核
    def render_norm(st):
        out = []
        if st["header"]:
            out.append(st["header"])
        out.extend("import: " + x for x in st["imports"])
        out.extend("robot: " + x for x in st["robotInit"])
        out.extend("var: " + x for x in st["varDecls"])
        out.extend("other: " + x for x in st["otherPreamble"])
        for f in st["functions"]:
            out.append(f"def {f['name']}({f['args']}):")
            out.extend("    " + b for b in f["body"])
        out.extend("tail: " + x for x in st["tail"])
        return out

    norm_ref = render_norm(ref)
    norm_gen = render_norm(gen)
    diff_lines = list(difflib.unified_diff(norm_ref, norm_gen,
                                           fromfile=f"ref:{ref_name}", tofile="generated",
                                           lineterm="", n=2))

    allowed = []
    if preamble["refHeader"] != preamble["genHeader"]:
        allowed.append(
            f"文件头不来自同一程序名：参考 {preamble['refHeader']!r} vs 生成 {preamble['genHeader']!r}"
            "（--program-name 可对齐）")
    if not preamble["varDeclsOrderEqual"] and preamble["varDeclsSetEqual"]:
        allowed.append("变量声明集合一致但顺序不同（变量模型遍历顺序差异，语义无关）")

    result = {
        "reference": ref_name,
        "refFunctionCount": ref_count,
        "genFunctionCount": gen_count,
        "refUserFunctionCount": len(ref_user),
        "userFunctionsIdentical": user_identical,
        "userAgreementRate": round(user_identical / len(ref_user), 4) if ref_user else None,
        "mainIdentical": bool(main_detail and main_detail["status"] == "identical"),
        "identicalFunctions": identical,
        "agreementRate": round(identical / ref_count, 4) if ref_count else None,
        "rawTextIdenticalNormalized": (
            ref_text.replace("\r\n", "\n").replace("\r", "\n")
            == gen_text.replace("\r\n", "\n").replace("\r", "\n")
        ),
        "signaturesAllEqual": all(d.get("argsEqual") for d in details if d["status"] != "missing_in_generated"),
        "bodiesAllIdentical": all(d.get("bodyEqual") for d in details if d["status"] != "missing_in_generated"),
        "missingInGenerated": [n for n in ref["functionNames"] if n not in gen_funcs],
        "extraInGenerated": extra,
        "functions": details,
        "preamble": preamble,
        "allowedDifferences": allowed,
        "normalizedDiff": diff_lines,
        "normalizedDiffLineCount": len(diff_lines),
        "identicalModuloAllowedDiffs": (
            identical == ref_count and not extra
            and preamble["importsEqual"] and preamble["robotInitEqual"]
            and preamble["varDeclsSetEqual"] and preamble["otherPreambleEqual"]
            and preamble["tailEqual"]
        ),
    }
    return result


# --------------------------------------------------------------------------------------
# 生成 Python 分析（浏览器之外的独立复核）
# --------------------------------------------------------------------------------------

def analyze_generated(code: str) -> dict:
    st = analyze_python_structure(code)
    return {
        "lineCount": st["lineCount"],
        "header": st["header"],
        "imports": st["imports"],
        "robotInit": st["robotInit"],
        "varDeclCount": len(st["varDecls"]),
        "varDecls": st["varDecls"],
        "otherPreamble": st["otherPreamble"],
        "defCount": len(st["functions"]),
        "defs": [{"name": f["name"], "args": f["args"], "bodyLines": len(f["body"]),
                  "globalLine": f["globalLine"]} for f in st["functions"]],
        "tail": st["tail"],
    }


def write_text_lf(path: Path, text: str) -> None:
    """按 IDE 生成文件的风格写 UTF-8 + LF（不随 Windows 自动转 CRLF）。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write(text)


def py_compile_check(code: str, work_dir: Path) -> dict:
    py = find_python_exe()
    target = work_dir / "generated_syntax_check.py"
    write_text_lf(target, code)
    t0 = time.time()
    try:
        proc = subprocess.run([py, "-m", "py_compile", str(target)],
                              capture_output=True, timeout=120)
        return {
            "ok": proc.returncode == 0,
            "returncode": proc.returncode,
            "cmd": [py, "-m", "py_compile", str(target)],
            "stdout": proc.stdout.decode("utf-8", "replace"),
            "stderr": proc.stderr.decode("utf-8", "replace"),
            "elapsedMs": round((time.time() - t0) * 1000),
            "file": str(target),
        }
    except subprocess.TimeoutExpired:
        return {"ok": False, "returncode": -999, "stderr": "py_compile 超时",
                "elapsedMs": round((time.time() - t0) * 1000), "file": str(target)}
    except Exception as e:  # pragma: no cover
        return {"ok": False, "error": str(e), "file": str(target)}


# --------------------------------------------------------------------------------------
# harness 结果 + 服务端复核 -> 最终结果
# --------------------------------------------------------------------------------------

def evaluate_harness_result(payload: dict | None, dom: str, chrome_info: dict) -> tuple[dict, list[str]]:
    """返回 (harness 结果, 错误列表)。

    成功时返回 harness 页面 POST 过来的结果本身（含 load/generation/... 键）；
    失败时返回 {"payload": None, "domSnippet":..., "chromeStderrTail":..., "chrome":...}。
    """
    errors: list[str] = []
    chrome_meta = {k: chrome_info.get(k) for k in ("returncode", "timedOut", "elapsedMs")}
    if payload is None:
        payload = parse_dom_result(dom)
        if payload is not None:
            errors.append("POST 结果缺失，已从 DOM <pre id=harness-result> 兜底解析")
    if payload is None:
        snippet = dom[:2000]
        errors.append("harness 未返回结果（页面可能加载失败）")
        return {"payload": None, "domSnippet": snippet,
                "chromeStderrTail": tail(chrome_info.get("stderr", "")),
                "chrome": chrome_meta}, errors
    if not isinstance(payload, dict) or "load" not in payload:
        errors.append(f"harness 返回数据格式异常：{str(payload)[:500]}")
        return {"payload": None, "domSnippet": str(payload)[:2000],
                "chromeStderrTail": tail(chrome_info.get("stderr", "")),
                "chrome": chrome_meta}, errors
    if chrome_info.get("timedOut"):
        errors.append("Chrome 运行超时（--timeout 可调大）")
    if not payload.get("ok"):
        errors.append("harness 报告 ok=false（见 windowErrors/consoleErrors/load.error）")
    return payload, errors


def make_evidence_name(input_path: str | Path | None, mode: str) -> str:
    if mode == "param":
        return "param_test"
    if input_path:
        return Path(input_path).stem
    return "project"


def summarize_text(result: dict) -> str:
    lines: list[str] = []
    proj = result.get("project", {})
    harness = result.get("harness") or {}
    lines.append("=" * 78)
    lines.append(f"WER headless 验证报告   生成时间 {result['meta']['generatedAt']}")
    lines.append("=" * 78)
    if proj:
        lines.append(f"输入文件    : {proj.get('inputPath')}  ({proj.get('format')}, {proj.get('encoding')})")
        lines.append(f"机器人类型  : {proj.get('robotType')}    连接: {proj.get('connectionType')}    程序名: {proj.get('programName')}")
        info = proj.get("info") or {}
        if info:
            lines.append(f"项目 Info   : {json.dumps(info, ensure_ascii=False)}")
        st = proj.get("static") or {}
        lines.append(f"XML 静态校验: {'通过' if st.get('xmlValid') else '失败: ' + str(st.get('xmlError'))}"
                     f"    静态顶层块: {st.get('topBlockCount')}    变量: {st.get('variablesCount')}"
                     f"    静态函数定义: {len((st.get('procedures') or {}).get('defnoreturn', []))}")
        for w in proj.get("warnings") or []:
            lines.append(f"  [警告] {w}")
    lines.append("")
    if not harness or "load" not in harness:
        lines.append("!! harness 未返回有效结果")
        lines.append(f"   Chrome returncode={harness.get('chrome', {}).get('returncode')} "
                     f"timedOut={harness.get('chrome', {}).get('timedOut')}")
        if harness.get("domSnippet"):
            lines.append("   DOM 片段: " + harness["domSnippet"][:800].replace("\n", " "))
        if harness.get("chromeStderrTail"):
            lines.append("   Chrome stderr 尾部: " + harness["chromeStderrTail"][-1500:])
        for e in (result.get("errors") or []):
            lines.append("   [错误] " + str(e)[:3000])
        return "\n".join(lines)

    h = harness
    load = h.get("load") or {}
    lines.append(f"[1] 加载项目 XML : {'成功' if load.get('success') else '失败'}  ({load.get('ms')} ms)")
    if load.get("error"):
        lines.append(f"    错误: {str(load['error']).splitlines()[0] if load.get('error') else ''}")
    ws = h.get("workspace") or {}
    lines.append(f"    顶层块数: {ws.get('topBlockCount')}    总块数: {ws.get('totalBlockCount')}"
                 f"    变量数: {ws.get('variableCount')}")
    lines.append(f"    顶层块类型: {json.dumps(ws.get('topBlocksByType') or {}, ensure_ascii=False)}")
    rs = ws.get("render") or {}
    if rs:
        lines.append(f"    渲染检查: 已渲染块 {rs.get('renderedBlockCount')}/{ws.get('totalBlockCount')}"
                     f"    SVG 根 {rs.get('renderedSvgRootCount')}    0 尺寸块 {rs.get('zeroSizeBlockCount')}"
                     f"    警告 {rs.get('warningCount')}    禁用 {rs.get('disabledBlockCount')}"
                     f"    mainWorkspace 正确 {rs.get('mainWorkspaceIsThis')}")
        for w in (rs.get("warnings") or [])[:5]:
            lines.append(f"      [块警告] {w.get('type')}: {w.get('text')}")
    procs = h.get("procedures") or {}
    nr = procs.get("defnoreturn") or []
    rr = procs.get("defreturn") or []
    lines.append(f"[2] 函数定义     : 无返回值 {len(nr)} 个, 有返回值 {len(rr)} 个")
    for rec in nr:
        lines.append(f"    - {rec['name']}({', '.join(rec.get('args') or [])})")
    for rec in rr:
        lines.append(f"    - [return] {rec['name']}({', '.join(rec.get('args') or [])})")
    fx = h.get("flyout") or {}
    cat = fx.get("categoryXml") or {}
    lines.append(f"[3] 函数分类 flyout（Blockly.Procedures.flyoutCategory）: {cat.get('count')} 个 XML 块")
    if cat.get("error"):
        lines.append(f"    错误: {cat['error']}")
    for rec in (cat.get("blocks") or []):
        name = rec.get("mutationName") or rec.get("fieldName") or "?"
        args = rec.get("args") or []
        lines.append(f"    - {rec.get('type')}  name={name!r}  args={args}")
    inst = fx.get("instantiate") or {}
    if inst.get("error"):
        lines.append(f"[4] 真实 flyout 实例化: 失败 {inst['error']}")
    else:
        irs = inst.get("render") or {}
        lines.append(f"[4] 真实 flyout 实例化: {'成功' if inst.get('blockCount') else '空'} "
                     f"({inst.get('blockCount')} 块, 经工具箱树真实选中={inst.get('viaTreeSelection')})"
                     f"    渲染 {irs.get('renderedBlockCount')}/{inst.get('blockCount')}"
                     f"    SVG 根 {irs.get('renderedSvgRootCount')}    0 尺寸 {irs.get('zeroSizeBlockCount')}")
        for rec in (inst.get("blocks") or [])[:60]:
            name = rec.get("callName") or rec.get("name") or "?"
            lines.append(f"    - {rec.get('type')}  name={name!r}  args={rec.get('args') or []}  inputs={rec.get('inputs')}")
        if len(inst.get("blocks") or []) > 60:
            lines.append(f"    ...（共 {len(inst.get('blocks'))} 块，完整列表见 JSON）")
    gen = h.get("generation") or {}
    lines.append(f"[5] Python 生成  : {'成功' if gen.get('success') else '失败'}"
                 f"  ({gen.get('ms')} ms, 使用 maingui.js 原始 getPythonCode={gen.get('usedRealSource')})")
    if gen.get("error"):
        lines.append(f"    错误: {gen['error']}")
    analysis = result.get("analysis")
    if analysis:
        lines.append(f"    长度/行数: {analysis.get('lineCount')} 行")
        lines.append(f"    文件头: {analysis.get('header')!r}    def 数: {analysis.get('defCount')}"
                     f"    import: {analysis.get('imports')}")
        lines.append(f"    变量声明: {analysis.get('varDeclCount')} 个   尾部: {analysis.get('tail')}")
    sc = result.get("syntaxCheck") or {}
    lines.append(f"[6] py_compile  : {'通过' if sc.get('ok') else '失败'}")
    if not sc.get("ok"):
        lines.append(f"    stderr: {tail(str(sc.get('stderr') or sc.get('error') or ''), 2000)}")
    cmps = result.get("comparison")
    if cmps:
        lines.append("")
        lines.append(f"[7] 与参考 {cmps['reference']} 对比")
        lines.append(f"    用户函数（不含 main）: {cmps['userFunctionsIdentical']}/{cmps['refUserFunctionCount']} 完全一致"
                     f"    一致率 {cmps['userAgreementRate']}    main 一致: {cmps['mainIdentical']}")
        lines.append(f"    全部 def 数: 参考 {cmps['refFunctionCount']} / 生成 {cmps['genFunctionCount']}"
                     f"    完全一致: {cmps['identicalFunctions']}/{cmps['refFunctionCount']}")
        lines.append(f"    参数签名全部相同: {cmps['signaturesAllEqual']}    函数体全部相同: {cmps['bodiesAllIdentical']}")
        lines.append(f"    缺失函数: {cmps['missingInGenerated']}    多出函数: {cmps['extraInGenerated']}")
        p = cmps["preamble"]
        lines.append(f"    import 集合相同: {p['importsEqual']}    robot=Robot() 行: {p['robotInitEqual']}")
        lines.append(f"    变量声明集合相同: {p['varDeclsSetEqual']}  (参考 {p['refVarDeclCount']} / 生成 {p['genVarDeclCount']})")
        lines.append(f"    变量声明顺序相同: {p['varDeclsOrderEqual']}    尾部语句相同: {p['tailEqual']}")
        lines.append(f"    原始文本（忽略换行风格）完全相同: {cmps['rawTextIdenticalNormalized']}")
        for a in cmps.get("allowedDifferences") or []:
            lines.append(f"    [允许的差异] {a}")
        diffs = [d for d in cmps["functions"] if d["status"] == "different"]
        for d in diffs[:20]:
            fd = d.get("firstDiff") or {}
            lines.append(f"    [差异] {d['name']}: argsEqual={d['argsEqual']} bodyEqual={d['bodyEqual']}"
                         f" 首个不同行#{fd.get('index')}\n        ref: {fd.get('ref')}\n        gen: {fd.get('gen')}")
        if len(diffs) > 20:
            lines.append(f"    ...共 {len(diffs)} 个函数有差异，完整信息见 JSON")
        lines.append(f"    归一化 diff 行数: {cmps['normalizedDiffLineCount']}")
        lines.append(f"    等价（除允许差异外）: {cmps['identicalModuloAllowedDiffs']}")
    pt = result.get("paramTest")
    if pt:
        lines.append("")
        lines.append(f"[8] 带参数函数结论: {'通过' if pt.get('passed') else '失败'} "
                     f"({pt.get('passedCount')}/{pt.get('totalCount')})")
        for c in pt.get("checks") or []:
            lines.append(f"    [{'PASS' if c['pass'] else 'FAIL'}] {c['name']}: {c.get('detail', '')}")
    dt = result.get("dragTest")
    if dt:
        lines.append("")
        lines.append(f"[9] 拖拽可用性（函数分类 flyout → createBlock 拖出 → 接入 start → 生成 Python）: "
                     f"{'通过' if dt.get('passed') else '失败'} ({dt.get('passedCount')}/{dt.get('totalCount')})")
        for c in dt.get("checks") or []:
            lines.append(f"    [{'PASS' if c['pass'] else 'FAIL'}] {c['name']}: {c.get('detail', '')}")
    nt = result.get("nativeTest")
    if nt:
        lines.append("")
        lines.append(f"[10] 原生函数块（工具箱“我的函数”分类 → flyout createBlock 拖出 → 接入 start → 生成 Python）: "
                     f"{'通过' if nt.get('passed') else '失败'} ({nt.get('passedCount')}/{nt.get('totalCount')})")
        for c in nt.get("checks") or []:
            lines.append(f"    [{'PASS' if c['pass'] else 'FAIL'}] {c['name']}: {c.get('detail', '')}")
    npl = result.get("nativePrelude")
    if npl:
        lines.append("")
        if npl.get("skipped"):
            lines.append(f"[11] 原生块 prelude 注入回归: 跳过（{npl['skipped']}）")
        else:
            lines.append(f"[11] 原生块 prelude 注入回归: {'通过' if npl.get('ok') else '失败'}"
                         f"（项目原生块数 {npl.get('projectNativeBlockCount')}，"
                         f"期望注入={npl.get('expectedInjection')}，实际注入={npl.get('detectedInjection')}，"
                         f"prelude {npl.get('preludeChars')} 字符，userlib 函数 {npl.get('userlibFunctionCount')} 个）")
    if (result.get("meta") or {}).get("semanticReport"):
        lines.append("")
        lines.append(f"语义核对报告: {result['meta']['semanticReport']}")
    if gen.get("code"):
        lines.append("")
        lines.append("生成的 Python 全文见 --py 输出 / JSON generated.code；"
                     "可另传 --screenshot 截图。")
    lines.append("")
    errs = result.get("errors") or []
    if errs:
        lines.append("注意:")
        for e in errs:
            lines.append(f"  - {e}")
    lines.append(f"结论: {'通过' if result.get('ok') else '失败'}")
    return "\n".join([ln for ln in lines if ln != ""])


# --------------------------------------------------------------------------------------
# 带参数函数断言
# --------------------------------------------------------------------------------------

def build_param_test(harness: dict, generated_code: str, syntax: dict) -> dict:
    checks: list[dict] = []

    def add(name: str, ok: bool, detail: str = ""):
        checks.append({"name": name, "pass": bool(ok), "detail": detail})

    load = harness.get("load") or {}
    add("项目加载成功", bool(load.get("success")), str(load.get("error") or ""))
    ws = harness.get("workspace") or {}
    add("顶层块数=2（1 个函数定义 + 1 个 start）", ws.get("topBlockCount") == 2,
        f"实际 {ws.get('topBlockCount')}: {ws.get('topBlocksByType')}")

    procs = harness.get("procedures") or {}
    nr = procs.get("defnoreturn") or []
    found = [p for p in nr if p.get("name") == "func_MoveCm"]
    add("procedures 列表中 func_MoveCm 存在", len(found) == 1, json.dumps(nr, ensure_ascii=False))
    add("func_MoveCm 的参数为 ['cm']", bool(found) and found[0].get("args") == ["cm"],
        json.dumps(found[0].get("args") if found else None))

    cat = (harness.get("flyout") or {}).get("categoryXml") or {}
    cat_calls = [b for b in (cat.get("blocks") or [])
                 if b.get("type") == "procedures_callnoreturn" and b.get("mutationName") == "func_MoveCm"]
    add("flyoutCategory 生成 func_MoveCm 的调用块 XML", len(cat_calls) == 1,
        json.dumps(cat.get("blocks"), ensure_ascii=False)[:600])
    add("该调用块 XML 的 mutation 带参数 cm",
        bool(cat_calls) and cat_calls[0].get("args") == ["cm"],
        json.dumps(cat_calls[0].get("args") if cat_calls else None))

    inst = (harness.get("flyout") or {}).get("instantiate") or {}
    inst_calls = [b for b in (inst.get("blocks") or [])
                  if b.get("type") == "procedures_callnoreturn" and b.get("callName") == "func_MoveCm"]
    add("真实 flyout 实例化出 func_MoveCm 调用块", len(inst_calls) == 1,
        json.dumps(inst.get("blocks"), ensure_ascii=False)[:600])
    add("实例化调用块的 arguments_=['cm'] 且有 ARG0 值输入",
        bool(inst_calls) and inst_calls[0].get("args") == ["cm"]
        and "ARG0" in (inst_calls[0].get("inputs") or []),
        json.dumps(inst_calls[0] if inst_calls else None, ensure_ascii=False))

    code = generated_code or ""
    def_match = re.search(r"^def func_MoveCm\(cm\):$", code, re.M)
    add("生成 Python 含 `def func_MoveCm(cm):`", bool(def_match),
        (def_match.group(0) if def_match else "未找到"))
    add("函数体用参数：`var_last_cm = cm`",
        bool(re.search(r"^\s+var_last_cm = cm\s*$", code, re.M)), "")
    add("函数体用参数：`time.sleep(cm)`",
        bool(re.search(r"^\s+time\.sleep\(cm\)\s*$", code, re.M)), "")
    # global 行必须包含工程变量 var_last_cm，但不能包含参数 cm
    func_block = None
    if def_match:
        start = def_match.start()
        rest = code[start:]
        m = re.search(r"\n(?=\S)", rest[1:])
        func_block = rest[: (m.start() + 1)] if m else rest
    gl = re.search(r"^\s+global ([^\n]+)$", func_block or "", re.M)
    gl_names = [x.strip() for x in gl.group(1).split(",")] if gl else []
    add("func_MoveCm 内 global 含 var_last_cm", "var_last_cm" in gl_names, str(gl_names))
    add("func_MoveCm 内 global 不含参数 cm（参数被正确排除）", "cm" not in gl_names, str(gl_names))
    add("main 中调用 func_MoveCm(10)", bool(re.search(r"^\s+func_MoveCm\(10\)\s*$", code, re.M)), "")
    add("main 中调用 func_MoveCm(20)", bool(re.search(r"^\s+func_MoveCm\(20\)\s*$", code, re.M)), "")
    add("py_compile 语法检查通过", bool(syntax.get("ok")), tail(str(syntax.get("stderr") or ""), 800))

    passed = sum(1 for c in checks if c["pass"])
    return {"checks": checks, "passed": passed == len(checks), "passedCount": passed,
            "totalCount": len(checks)}


# --------------------------------------------------------------------------------------
# “从函数分类拖出调用块”断言
# --------------------------------------------------------------------------------------

def build_drag_test(project: dict, harness: dict, generated_code: str, syntax: dict) -> dict:
    checks: list[dict] = []

    def add(name: str, ok: bool, detail: str = ""):
        checks.append({"name": name, "pass": bool(ok), "detail": detail})

    static = project.get("static") or {}
    defs = (static.get("procedures") or {}).get("defnoreturn", [])
    expected = {d.get("name"): (d.get("args") or []) for d in defs}

    add("项目加载成功", bool((harness.get("load") or {}).get("success")),
        str((harness.get("load") or {}).get("error") or ""))
    drag = harness.get("drag") or {}
    add("拖拽路径执行成功（Flyout.createBlock）", bool(drag.get("ok")), str(drag.get("error") or ""))
    created = drag.get("created") or []
    add(f"从 flyout 拖出的调用块数量 = 函数定义数（{len(expected)}）",
        len(created) == len(expected), f"实际 {len(created)}")
    names = [c.get("name") for c in created]
    add("拖出的调用块覆盖全部函数", set(names) == set(expected),
        f"created={names[:10]}{'...' if len(names) > 10 else ''}")
    bad_args = [c for c in created if c.get("args") != expected.get(c.get("name"))]
    add("拖出调用块的参数列表与函数定义一致", not bad_args,
        json.dumps([(c.get("name"), c.get("args"), expected.get(c.get("name"))) for c in bad_args],
                   ensure_ascii=False)[:600])
    not_rendered = [c for c in created if not (c.get("rendered") and c.get("svgOk"))]
    add("拖出的调用块均已渲染（rendered + SVG root）", not not_rendered,
        json.dumps(not_rendered, ensure_ascii=False)[:500])

    code = generated_code or ""
    m = re.search(r"^def main\(\):.*?(?=^main\(\)#program entry)", code, re.M | re.S)
    main_code = m.group(0) if m else ""
    add("生成的 Python 里有 main()", bool(m), "")
    missing = [n for n in names if n and not re.search(re.escape(n) + r"\(", main_code)]
    add("main 中包含全部拖出函数的调用", not missing, f"缺失 {missing}")
    # 注意：start 里本来就有示例调用，可能与拖出的调用同名；用“完整调用表达式 + rfind（最后出现）”
    # 定位拖出的那一次调用（拖出的调用接在示例之后，位于 main 末尾）。
    exprs = []
    for c in created:
        if not c.get("name"):
            continue
        args = c.get("argValues") or []
        exprs.append([c["name"], c["name"] + "(" + ", ".join(args) + ")"])
    positions = [[n, main_code.rfind(expr)] for n, expr in exprs]
    ordered = bool(positions) and all(
        positions[i][1] >= 0 and (i == 0 or positions[i][1] > positions[i - 1][1])
        for i in range(len(positions)))
    add("main 中拖出调用的顺序与拖出顺序一致（按完整调用表达式定位）", ordered,
        json.dumps(positions[:10], ensure_ascii=False))
    text_calls = [c for c in created if c.get("argValues") and "'hello'" in c.get("argValues")]
    if text_calls:
        c = text_calls[0]
        expr = c["name"] + "(" + ", ".join(c["argValues"]) + ")"
        add(f"main 中含文本参数调用 {expr}", bool(re.search(re.escape(expr), main_code)), "")
    numeric = [c for c in created if c.get("args") and c.get("argValues")]
    if numeric:
        c = numeric[0]
        expr = c["name"] + "(" + ", ".join(c["argValues"]) + ")"
        add(f"main 中含数值参数调用 {expr}", bool(re.search(re.escape(expr), main_code)), "")
    funcs = re.findall(r"^def ([A-Za-z_]\w*)\(", code, re.M)
    missing_defs = [n for n in expected if n not in funcs]
    add(f"生成代码仍保留全部 {len(expected)} 个函数定义", not missing_defs, f"缺失 {missing_defs}")
    add("py_compile 语法检查通过", bool(syntax.get("ok")),
        tail(str(syntax.get("stderr") or ""), 600))

    passed = sum(1 for c in checks if c["pass"])
    return {"checks": checks, "passed": passed == len(checks), "passedCount": passed,
            "totalCount": len(checks), "createdCount": len(created)}


# --------------------------------------------------------------------------------------
# 语义核对报告（块结构 vs 生成 Python + 自动风险扫描）
# --------------------------------------------------------------------------------------

NS = "{http://www.w3.org/1999/xhtml}"


def _et_local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag


def _xml_block_tree(xml_block, depth: int = 0) -> dict:
    """把 <block> XML 元素转成可读的嵌套字典（块结构）。"""
    node = {"type": xml_block.get("type"), "fields": [], "args": [], "mutationName": None,
            "values": [], "statements": [], "next": None, "depth": depth}
    for sub in list(xml_block):
        ln = _et_local(sub.tag)
        if ln == "field":
            node["fields"].append([sub.get("name"), (sub.text or "").strip()])
        elif ln == "mutation":
            node["mutationName"] = sub.get("name")
            node["args"] = [a.get("name") for a in list(sub) if _et_local(a.tag) == "arg"]
        elif ln == "value":
            child = sub.find(NS + "block")
            if child is not None:
                node["values"].append([sub.get("name"), _xml_block_tree(child, depth + 1)])
        elif ln == "statement":
            child = sub.find(NS + "block")
            if child is not None:
                node["statements"].append([sub.get("name"), _xml_block_tree(child, depth + 1)])
        elif ln == "next":
            child = sub.find(NS + "block")
            if child is not None:
                node["next"] = _xml_block_tree(child, depth)
    return node


def _render_block_tree(node: dict | None, indent: int = 0, lines: list[str] | None = None) -> str:
    if lines is None:
        lines = []
    if node is None:
        return ""
    pad = "  " * indent
    extra = ""
    if node["mutationName"]:
        extra += f" [call {node['mutationName']}({', '.join(node['args'])})]"
    if node["fields"]:
        fs = []
        for k, v in node["fields"]:
            v = v.replace("\n", "\\n")
            if len(v) > 60:
                v = v[:57] + "..."
            fs.append(f"{k}={v!r}")
        extra += " {" + ", ".join(fs) + "}"
    lines.append(f"{pad}- {node['type']}{extra}")
    for name, child in node["values"]:
        lines.append(f"{pad}    .[{name}]")
        _render_block_tree(child, indent + 2, lines)
    for name, child in node["statements"]:
        lines.append(f"{pad}    .statement[{name}]")
        _render_block_tree(child, indent + 2, lines)
    if node.get("next"):
        lines.append(f"{pad}    ->")
        _render_block_tree(node["next"], indent + 1, lines)
    return "\n".join(lines)


def _walk_blocks(node: dict | None, visit):
    if node is None:
        return
    visit(node)
    for _, child in node["values"] + node["statements"]:
        _walk_blocks(child, visit)
    _walk_blocks(node.get("next"), visit)


def _subtree_has_type(node: dict | None, types: set[str]) -> bool:
    found = [False]

    def visit(n):
        if n["type"] in types:
            found[0] = True
    _walk_blocks(node, visit)
    return found[0]


RISKY_NOT_COMBINATORS = {"logic_operation", "logic_negate"}
RISKY_NEST_IN_MATH = {"math_compare", "logic_compare"}
MATH_WRAPPERS = {"math_op", "robot_math_unary_operation", "robot_math_rounding",
                 "robot_math_trigonometric_function", "logic_operation"}


def scan_semantic_risks(project_xml: str) -> list[dict]:
    """扫描块结构里可能因本 IDE 生成器括号/优先级问题而语义不符的用法。"""
    import xml.etree.ElementTree as ET
    risks: list[dict] = []
    try:
        root = ET.fromstring(project_xml)
    except Exception as e:
        return [{"level": "error", "scope": "-", "message": f"XML 解析失败：{e}"}]

    def scan(node, scope):
        t = node["type"]
        if t == "while_cmp":
            bool_node = next((c for name, c in node["values"] if name == "bool"), None)
            if bool_node is not None:
                if _subtree_has_type(bool_node, RISKY_NOT_COMBINATORS):
                    risks.append({"level": "high", "scope": scope,
                                  "message": f"重复执行直到 的条件里含 and/or/not 组合：生成器输出 'while not <条件>'，"
                                             f"而本 IDE 的括号补全被注释掉（core/generator.js L272），"
                                             f"`while not a and b` 会被 Python 解析成 `(not a) and b`，语义可能相反"})
                elif bool_node["type"] != "math_compare":
                    risks.append({"level": "low", "scope": scope,
                                  "message": f"重复执行直到 的条件块是 {bool_node['type']}（不是单比较块），"
                                             f"`while not <条件>` 的优先级需要人工确认"})
        if t in MATH_WRAPPERS:
            for name, child in node["values"]:
                if child is not None and child["type"] in RISKY_NEST_IN_MATH:
                    risks.append({"level": "medium", "scope": scope,
                                  "message": f"{t}.{name} 里嵌了比较表达式：本 IDE 不做括号补全，"
                                             f"比较表达式作为运算子可能出现优先级问题"})
        for _, child in node["values"] + node["statements"]:
            scan(child, scope)
        if node.get("next"):
            scan(node["next"], scope)

    for child in list(root):
        if _et_local(child.tag) != "block":
            continue
        btype = child.get("type")
        if btype in ("procedures_defnoreturn", "procedures_defreturn"):
            name = None
            args = []
            for sub in list(child):
                ln = _et_local(sub.tag)
                if ln == "field" and sub.get("name") == "NAME":
                    name = (sub.text or "").strip()
                elif ln == "mutation":
                    args = [a.get("name") for a in list(sub) if _et_local(a.tag) == "arg"]
            scope = f"函数 {name}({', '.join(args)})"
            st = child.find(NS + "statement")
            if st is not None:
                first = st.find(NS + "block")
                if first is not None:
                    scan(_xml_block_tree(first), scope)
        elif btype == "start":
            st = child.find(NS + "statement")
            if st is not None:
                first = st.find(NS + "block")
                if first is not None:
                    scan(_xml_block_tree(first), "start/main")
    return risks


def write_semantic_report(path: Path, project: dict, generated_code: str, result: dict) -> None:
    """输出“块结构 vs 生成 Python”的逐函数核对 Markdown。"""
    import xml.etree.ElementTree as ET
    project_xml = project.get("projectXml") or ""
    gen = analyze_python_structure(generated_code or "")
    gen_funcs = {f["name"]: f for f in gen["functions"]}
    lines: list[str] = []
    lines.append(f"# 语义核对报告：{project.get('inputPath') or '(内置项目)'}")
    lines.append("")
    lines.append(f"- 生成时间：{now_iso()}")
    lines.append(f"- 机器人类型：{project.get('robotType')}    程序名：{project.get('programName')}")
    lines.append(f"- 生成 Python 行数：{gen['lineCount']}    函数定义数：{len(gen['functions'])}")
    lines.append("- 说明：本报告把“块结构（IDE 里看到/拖出来的逻辑）”与“该函数最终生成的 Python”并排列出，"
                 "并给出自动风险扫描结果，便于人工逐条核对语义。")
    lines.append("")
    risks = scan_semantic_risks(project_xml) if project_xml else []
    lines.append("## 自动风险扫描")
    lines.append("")
    if not risks:
        lines.append("未发现已知的括号/优先级风险模式（while_cmp 条件均为单个比较块；比较表达式未嵌入运算）。")
    else:
        for r in risks:
            lines.append(f"- **[{r['level']}] {r['scope']}**：{r['message']}")
    lines.append("")

    try:
        root = ET.fromstring(project_xml)
    except Exception:
        root = None
    defs = []
    if root is not None:
        for child in list(root):
            if _et_local(child.tag) != "block":
                continue
            if child.get("type") not in ("procedures_defnoreturn", "procedures_defreturn"):
                continue
            name, args = None, []
            for sub in list(child):
                ln = _et_local(sub.tag)
                if ln == "field" and sub.get("name") == "NAME":
                    name = (sub.text or "").strip()
                elif ln == "mutation":
                    args = [a.get("name") for a in list(sub) if _et_local(a.tag) == "arg"]
            st = child.find(NS + "statement")
            tree = None
            if st is not None:
                first = st.find(NS + "block")
                if first is not None:
                    tree = _xml_block_tree(first)
            defs.append({"name": name, "args": args, "tree": tree})

    lines.append("## 逐函数核对")
    lines.append("")
    for i, d in enumerate(defs, 1):
        lines.append(f"### {i}. {d['name']}({', '.join(d['args'])})")
        lines.append("")
        lines.append("**块结构**")
        lines.append("")
        lines.append("```")
        lines.append(_render_block_tree(d["tree"]) if d["tree"] else "(空函数体)")
        lines.append("```")
        lines.append("")
        body = gen_funcs.get(d["name"])
        lines.append("**生成 Python**")
        lines.append("")
        lines.append("```python")
        if body:
            lines.append(f"def {body['name']}({body['args']}):")
            lines.extend(body["body"] if body["body"] else ["    pass"])
        else:
            lines.append("(生成结果中未找到该函数)")
        lines.append("```")
        lines.append("")
        # 参数使用核查
        if d["args"]:
            used = [a for a in d["args"]
                    if _subtree_has_varget(d["tree"], a)]
            unused = [a for a in d["args"] if a not in used]
            lines.append(f"参数使用：{used}" + (f"；**未在函数体引用：{unused}**" if unused else ""))
            lines.append("")
    path.parent.mkdir(parents=True, exist_ok=True)
    write_text_lf(path, "\n".join(lines) + "\n")


def _subtree_has_varget(node: dict | None, var_name: str) -> bool:
    found = [False]

    def visit(n):
        if n["type"] == "variables_get":
            for k, v in n["fields"]:
                if k == "VAR" and v == var_name:
                    found[0] = True
    _walk_blocks(node, visit)
    return found[0]


# --------------------------------------------------------------------------------------
# 原生函数块（abilix_userlib.js）：解析、项目内原生块统计、prelude 注入核对、--native-test 断言
# --------------------------------------------------------------------------------------

def _extract_js_literal(text: str, var_name: str) -> str | None:
    """从 JS 文本里提取 `var <var_name> = <字面量>;` 的字面量原文。

    只做轻量词法扫描（字符串里的转义、数组/对象里的嵌套括号都能正确处理），
    不依赖任何 JS 引擎。返回字面量原文（不含结尾分号）；找不到返回 None。
    """
    m = re.search(r"(?m)^[ \t]*var\s+" + re.escape(var_name) + r"\s*=\s*", text)
    if not m:
        return None
    i, n = m.end(), len(text)
    while i < n and text[i] in " \t\r\n":
        i += 1
    start = i
    in_str = None
    depth = 0
    while i < n:
        ch = text[i]
        if in_str:
            if ch == "\\":
                i += 2
                continue
            if ch == in_str:
                in_str = None
        else:
            if ch in "\"'`":
                in_str = ch
            elif ch in "[{(":
                depth += 1
            elif ch in "]})":
                depth -= 1
                if depth <= 0:
                    i += 1
                    break
            elif ch == ";" and depth <= 0:
                break
        i += 1
    literal = text[start:i].strip()
    if literal.endswith(";"):
        literal = literal[:-1].strip()
    return literal or None


def load_userlib(web_root: Path) -> dict:
    """解析 web_root 里的原生函数块补丁 abilix_userlib.js。

    返回 dict：
      present       文件是否存在（False 时调用方完全跳过原生块逻辑）
      path          文件绝对路径
      encoding      文件编码
      functions     [{"name", "args", "tip", "blockType"}]，blockType 形如 abilixuf_func_Hello
      prelude       abilixUserLibPython 字符串（生成 Python 时注入的函数定义）
      preludeChars / preludeSha256
      errors        解析过程中的问题（不抛异常，交给断言层判断）
    """
    path = Path(web_root) / USERLIB_REL_PATH
    info: dict = {"present": False, "path": str(path), "functions": [], "prelude": "",
                  "errors": [], "preludeChars": 0, "preludeSha256": None}
    if not path.is_file():
        return info
    info["present"] = True
    try:
        text, enc = decode_bytes(path.read_bytes())
        info["encoding"] = enc
    except Exception as e:  # pragma: no cover - 读取失败极端情况
        info["errors"].append(f"读取 abilix_userlib.js 失败：{e}")
        return info

    raw_py = _extract_js_literal(text, "abilixUserLibPython")
    if raw_py is None:
        info["errors"].append("abilix_userlib.js 里找不到 var abilixUserLibPython")
    else:
        try:
            prelude = json.loads(raw_py)
            if isinstance(prelude, str):
                info["prelude"] = prelude
            else:
                info["errors"].append("abilixUserLibPython 不是字符串")
        except Exception as e:
            info["errors"].append(f"abilixUserLibPython 不是合法 JSON 字符串：{e}")

    raw_fn = _extract_js_literal(text, "abilixUserLib")
    if raw_fn is None:
        info["errors"].append("abilix_userlib.js 里找不到 var abilixUserLib")
    else:
        try:
            funcs = json.loads(raw_fn)
            if not isinstance(funcs, list):
                info["errors"].append("abilixUserLib 不是数组")
                funcs = []
            for fn in funcs:
                if not isinstance(fn, dict) or not fn.get("name"):
                    continue
                name = str(fn.get("name"))
                info["functions"].append({
                    "name": name,
                    "args": [str(a) for a in (fn.get("args") or [])],
                    "tip": str(fn.get("tip") or ""),
                    "blockType": NATIVE_BLOCK_PREFIX + re.sub(r"[^A-Za-z0-9_]", "_", name),
                })
        except Exception as e:
            info["errors"].append(f"abilixUserLib 不是合法 JSON 数组：{e}")

    info["preludeChars"] = len(info["prelude"])
    if info["prelude"]:
        info["preludeSha256"] = hashlib.sha256(info["prelude"].encode("utf-8")).hexdigest()
    return info


def project_native_blocks(project_xml: str) -> dict:
    """递归统计项目 XML 里所有原生函数块（含 start 语句链/嵌套输入里的块）。

    返回 {count, types, byType}；XML 解析失败时带 error 字段（不抛异常）。
    """
    import xml.etree.ElementTree as ET
    out: dict = {"count": 0, "types": [], "byType": {}}
    try:
        root = ET.fromstring(project_xml or "<xml/>")
        for el in root.iter():
            if _et_local(el.tag) != "block":
                continue
            btype = el.get("type") or ""
            if btype.startswith(NATIVE_BLOCK_PREFIX):
                out["count"] += 1
                out["types"].append(btype)
                out["byType"][btype] = out["byType"].get(btype, 0) + 1
    except Exception as e:
        out["error"] = str(e)
    return out


def detect_prelude_injection(generated_code: str, prelude: str) -> dict:
    """判断生成的 Python 里是否包含 userlib 注入的 prelude。

    先整段子串匹配（真实 maingui.js 注入的就是同一段字符串）；
    整段匹配不到时退化为“prelude 的每个非空行按顺序出现”，便于诊断换行差异。
    """
    code = generated_code or ""
    det = {"exact": bool(prelude) and prelude in code, "lineSequence": False,
           "preludeFirstLine": None, "preludeLastLine": None}
    lines = [ln for ln in (prelude or "").splitlines() if ln.strip()]
    if lines:
        det["preludeFirstLine"] = lines[0]
        det["preludeLastLine"] = lines[-1]
        pos, ordered = -1, True
        for ln in lines:
            p = code.find(ln, pos + 1)
            if p < 0:
                ordered = False
                break
            pos = p
        det["lineSequence"] = ordered
    return det


def build_native_test(project: dict, harness: dict, userlib: dict, generated_code: str,
                      syntax: dict) -> dict:
    """--native-test 断言：真实工具箱「我的函数」分类 → flyout → createBlock 拖出 → 生成 Python。"""
    checks: list[dict] = []

    def add(name: str, ok: bool, detail: str = ""):
        checks.append({"name": name, "pass": bool(ok), "detail": detail})

    funcs = userlib.get("functions") or []
    expected_types = [f["blockType"] for f in funcs]
    by_type = {f["blockType"]: f for f in funcs}

    load = harness.get("load") or {}
    add("项目加载成功", bool(load.get("success")), str(load.get("error") or ""))
    add("web_root 中存在原生函数块补丁 abilix_userlib.js", bool(userlib.get("present")),
        str(userlib.get("path")))
    add("userlib 解析无错误", not userlib.get("errors"), "; ".join(userlib.get("errors") or []))
    add(f"userlib 中解析出原生函数（{len(funcs)} 个）", bool(funcs),
        ", ".join(f["name"] for f in funcs[:8]) + ("..." if len(funcs) > 8 else ""))

    nat = harness.get("native") or {}
    cat = nat.get("category") or {}
    add("工具箱树里找到「我的函数」分类", bool(cat.get("found")),
        f"name={cat.get('name')!r} blockCount={cat.get('blockCount')}")
    add(f"分类名 == {NATIVE_CATEGORY_NAME!r}", (cat.get("name") or "").strip() == NATIVE_CATEGORY_NAME,
        str(cat.get("name")))
    add("经由真实工具箱树选中分类（Toolbox.TreeControl.setSelectedItem）",
        bool(cat.get("viaTreeSelection")), str(cat.get("viaTreeSelection")))
    fly = nat.get("flyout") or {}
    fly_types = [b.get("type") for b in (fly.get("blocks") or [])]
    add(f"flyout 实例化块数 == userlib 函数数（{len(funcs)}）",
        fly.get("blockCount") == len(funcs), f"实际 {fly.get('blockCount')}")
    add("flyout 里全部是 abilixuf_* 原生块",
        bool(fly_types) and all((t or "").startswith(NATIVE_BLOCK_PREFIX) for t in fly_types),
        str(fly_types[:8]))
    add("flyout 原生块类型与 userlib 完全一致（含顺序）", fly_types == expected_types,
        json.dumps({"flyout": fly_types[:8], "expected": expected_types[:8]}, ensure_ascii=False))
    fr = fly.get("render") or {}
    add("flyout 原生块均已渲染（rendered + SVG root + 非 0 尺寸）",
        bool(fr) and fr.get("renderedBlockCount") == fly.get("blockCount")
        and fr.get("renderedSvgRootCount") == fly.get("blockCount")
        and not (fr.get("zeroSizeBlockCount") or 0),
        json.dumps(fr, ensure_ascii=False))

    drag = nat.get("drag") or {}
    created = drag.get("created") or []
    add("拖拽路径执行成功（Flyout.createBlock 真实拖出）", bool(drag.get("ok")),
        str(drag.get("error") or ""))
    add(f"从 flyout 拖出的原生块数量 == flyout 块数（{fly.get('blockCount')}）",
        len(created) == fly.get("blockCount"), f"实际 {len(created)}")
    created_types = [c.get("type") for c in created]
    add("拖出原生块类型与 flyout 顺序一致", created_types == fly_types,
        json.dumps(created_types[:8], ensure_ascii=False))
    not_rendered = [c for c in created if not (c.get("rendered") and c.get("svgOk"))]
    add("拖出的原生块均已渲染（rendered + SVG root）", not not_rendered,
        json.dumps(not_rendered, ensure_ascii=False)[:500])
    arg_total = sum(len(f.get("args") or []) for f in funcs)
    filled = sum(len(c.get("argValues") or []) for c in created)
    add(f"所有带参原生块的参数输入都已填值（{arg_total} 个）", filled == arg_total,
        f"实际 {filled}/{arg_total}")
    add("拖出的原生块已接入 start 的 code 语句链",
        bool(drag.get("startBlockId")) and drag.get("chainLength") == len(created),
        f"startBlockId={drag.get('startBlockId')} chainLength={drag.get('chainLength')}")
    project_native = project_native_blocks(project.get("projectXml") or "")
    add("项目里原有的原生块在拖拽前被移除（避免重复调用，生成内容全部来自本次拖出）",
        drag.get("removedCount") == project_native.get("count"),
        f"removed={drag.get('removedCount')} projectNative={project_native.get('count')}")

    gen = harness.get("generation") or {}
    add("真实 maingui.getPythonCode 生成成功", bool(gen.get("success")) and bool(gen.get("usedRealSource")),
        str(gen.get("error") or ""))

    code = generated_code or ""
    header = f"#<{project.get('robotType')}><{project.get('connectionType')}><{project.get('programName')}>"
    first_line = code.splitlines()[0] if code else ""
    add("文件头恰好出现一次且内容正确", code.count(header) == 1 and first_line == header,
        f"期待 {header!r}，实际首行 {first_line!r}，出现 {code.count(header)} 次")
    imports = re.findall(r"(?m)^import\s+(\w+)", code)
    need_imports = [] if project.get("robotType") == "SKCON2" else ["threading", "time", "libstarpy"]
    add("import 无重复且包含 threading/time/libstarpy",
        all(imports.count(m) == 1 for m in need_imports) and len(imports) == len(set(imports)),
        str(imports))
    robot_init_count = len(re.findall(r"(?m)^robot = Robot\(\)\s*$", code))
    add("robot = Robot() 恰好一次", robot_init_count == 1, f"实际 {robot_init_count} 次")

    det = detect_prelude_injection(code, userlib.get("prelude") or "")
    add("生成代码注入了 abilixUserLibPython（整段完全一致）", det["exact"],
        f"prelude {userlib.get('preludeChars')} 字符，行序匹配={det['lineSequence']}，sha256={userlib.get('preludeSha256')}")
    prelude_pos = -1
    if det.get("preludeFirstLine"):
        prelude_pos = code.find(det["preludeFirstLine"])
    main_pos = code.find("\ndef main(")
    add("userlib 注入内容位于 def main 之前", prelude_pos >= 0 and main_pos > prelude_pos,
        f"prelude@{prelude_pos} main@{main_pos}")
    defs = re.findall(r"(?m)^def ([A-Za-z_]\w*)\(", code)
    dup_defs = sorted({d for d in defs if defs.count(d) > 1})
    add("注入的 def 没有重复", not dup_defs, f"重复 {dup_defs}")
    missing_defs = [f["name"] for f in funcs if f["name"] not in defs]
    add(f"userlib {len(funcs)} 个函数定义全部出现在生成代码中", not missing_defs, str(missing_defs))

    m = re.search(r"^def main\(\):(.*?)(?=^main\(\)#program entry)", code, re.M | re.S)
    main_body = m.group(1) if m else ""
    add("生成代码里有 def main()", bool(m), "")
    missing_calls = [f["name"] for f in funcs if not re.search(re.escape(f["name"]) + r"\(", main_body)]
    add(f"main 里调用了全部 {len(funcs)} 个原生函数", not missing_calls, f"缺失 {missing_calls}")
    invoke_exprs, invoke_names = [], []
    for c in created:
        fn = by_type.get(c.get("type")) or {}
        name = fn.get("name") or ""
        if not name:
            continue
        invoke_names.append(name)
        invoke_exprs.append(name + "(" + ", ".join(str(v) for v in (c.get("argValues") or [])) + ")")
    positions = [main_body.rfind(expr) for expr in invoke_exprs]
    order_ok = bool(invoke_exprs) and all(p >= 0 for p in positions) and all(
        positions[i] < positions[i + 1] for i in range(len(positions) - 1))
    add("main 里调用顺序与 flyout 拖出顺序一致", order_ok,
        json.dumps(list(zip(invoke_names, positions))[:12], ensure_ascii=False))
    add("main 里带参数调用的实参与填值完全一致（逐表达式匹配）", bool(invoke_exprs) and
        all(p >= 0 for p in positions),
        json.dumps(invoke_exprs[:12], ensure_ascii=False))
    add("程序入口 main()#program entry 恰好一次且在末尾",
        code.rstrip().endswith("main()#program entry") and code.count("main()#program entry") == 1,
        f"出现 {code.count('main()#program entry')} 次")

    add("py_compile 语法检查通过", bool(syntax.get("ok")), tail(str(syntax.get("stderr") or ""), 800))

    passed = sum(1 for c in checks if c["pass"])
    return {"checks": checks, "passed": passed == len(checks), "passedCount": passed,
            "totalCount": len(checks)}


# --------------------------------------------------------------------------------------
# 主流程
# --------------------------------------------------------------------------------------

def build_harness_html(cfg: dict, toolbox_xml: str, toolbox_id: str,
                       extra_scripts=()) -> str:
    scripts = list(HARNESS_SCRIPTS) + list(extra_scripts)
    script_tags = "\n".join(f'<script src="{s}"></script>' for s in scripts)
    html_text = HARNESS_TEMPLATE
    html_text = html_text.replace("@@CONFIG_JSON@@", json_for_script(cfg))
    html_text = html_text.replace("@@TOOLBOX_XML@@", toolbox_xml)
    html_text = html_text.replace("@@TOOLBOX_ID@@", toolbox_id)
    html_text = html_text.replace("@@SCRIPT_TAGS@@", script_tags)
    html_text = html_text.replace("@@TOOL_VERSION@@", TOOL_VERSION)
    return html_text


def run(args: argparse.Namespace) -> int:
    started = time.time()
    mode = ("param" if args.param_test else
            ("drag" if args.drag_test else
             ("native" if getattr(args, "native_test", False) else "project")))

    tmp_parent = Path(args.work_dir).resolve() if args.work_dir else Path(tempfile.gettempdir())
    tmp_parent.mkdir(parents=True, exist_ok=True)
    work = Path(tempfile.mkdtemp(prefix="wer_validate_", dir=str(tmp_parent)))
    profile_dir = work / "chrome-profile"

    result: dict = {
        "meta": {
            "tool": "run_validate.py",
            "toolVersion": TOOL_VERSION,
            "generatedAt": now_iso(),
            "argv": sys.argv,
            "python": sys.version.split()[0],
            "mode": mode,
        },
        "ok": False,
        "errors": [],
    }
    exit_code = 3
    try:
        chrome_path = find_chrome(args.chrome)
        web_root = Path(args.web_root).resolve() if args.web_root else DEFAULT_WEB_ROOT
        evidence_dir = Path(args.evidence_dir).resolve() if args.evidence_dir else None
        result["meta"]["chrome"] = chrome_path
        result["meta"]["webRoot"] = str(web_root)

        log(f"== WER headless 验证工具 v{TOOL_VERSION} ==")
        log(f"   web_root : {web_root}")
        log(f"   chrome   : {chrome_path}")
        log(f"   work tmp : {work}")

        ide = load_ide_sources(web_root)

        if mode == "param":
            project = {
                "inputPath": None,
                "format": "builtin-param-test",
                "encoding": "utf-8",
                "info": {"RobotType": "SKCON9", "DownloadProgramName": "ProgramA"},
                "infoRaw": None,
                "zipRobotType": None,
                "robotType": args.robot_type or "SKCON9",
                "connectionType": args.connection_type or "USB",
                "programName": args.program_name or "ProgramA",
                "projectXml": PARAM_TEST_XML,
                "static": {},
                "warnings": [],
            }
            # 静态统计
            static = load_project_static(project["projectXml"])
            project["static"] = static
        else:
            if not args.input:
                log("[错误] 需要传入项目文件（.srh / .srhs / .xml），或使用 --param-test")
                return 2
            inp = Path(args.input).resolve()
            if not inp.exists():
                log(f"[错误] 文件不存在：{inp}")
                return 2
            project = load_project(inp, robot_type=args.robot_type,
                                   program_name=args.program_name,
                                   connection_type=args.connection_type)
        result["project"] = {k: v for k, v in project.items() if k != "projectXml"}

        if not (project["static"] or {}).get("xmlValid", True):
            result["errors"].append("项目 XML 无法被 XML 解析器解析：" + str(project["static"].get("xmlError")))
            result["ok"] = False
            exit_code = 2
            return finish(args, result, project, None, evidence_dir, started, exit_code, work)

        toolbox_id = ROBOT_TO_TOOLBOX.get(project["robotType"], "toolbox_skcon9")
        if toolbox_id not in ide["toolboxes"]:
            result["errors"].append(f"没有 {project['robotType']} 对应工具箱，退回 toolbox_skcon9")
            toolbox_id = "toolbox_skcon9"
        # --native-test 依赖原生积木补丁；没有补丁时直接失败并给出明确原因（不浪费一次 Chrome）
        if mode == "native" and not (web_root / USERLIB_REL_PATH).is_file():
            result["errors"].append(
                f"--native-test 需要 web_root 中存在 {USERLIB_REL_PATH}（由原生积木补丁脚本生成）；"
                f"当前 web_root={web_root}")
            result["ok"] = False
            exit_code = 2
            return finish(args, result, project, None, evidence_dir, started, exit_code, work)
        cfg = {
            "mode": mode,
            "robotType": project["robotType"],
            "connectionType": project["connectionType"],
            "programName": project["programName"],
            "projectXml": project["projectXml"],
            "getPythonCodeSource": ide.get("getPythonCodeSource"),
        }
        # --native-test：告诉 harness 去工具箱树里找“我的函数”分类并真实拖出原生块
        if mode == "native":
            cfg["nativeTest"] = {
                "enabled": True,
                "categoryName": NATIVE_CATEGORY_NAME,
                "blockPrefix": NATIVE_BLOCK_PREFIX,
                "argValueBase": 10,   # 参数填值 = 10*(块序号+1)+参数序号，便于精确断言调用
            }
        # 如果 web_root 里存在“原生函数块”补丁脚本，就一并加载（原生积木框架验证用；
        # 原版资源包没有这个文件，行为与之前完全一致）。
        extra_scripts = []
        userlib_js = web_root / "Blockly_Code" / "abilix_userlib.js"
        if userlib_js.is_file():
            extra_scripts.append("abilix_userlib.js")
        harness_html = build_harness_html(cfg, ide["toolboxes"][toolbox_id], toolbox_id,
                                          extra_scripts=extra_scripts)

        dom = ""
        chrome_info: dict = {}
        with HarnessServer(web_root, harness_html) as server:
            log(f"   harness URL: {server.url}")
            chrome_info = run_chrome(chrome_path, server.url, ["--virtual-time-budget=30000",
                                                               "--dump-dom"],
                                     profile_dir, timeout=args.timeout,
                                     window_size=args.window_size)
            payloads = server.results
            payload = payloads[-1] if payloads else None
        harness, errs = evaluate_harness_result(payload, chrome_info.get("stdout", ""), chrome_info)
        result["errors"].extend(errs)
        result["chrome"] = {k: chrome_info.get(k) for k in
                            ("returncode", "timedOut", "elapsedMs")}
        result["harness"] = harness
        if "load" not in harness:
            result["harness"] = harness
            result["ok"] = False
            exit_code = 3
            return finish(args, result, project, None, evidence_dir, started, exit_code, work)

        generated_code = ((harness.get("generation") or {}).get("code")) or ""
        if generated_code:
            result["analysis"] = analyze_generated(generated_code)
            result["syntaxCheck"] = py_compile_check(generated_code, work)
        else:
            result["analysis"] = None
            result["syntaxCheck"] = {"ok": False, "error": "未生成 Python 代码"}

        # ---- 原生函数块（abilix_userlib.js）核对：userlib 解析 + prelude 注入回归 ----
        # 原版资源包没有 abilix_userlib.js 时完全跳过（向后兼容，不改变旧行为）。
        userlib = load_userlib(web_root)
        native_blocks = project_native_blocks(project.get("projectXml") or "")
        result["nativeBlocks"] = native_blocks
        if userlib.get("present"):
            prelude = userlib.get("prelude") or ""
            prelude_det = detect_prelude_injection(generated_code, prelude)
            expected_injection = native_blocks.get("count", 0) > 0
            detected_injection = bool(prelude_det["exact"] or prelude_det["lineSequence"])
            result["nativePrelude"] = {
                "userlibPath": userlib.get("path"),
                "userlibFunctionCount": len(userlib.get("functions") or []),
                "userlibFunctions": [f["name"] for f in userlib.get("functions") or []],
                "preludeChars": userlib.get("preludeChars"),
                "preludeSha256": userlib.get("preludeSha256"),
                "projectNativeBlockCount": native_blocks.get("count"),
                "projectNativeBlockTypes": native_blocks.get("types"),
                "expectedInjection": expected_injection,
                "detectedInjection": detected_injection,
                "exactMatch": prelude_det["exact"],
                "lineSequenceMatch": prelude_det["lineSequence"],
                "ok": expected_injection == detected_injection,
            }
            if not result["nativePrelude"]["ok"]:
                result["errors"].append(
                    "原生块 prelude 注入回归失败：项目原生块数=%s（期望注入=%s），"
                    "生成代码实际注入=%s" % (native_blocks.get("count"),
                                              expected_injection, detected_injection))
            result["userlib"] = {k: userlib.get(k) for k in
                                 ("present", "path", "encoding", "functions", "preludeChars",
                                  "preludeSha256", "errors")}
        else:
            result["nativePrelude"] = {
                "skipped": "web_root 中没有 Blockly_Code/abilix_userlib.js（未打原生积木补丁）",
                "ok": True,
            }
            result["userlib"] = {"present": False, "path": userlib.get("path")}

        if args.compare_ref:
            ref_path = Path(args.compare_ref).resolve()
            ref_text, ref_enc = decode_bytes(ref_path.read_bytes())
            comparison = compare_python(ref_text, generated_code, str(ref_path))
            comparison["referenceEncoding"] = ref_enc
            result["comparison"] = comparison
            if args.diff_out:
                diff_path = Path(args.diff_out)
                write_text_lf(diff_path, "\n".join(comparison["normalizedDiff"]) + "\n")

        if mode == "param":
            result["paramTest"] = build_param_test(harness, generated_code,
                                                   result.get("syntaxCheck") or {})
        if mode == "drag":
            result["dragTest"] = build_drag_test(project, harness, generated_code,
                                                 result.get("syntaxCheck") or {})
        if mode == "native":
            result["nativeTest"] = build_native_test(project, harness, userlib, generated_code,
                                                     result.get("syntaxCheck") or {})

        if args.semantic_out:
            sem_path = Path(args.semantic_out).resolve()
            write_semantic_report(sem_path, project, generated_code, result)
            result["meta"]["semanticReport"] = str(sem_path)

        # 总判定
        ok = True
        if not (harness.get("load") or {}).get("success"):
            ok = False
        if not ((harness.get("generation") or {}).get("success")):
            ok = False
        if not (result.get("syntaxCheck") or {}).get("ok"):
            ok = False
        if mode == "param" and not (result.get("paramTest") or {}).get("passed"):
            ok = False
        if mode == "drag" and not (result.get("dragTest") or {}).get("passed"):
            ok = False
        if mode == "native" and not (result.get("nativeTest") or {}).get("passed"):
            ok = False
        # prelude 注入回归（web_root 有 userlib 补丁时才有实际判定；无补丁时 ok 恒为 True）
        if not (result.get("nativePrelude") or {}).get("ok", True):
            ok = False
        if args.fail_on_diff and result.get("comparison"):
            ok = ok and bool(result["comparison"]["identicalModuloAllowedDiffs"])
        result["ok"] = ok
        exit_code = 0 if ok else 2

        # 可选截图（单独一次 Chrome，页面 ?shot=1；原生块模式额外拍 4 张证据图）
        if args.screenshot is not None:
            shot_path = Path(args.screenshot) if args.screenshot else \
                Path(str(args.evidence_dir or SCRIPT_DIR / "证据")) / f"{make_evidence_name(args.input, mode)}_shot.png"
            shot_path = shot_path.resolve()
            shot_path.parent.mkdir(parents=True, exist_ok=True)
            prof2 = work / "chrome-profile-shot"
            with HarnessServer(web_root, harness_html) as server2:
                shot_url = server2.url + "?shot=1"
                info2 = run_chrome(chrome_path, shot_url,
                                   [f"--screenshot={shot_path}", "--virtual-time-budget=20000"],
                                   prof2, timeout=args.timeout,
                                   window_size=args.window_size)
            result["screenshot"] = {
                "path": str(shot_path),
                "exists": shot_path.exists(),
                "sizeBytes": shot_path.stat().st_size if shot_path.exists() else None,
                "chromeReturncode": info2.get("returncode"),
                "chromeTimedOut": info2.get("timedOut"),
                "chromeStderrTail": tail(info2.get("stderr", ""), 1500),
            }
            if not shot_path.exists():
                result["errors"].append("截图未生成（见 screenshot.chromeStderrTail）")

            # --native-test：额外拍 4 张分阶段证据图（与产物同目录，文件名 <stem>_shot_<kind>.png）
            if mode == "native":
                native_shots = []
                for kind in ("page", "flyout", "drag", "python"):
                    kind_path = shot_path.with_name(shot_path.stem + "_" + kind + shot_path.suffix)
                    prof_kind = work / ("chrome-profile-shot-" + kind)
                    with HarnessServer(web_root, harness_html) as server_k:
                        shot_url_k = server_k.url + "?shot=1&nativeShot=" + kind
                        info_k = run_chrome(chrome_path, shot_url_k,
                                            [f"--screenshot={kind_path}",
                                             "--virtual-time-budget=25000"],
                                            prof_kind, timeout=args.timeout,
                                            window_size=args.window_size)
                    rec = {
                        "kind": kind,
                        "path": str(kind_path),
                        "exists": kind_path.exists(),
                        "sizeBytes": kind_path.stat().st_size if kind_path.exists() else None,
                        "chromeReturncode": info_k.get("returncode"),
                        "chromeTimedOut": info_k.get("timedOut"),
                        "chromeStderrTail": tail(info_k.get("stderr", ""), 800),
                    }
                    native_shots.append(rec)
                    if not kind_path.exists():
                        result["errors"].append(
                            f"原生块截图 {kind} 未生成（见 screenshots[] 里的 chromeStderrTail）")
                result["screenshots"] = native_shots
        return finish(args, result, project, generated_code, evidence_dir, started, exit_code, work)
    except SystemExit as e:
        result["errors"].append(str(e))
        result["ok"] = False
        return finish(args, result, None, None, evidence_dir, started, 3, work)
    except Exception:
        result["errors"].append(traceback.format_exc())
        result["ok"] = False
        return finish(args, result, None, None, evidence_dir, started, 3, work)
    finally:
        if not args.keep:
            shutil.rmtree(work, ignore_errors=True)
        else:
            log(f"   [--keep] 临时目录保留：{work}")


def load_project_static(project_xml: str) -> dict:
    """对纯项目 XML 做静态统计（复用 load_project 中的逻辑）。"""
    import xml.etree.ElementTree as ET
    static = {"xmlValid": False, "xmlError": None}
    try:
        root = ET.fromstring(project_xml)
        static["xmlValid"] = True
        static["rootTag"] = localname(root.tag)
        variables, top_blocks = [], []
        for child in list(root):
            ln = localname(child.tag)
            if ln == "variables":
                for v in list(child):
                    if localname(v.tag) == "variable":
                        variables.append({"name": (v.text or "").strip(), "id": v.get("id")})
            elif ln == "block":
                btype = child.get("type")
                rec = {"type": btype, "id": child.get("id")}
                if btype in ("procedures_defnoreturn", "procedures_defreturn"):
                    name, args = None, []
                    for sub in list(child):
                        sl = localname(sub.tag)
                        if sl == "field" and sub.get("name") == "NAME":
                            name = (sub.text or "").strip()
                        elif sl == "mutation":
                            for a in list(sub):
                                if localname(a.tag) == "arg":
                                    args.append(a.get("name"))
                    rec.update({"name": name, "args": args})
                top_blocks.append(rec)
        static["variablesCount"] = len(variables)
        static["variables"] = variables
        static["topBlockCount"] = len(top_blocks)
        static["topBlocks"] = top_blocks
        static["procedures"] = {
            "defnoreturn": [b for b in top_blocks if b["type"] == "procedures_defnoreturn"],
            "defreturn": [b for b in top_blocks if b["type"] == "procedures_defreturn"],
        }
        static["topBlocksByType"] = {}
        for b in top_blocks:
            static["topBlocksByType"][b["type"]] = static["topBlocksByType"].get(b["type"], 0) + 1
        static["hasStartBlock"] = any(b["type"] == "start" for b in top_blocks)
    except Exception as e:
        static["xmlError"] = str(e)
    return static


def finish(args, result: dict, project: dict | None, generated_code: str | None,
           evidence_dir: Path | None, started: float, exit_code: int, work: Path) -> int:
    result["meta"]["elapsedMs"] = round((time.time() - started) * 1000)
    name = make_evidence_name(args.input if not args.param_test else None,
                              "param" if args.param_test else "project")
    text = summarize_text(result)

    if generated_code is not None and args.py:
        py_path = Path(args.py).resolve()
        write_text_lf(py_path, generated_code)
        result["meta"]["pythonOutput"] = str(py_path)

    if args.json:
        json_path = Path(args.json).resolve()
        json_path.parent.mkdir(parents=True, exist_ok=True)
        write_text_lf(json_path, json.dumps(result, ensure_ascii=False, indent=2))
        result["meta"]["jsonOutput"] = str(json_path)

    if evidence_dir is not None:
        evidence_dir.mkdir(parents=True, exist_ok=True)
        stamp = time.strftime("%Y%m%d_%H%M%S")
        base = evidence_dir / f"{stamp}_{name}"
        write_text_lf(base.with_suffix(".json"), json.dumps(result, ensure_ascii=False, indent=2))
        write_text_lf(base.with_suffix(".report.txt"), text + "\n")
        if generated_code:
            write_text_lf(base.with_suffix(".py"), generated_code)
        result["meta"]["evidenceBase"] = str(base)
        log(f"\n证据已写入：{base}.json / .report.txt / .py")

    log("\n" + text)

    # --json 的路径在 result 里回填后再落盘一次（保证 json 自包含路径信息）
    if args.json:
        write_text_lf(Path(args.json).resolve(), json.dumps(result, ensure_ascii=False, indent=2))

    return exit_code


def build_arg_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        description="WER/AbilixScratch3.0 项目 headless 验证工具（真实 Blockly 引擎 + 真实 Python 生成器）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""示例:
  python run_validate.py _分析临时/PI/abilixProject.srh --compare-ref 逆向资料/样本程序/PI.py
  python run_validate.py 项目.srhs --json out/result.json --py out/generated.py
  python run_validate.py --param-test --evidence-dir 证据\\param
  python run_validate.py 项目.srh --screenshot 证据\\shot.png
""")
    ap.add_argument("input", nargs="?", help="项目文件（.srh / .srhs / 项目 XML）")
    ap.add_argument("--json", help="把完整结果 JSON 写到该路径")
    ap.add_argument("--py", help="把生成的完整 Python 写到该路径")
    ap.add_argument("--screenshot", nargs="?", const="", default=None,
                    help="额外跑一次 Chrome 截图；不带路径时写证据目录")
    ap.add_argument("--compare-ref", help="与参考 Python 做结构化对比（如 逆向资料/样本程序/PI.py）")
    ap.add_argument("--diff-out", help="把归一化 unified diff 写到该路径")
    ap.add_argument("--fail-on-diff", action="store_true",
                    help="对比存在非允许差异时返回失败")
    ap.add_argument("--param-test", action="store_true", help="运行内置“带参数函数”最小用例")
    ap.add_argument("--drag-test", action="store_true",
                    help="从函数分类 flyout 逐个 createBlock 拖出调用块并接入 start，验证“拖下来就能用”")
    ap.add_argument("--native-test", action="store_true",
                    help="原生函数块验证：在真实工具箱里选中“我的函数”分类，从 flyout 逐个 createBlock "
                         "拖出原生块（含参数块）接入 start，生成 Python 并断言调用/注入 def/py_compile；"
                         "需 --web-root 包含 abilix_userlib.js（如 _分析临时/native_work/patched_web）")
    ap.add_argument("--window-size", default="1600,1000",
                    help="Chrome 窗口尺寸 W,H（截图想看全函数分类可调高，如 1600,1800）")
    ap.add_argument("--semantic-out", help="输出逐函数“块结构 vs 生成 Python”语义核对 Markdown")
    ap.add_argument("--evidence-dir", help="把 JSON/报告/Python 证据写入该目录")
    ap.add_argument("--chrome", help="Chrome/Edge 可执行文件路径")
    ap.add_argument("--web-root", help="blockly_web 目录（含 Blockly_Code 与 closure-library）")
    ap.add_argument("--work-dir", help="临时工作目录父目录（默认系统 temp，用后自动清理）")
    ap.add_argument("--robot-type", help="覆盖项目里的机器人类型（默认读 .srh Info）")
    ap.add_argument("--connection-type", help="覆盖连接方式（默认 USB）")
    ap.add_argument("--program-name", help="覆盖程序名（影响生成文件头 #<...>）")
    ap.add_argument("--timeout", type=float, default=240.0, help="单次 Chrome 超时秒数（默认 240）")
    ap.add_argument("--keep", action="store_true", help="保留临时目录（调试用）")
    return ap


def main(argv=None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    ap = build_arg_parser()
    args = ap.parse_args(argv)
    if not args.param_test and not args.input:
        ap.print_help()
        return 2
    return run(args)


if __name__ == "__main__":
    sys.exit(main())
