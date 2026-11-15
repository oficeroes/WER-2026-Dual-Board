# 实验19 证据：双板通讯原型（Python prelude 拉起 C 助手）首次两板直测

- 时间：2026-11-12 20:39 起
- 网络：PC 192.168.1.105；1 号机（按钮板）192.168.1.102；2 号机（LED 板）192.168.1.103
- 程序：
  - `双板通讯研究/实验/实验19_双板通讯积木原型/wl_prelude.py`（双板通讯 Python prelude v0.1：内嵌 C 助手源码 → 机器人自带 gcc 编译到 `/data/data/com.abilix.controller/files/wlnet_helper` → fork+execv 启动，双 pipe IPC；UDP 8990 收发；地址→最新值字典）
  - `生成测试程序.py` 生成 `WLA.py`（1 号机，peer=.103，发 addr1 计数 + addr3 文本，收 addr2/addr3）与 `WLB.py`（2 号机，peer=.102，对称）
- 下发：WLA → .102（3685B，1388ms，160,3）；WLB → .103（3684B，1459ms，160,3）
- 判据：两块板屏幕上 `i=` 递增，且 `rx=` 显示对方发来的计数（前几秒为 0，对端起来后变为非 0）；`rx3=` 显示对方文本；`err=[]` 说明助手启动无异常。
- 预期技术链路：Python（积木 prelude）→ gcc 编译 C 助手到 App 私有目录 → fork/execv 启动 → C 助手 UDP 收发 → Python 字典 → 积木 reporter 读取。这条路若通，「双板通讯」积木只剩 IDE 侧打包工作。

## 实测结果：成功（2026-11-12 20:42）
两板屏幕（用户拍照 m01583）：
- 1 号机 WLA：`WLA i=18 rx=15 rx3=B-text err=[]`（i 递增至 18，rx=2 号机最新计数 15，文本段来自 2 号机）
- 2 号机 WLB：`WLB i=15 rx=17 rx3=A-text err=[]`（rx=1 号机最新计数 17）
- 两板 `err=[]`：C 助手编译/启动/IPC 全部正常；rx 数值随对端递增（差值为启动时间差），双向 UDP 通道成立。
→ 「双板通讯」运行时内核验证完毕：**Python（积木 prelude）→ 现场 gcc 编译 C 助手到 App 私有目录 → fork/execv 启动 → 双 pipe IPC → UDP 8990 收发 → 地址→最新值字典 → reporter 读取**。
- 证据照片：m01574（rx3 文本互通、rx=0 的旧版地址配置错误）、m01583（修正地址后数值+文本双向互通）。
