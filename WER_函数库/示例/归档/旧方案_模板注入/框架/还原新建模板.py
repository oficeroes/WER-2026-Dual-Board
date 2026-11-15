# -*- coding: utf-8 -*-
"""
还原新建模板.py —— 把软件的新建项目默认模板还原回打补丁之前
========================================================================

原理：打补丁时脚本会自动把原 browser_assets 备份成 `browser_assets.备份-<时间戳>`
      （与 browser_assets 同目录）。本工具找到备份，先把你**当前**的 browser_assets
      另存为 `browser_assets.还原前备份-<时间戳>`，再用备份覆盖回去，并校验 sha256。

用法
----
    :: 1) 先看看有哪些备份（不写文件）
    python 还原新建模板.py --list

    :: 2) 只看还原计划（不写文件）
    python 还原新建模板.py

    :: 3) 真正还原（需要管理员权限）
    python 还原新建模板.py --yes
    :: 或者直接双击：还原新建模板(管理员).cmd（会自动弹 UAC 提权）

    指定某一份备份：  --backup "…\\browser_assets.备份-20261110-132909"
    指定资源包路径：  --assets  "…\\browser_assets"

注意：多次同步会生成多份备份，最新备份 = 上一次同步之前的状态。
      要回到“出厂原始模板”，请用 --backup 指定最早的那份备份（--list 可以看到）。

退出码：0 = 成功/仅显示计划；1 = 还原失败；2 = 找不到备份或没有管理员权限。

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
                     forced_cmd='restore')


if __name__ == '__main__':
    sys.exit(main())
