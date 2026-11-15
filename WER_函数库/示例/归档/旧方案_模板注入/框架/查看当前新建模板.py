# -*- coding: utf-8 -*-
"""
查看当前新建模板.py —— 查看软件「新建项目」默认模板里现在有什么
========================================================================

用途：只读。打开软件资源包 browser_assets，解出 `Blockly_Code/maingui_init.js`
      里三种语言（简中/繁中/英文）的 defaultcode 字符串，解析出：
        · 当前模板里的函数列表（名字 / 参数）
        · 变量声明
        · 顶层积木数 / start 数
        · 判定当前是“原始模板（0 个函数）”还是“已打过补丁”
      并且可以和「我的函数库」对比：同步后会新增哪些函数、缺失哪些、参数有什么不同。

用法
----
    python 查看当前新建模板.py
    python 查看当前新建模板.py --json --json-out 当前模板.json
    python 查看当前新建模板.py --library 我的函数库.srh      （对比指定函数库）
    python 查看当前新建模板.py --assets "…\\browser_assets"   （手动指定资源包）

退出码：0 = 读取成功；1 = 读到的内容有异常；2 = 找不到 browser_assets。

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
                     forced_cmd='inspect')


if __name__ == '__main__':
    sys.exit(main())
