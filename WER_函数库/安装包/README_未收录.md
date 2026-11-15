# 离线安装包里的 browser_assets.patched 未收录

这个目录原本还包含：

- `browser_assets.patched`（约 **85 MB**，已打「我的函数」补丁的 IDE 资源包）
- 预编译的离线安装脚本

它超过了 GitHub 单文件 100 MB 的限制，且包含官方 IDE 资源，因此没有进入仓库。
仓库保留的是源码工具链：

- `WER_函数库/工具/原生积木/安装原生积木.cmd`：从你自己的 IDE 编译并安装
- `WER_函数库/工具/原生积木/原生积木核心.py`：build / install / restore / status / verify
- `WER_函数库/修改软件说明/`：原理、换电脑、回滚、升级

按 `docs/04_安装步骤.md` 在自己的电脑上生成补丁即可。
