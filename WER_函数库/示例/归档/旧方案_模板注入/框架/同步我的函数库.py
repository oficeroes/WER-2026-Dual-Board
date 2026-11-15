# -*- coding: utf-8 -*-
"""
同步我的函数库.py —— 把「我的函数库」同步进软件的新建项目默认模板
========================================================================

原理：修改软件资源包 browser_assets 里 `Blockly_Code/maingui_init.js` 的
      `var defaultcode` 字符串 = 你的函数库（全部函数定义 + 变量声明 + start 主函数）。
      之后在 IDE 里「每新建一个项目」工作区就自带这些函数，「函数」分类里直接拖用。

用法
----
    :: 1) 演练（推荐先做）：只生成补丁包并自检，绝不写安装目录
    python 同步我的函数库.py --dry-run

    :: 2) 真正安装（需要管理员权限；会自动备份原文件 browser_assets.备份-<时间戳>）
    python 同步我的函数库.py --install
    :: 或者直接双击：同步我的函数库(管理员).cmd（会自动弹 UAC 提权）

    常用参数：
      --library 指定函数库源文件（默认自动找 我的函数库.srh/.srhs）
      --assets  指定 browser_assets（默认自动扫描本机安装目录）
      --langs   替换哪些语言模板：zh-hans（默认）/ all
      --out     补丁包输出路径（默认 <工作区>/_分析临时/framework_work/browser_assets.patched）
      --json / --json-out   输出 JSON 结果

退出码：0 = 成功（演练成功也算）；1 = 校验/自检失败；2 = 需要管理员权限或文件缺失。

安全：默认绝不写安装目录；确认无误后才加 --install。安装前自动备份，可用
      还原新建模板.py（或 还原新建模板(管理员).cmd）一键还原。

本文件只是中文名称的入口，真正实现在同目录 框架核心.py（可 import 复用）。
"""

from __future__ import annotations

import importlib.util
import os
import sys


def _load_core():
    """按文件路径加载同目录的 框架核心.py（文件名含中文，不能直接 import）。"""
    sys.dont_write_bytecode = True  # 不在交付目录里留下 __pycache__
    here = os.path.dirname(os.path.abspath(__file__))
    path = os.path.join(here, '框架核心.py')
    spec = importlib.util.spec_from_file_location('wer_framework_core', path)
    if spec is None or spec.loader is None:
        raise RuntimeError('无法加载框架核心.py：%s' % path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> int:
    core = _load_core()
    return core.main(sys.argv[1:], prog=os.path.basename(os.path.abspath(__file__)),
                     forced_cmd='sync')


if __name__ == '__main__':
    sys.exit(main())
