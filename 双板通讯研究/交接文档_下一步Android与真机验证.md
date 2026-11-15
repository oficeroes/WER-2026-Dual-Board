# 交接文档：下一步（Android 真机 + 两板通讯验证）

> 生成：2026-11-11 21:0x（Asia/Shanghai）｜工作区：`D:\UserData\Documents\WER\2026普级赛`
> 读者：**新开会话的 AI（零上下文）** + 用户本人
> 阅读顺序：§0 本次新增事实 → §2 硬事实基线 → §3 最终判定 → §4 下一步 WBS → 附录 A 提示词 → 附录 B 工具清单
>
> **一句话交接**：最初的两个设想（"1 号口直读/篡改对方地址"、"传感器自身收发射频"）都已证伪；
> 但 2026-11-11 实测发现 **USB-C 口是 CH340 串口（COM3），937500 8N1，官方有线协议握手已成功**。
> 下一步主线 = 把这条 USB-C 通道吃透（下载程序、运行期命令），同时验证 **C 用户程序能否用 libc socket**（若能，两板 WiFi 直连复活），
> 保底路线 = 端口 DO→AI bit-bang / 声 / 光。**Android 改造（root/改 APK）放到最后，且必须先用 MTKClient 全盘备份。**

---

## 0. 本会话新增实测（2026-11-11，全部基于用户真机）

### 0.1 实验 05 结果：机器人端 Python **没有 socket**

用户已跑完 `实验/实验05_运行环境探测.py`，结果文件：`双板通讯研究/实验/实验5返回结果.txt`（2026-11-10 17:57 生成），逐行：

```
env probe...
time=1  math=0  sys=1  os=1  socket=0  threading=1  struct=1  json=1
random=0  subprocess=0  serial=0  ctypes=0
py=3.4.5(default,Jan 18 2017, 19:44:59) [GCC 4.8]
cwd=/  ls=52
socket=0
No module named'_socket'
done
```

含义（`probe_one()` 成功 import=1，失败=0）：

| 模块 | 结果 | 说明 |
|---|---|---|
| `time sys os threading struct json` | ✅ | 纯 Python / 静态编入 libpython 的模块可用 |
| `socket` | ❌ `No module named '_socket'` | **没有 C 扩展 `_socket`** → 纯 Python 写 TCP 客户端/服务器 **不可行** |
| `math random subprocess serial ctypes` | ❌ | 同为 C 扩展（`math` 也缺），说明运行时没有 dynload 的 `.so` 模块 |

推论：机器人上的 Python 3.4.5 只带"编译进 libpython 的 C 模块 + 纯 Python stdlib"。
→ **原主报告里"若 socket 可用就走 WiFi"的待实测点，结论为：不可用。**（主报告 §0.0-A 已记录）
→ 但"C 用户程序"由机器人本机 gcc 编译、链接 bionic libc，**理论上仍可调用 POSIX `socket()`** —— 见 §4-W4，这是 WiFi 两板直连能否复活的关键。

### 0.2 USB-C = CH340 串口（COM3），且**官方有线协议握手已实测成功**

设备（Windows PnP，用户 2026-11-11 20:36 插上）：

| 项 | 值 |
|---|---|
| 名称 | `USB-SERIAL CH340 (COM3)` |
| InstanceId | `USB\VID_1A86&PID_7523\5&226F2F82&0&3` |
| 厂商 / 驱动 | wch.cn / CH340 驱动 3.9.2024.9（2024-09-16） |
| 到达时间 | 2026/11/11 20:36:53（就是用户说的"Type-C 连上了"） |
| adb | `C:\platform-tools\adb.exe devices` 为空；无其他 Android USB 设备 → **这个口不是 ADB gadget**，USB 调试/`adb` 不成立 |

官方 PC 软件（AbilixScratch3.0）走的就是这个口：反编译里 `UartManager`（`Assembly-CSharp.decompiled.cs:95827-96019`）用 `LibUart`（同文件 95287-95739）以 **937500 bps、8N1、读超时 1000ms** 打开 `\\.\COMx`；`UsbManager`（96120-96429）是另一条直连 USB 通道（同样 937500 8N1）。

**本会话写的实测脚本**：`双板通讯研究/实验/实验09_有线握手_CH340.py`（依赖 pyserial，已 `py -3 -m pip install pyserial` 装 3.5）

- 发送（type=0x6F=111=SKCON9，cmd1=176/0xB0，cmd2=1，seq=1）：
  `AA 55 00 08 6F B0 01 00 00 00 01 28`
- 接收：
  `AA 55 00 09 6F B0 01 00 00 00 00 01 29`（payload=`01`，校验和 OK）
- 官方判据（`BaseSK.RecvConnectDatasValidityHandler`，94897-94969）：`len>11 && recv[5]==176 && recv[6]==1 && recv[11]∈{1,40}` → **满足 = 握手成功**。

→ **结论：USB-C（CH340）是"电脑 ↔ 主板"的可用双向数据通道**，官方软件用它下载程序。
→ 下一步只需按同一协议把**文件下载**跑通（格式已全部解出，见 §2.6），即可获得"程序下发"能力。

### 0.3 主报告的更新

`双板通讯研究/README_可行性研究主报告.md` 已插入 **`## 0.0 2026-11-11 实测更新`**（A：实验 05 的 socket=0 详解；B：USB-C CH340 握手实测与协议；C：结论变化速览表），并在正文打了 11 处补丁（WiFi 行改 ❌、实验顺序、链路表、待实测清单等）。**以 §0.0 + 本交接文档为准。**

### 0.4 APK 侧新证据（2026-11-11 21:04；详细版见 `_交接素材/APK证据_素材.md`，465 行）

> 来源：`AbilixSetting_25.apk` / `AbilixUpdate_1.apk` / `Controller_43.apk` / `BlocklyC_V103.apk` 的 dex/manifest/证书静态分析（未真机验证处已标注）。

| # | 问题 | 结论 |
|---|---|---|
| 1 | 官方 adb.exe | **不可行/死文件**：C# 里只有常量 `COMMANDEXEC="adb.exe"`（`Assembly-CSharp.decompiled.cs:110819`），全工程无调用；Lua/DLL 零引用；设备也没有对外 ADB 接口 |
| 2 | 开 ADB | **间接可行（待实测）**：无现成开关（Setting 的 `AdbEnabled()` 只读 `adb_enabled`、无调用点）；但 **`AbilixSetting_25.apk` 是 `sharedUserId=android.uid.system` + AOSP testkey 签名**（证书 SHA-256 以 `c8a2e9bc…` 开头、notBefore 2008-04-15，与公开 testkey 一致）→ 可用公开 testkey 自签同包名更新包拿 system UID → 写 `adb_enabled=1`/起 adbd |
| 3 | 官方装 APK | **可行（有条件）**：`/sdcard/Abilix/update/*.apk` → 广播 `com.abilix.controller.service.ApkManageService.ACTION_SW_UPDATE`（receiver `exported=true`，无权限校验）→ `ApkManageService` 只比 versionCode → 系统 `com.grandar.installservice` 的 AIDL `installApk(path,pkg)` 安装；无签名/hash 校验。**同包名替换仍受 Android 签名约束**：Setting(testkey) 可换；Controller/Update(CN=Abilix) 不可伪造；**新包名**能否装取决于 grandar 白名单（待验证） |
| 4 | 有线下载第二套协议 | **可行**：机器人侧 `TransSerial`（`/dev/ttyMT0` @ **1,000,000**）：握手 `55 55 11` → 回 `0x61`(对)/`0x65`(错)；帧 15B 头（`[0..1]=55 55`、`[2]=cmd(5 写码 / 6 结束)`、`[10..13]=长度 BE`、`[14]=8 位和`）+ ≤2064B 分片 → 落 `/sdcard/Abilix/tmp/tmp.zip` → `handleProgramZip`（zip 内需 `zip_temp/` 前缀，取 `.c/.py/.js`）。PC 侧 AA55 帧（cmd1=176 握手 / cmd1=1 传文件）波特率 937500 —— **两套的波特率/对应关系待实测**（我们已实测 937500 AA55 握手成功） |
| 5 | C 用户程序 | **可行（应用沙箱内，无 root）**：8890 传 C（`fileType=20`）落 `/sdcard/Abilix/tmp` → `ControllerService.handleProgramZip` → `CompileUtil.compile` 自动编译（机器人本机 gcc4.8.2，`-pie -fPIC -lm -lRobot -shared`）→ 产物复制为 `filesDir/libuser.so` → `System.loadLibrary("Robot")` 后 JNI `JCC_Main` 在 Controller 进程内 dlopen；**C 可调 libc `socket/open/system`**，有 INTERNET + 读写 /sdcard 权限，无 root、不能写 `/data/local/tmp` |
| 6 | 8890 文件传输 | **可行且无鉴权**：帧同 AA55；`FileTrans` payload=`appType[0],fileType[1],size[2..5]BE,crc[6..9]BE,name[10..]UTF-8`；fileType=1→`/sdcard/Abilix/update`，2/4/14/16→tmp，20/21→tmp+自动处理；`getFilePath` 不过滤 `../`、appType>4 走绝对路径、unZip 无 canonical 校验 → **路径穿越/任意写/ZipSlip 成立**（待真机确认落点） |
| 7 | 其他入口 | 8890/10086 TCP、7777/9999 UDP 无鉴权；Controller `ProtocolService`/`UVCService`、Setting `SettingReceiver`（关机/熄屏/休眠广播）、Update `UpdateReceiver`/`ApkManageService` 均可从外部触发 |

**一句话**：Android 侧最强的两条新路 = **① 8890 无鉴权投递 APK（传完自动触发安装）**、**② testkey 换 Setting 拿 system UID（进而开 ADB）**；C 程序路径也已打通到"8890 传 → 机器人自己编译"，这使 W4 不再依赖 adb。

---

## 1. 用户当前目标（m00547 原文大意，供新会话对齐）

1. 用户已找到主板，用 **Type-C 线连到 PC**（已确认 = COM3 CH340）。
2. 用户写了一份实验报告（即 §0.1 的 `实验5返回结果.txt`），要求**纳入研究结论**（已完成）。
3. 要求把全部内容**重新梳理**，写一份**交接文档/提示词**，用户会**新开一个 AI 会话**继续推进（本文档即该交付物）。
4. 要求梳理**接下来连接安卓主板需要的工具**，特别是**修改安卓**方面的软件工具，用户会去下载（见 `工具下载清单_安卓与逆向.md`）。

---

## 2. 硬事实基线（新会话必须知道，全部有证据）

### 2.1 硬件

- 主板型号 **SKCON9**（九代），机型码 **111（0x6F）**。
- 双处理器：**MTK6580** 1.3GHz（Android 主控，4G Flash / 512M RAM）+ **STM32F103VET6** 72MHz（512K Flash / 64K SRAM，实时外设）。
- I/O：12 路 RJ11 口（AI/DI/DO、UART×10、可复用 I²C×2；**端口自动识别传感器类型**，手册 p11-14）。
- 电机：4 路 RJ11（电池电压 7.4V，单路 1.5A）；SERVO 1 路 RJ11（485）。
- 无线：WiFi 仅 2.4G（WLAN + 热点两种模式）；蓝牙；3.5" 触摸屏/扬声器/麦克风/陀螺仪。
- 电池 7~8.4V；USB-C 口 = **CH340 串口**（不是 ADB）。

### 2.2 机器人运行环境（关键约束）

| 项 | 事实 |
|---|---|
| 程序形态 | Python 3.4.5（用户程序，走 StarCore + libstarpy）；另有 C 用户程序（本机 gcc4.8.2 编译） |
| Python 可用 | `time sys os threading struct json` + 纯 Python stdlib |
| Python 不可用 | **`socket`（无 `_socket`）**、`math random subprocess serial ctypes`（无 dynload .so） |
| 进程 cwd | `/`；`os.listdir('.')` 可见 52 项 |
| 程序目录 | `getPackageName()/python_dir/`（Controller 包名 `com.abilix.controller`） |
| 入口 | `ProgramAndInterfacePython.runPython → PythonTask`；模板 `#!/usr/bin/python3 / import threading / import time / import libstarpy / robot = Robot()` |
| C 程序 | 机器人本机 `/system/xbin/gcc4.8.2/bin/arm-linux-androideabi-gcc *.c -pie -fPIC -L. -lm -lRobot -shared -o librobot_xxx.so` → 复制为 `libuser.so` → `libRobot.so` 的 JNI `JCC_Main` 加载执行 |
| C↔Java 桥 | `libRobot.so` 把 C API 变成 `"API名&参数"` 字符串，经 `CCJ_Interface` JNI 交给 Java 层 |

### 2.3 EEPROM（"读写数据"）

- 128 个 32 位整数槽（1~128），掉电不丢；**在本板 STM32 内部 Flash（≈`0x0801F000`，128×32B）**，不是 MTK 文件。
- 11~20 号被官方环境采集占用，用户程序建议用 21 以上（实验里用 100+）。
- 访问链：`SetEE/GetEE` → CCJ 分派码 13/14 → `ControllerApi.getData/setData` → AIDL → STM32。
- **不存在"从 I/O 口访问 EE"的总线**，也不存在"端口 UART 透传"分支（STM32 固件里没有）。

### 2.4 STM32 固件要点（决定方向1/2 的关键）

- `stm32.bin`：24,172B 合法 APP 镜像，加载基址 **`0x08004000`**（`0x08000000–0x4000` 是 bootloader），复位 `0x08004145`。
- 帧解析 `0x080051F8`：校验 `AA 55`、按 `buf[2]` switch 1..4、在 `buf+0x64` 回填 `BB 66` id `0x44`。
- 槽处理函数 `0x08007958 / 0x080077A4 / 0x08007EA4 / 0x08007CE8`：都是**内部外设处理**，**没有"把端口数据转发到其它 I/O 口 UART"的分支**。
- 引用外设：USART1(0x40013800)/USART2(0x40004400)/USART3(0x40004800)+DMA1+GPIOA-E+RCC+FLASH；**未发现 ADC/I²C/SPI/TIM 基址引用**（与"端口采样在 MTK 侧/专用芯片"的分析一致）。

### 2.5 MTK ↔ STM32 主链路（板内）

- `/dev/ttyMT1` @ **2,000,000 bps**：主数据链路。
- `/dev/ttyMT0` @ **1,000,000 bps**：PC 下装/升级通道（3 字节握手 → zip 落盘）。
- 下行 32B：`AA 55 | 槽位1..4 | 0x20 | 电机[4-7] | DO[8-9] | 槽载荷[10-29] | [30]升级 | [31]字节和`
- 上行 72B：`BB 66 | 槽位 | 0x44 | AI[4-15] | 编码器[40-43] | 陀螺[44-49] | 槽载荷[50-66] | [67]电量 | [69]版本 | [71]字节和`
- 4 槽轮转，MTK ≥1.5ms 发一帧；**传感器值每帧广播，App 只读缓存**（无逐传感器阻塞读取）。

### 2.6 官方有线/无线下载协议（已全部解出；新会话直接照抄）

**帧格式**（`RobotUtils.buildProtocol/addProtocol`，`Assembly-CSharp.decompiled.cs:99580-99624`）：

```
AA 55 | lenHi lenLo | type cmd1 cmd2 | 00 00 00 | seq | data... | sum8
- len = 帧总长 - 4（大端 16 位）
- sum8 = 前面所有字节和的低 8 位
- seq = DATA_PACKAGE_INDEX 先自增再 %255（初值 1 ⇒ 首帧 seq=2）
- 最小帧 12B（data 为空）
```

**命令表**：

| 场景 | type | cmd1 | cmd2 | 说明 |
|---|---|---|---|---|
| 握手（连接确认） | 111 | 176 (0xB0) | 1 | 应答 `176,1`，payload `[0]=1`（BaseSK 还接受 40） |
| 心跳启动 | 111 | 0 | 2 | 负载 10B（APP/版本/平台） |
| 心跳周期 | 111 | 0 | 4 | 每 1000ms |
| 文件请求 | 111 | 1 | 1 | payload=`appType=3,fileType=21,len LE32,CRC32 LE32,fileName` |
| 文件分块 | 0（未扫描时 ROBOT_CONNECTED 默认） | 1 | 3 | 每块 ≤1024B（串口 SK9 READ_BUFFER）/≤10240B（TCP） |
| 文件结束 | 0 | 1 | 4 | 空负载 |
| 应答 | 机器人 type=111 | **160 (0xA0)** | 1/3/4/2/7 | 1=允许发送；4=心跳/分块 ACK；3=成功；2=CRC 错；7=文件已存在（官方视为成功） |

- 机器人应答 data 从**偏移 11** 开始。
- **CRC32 = zlib 标准**（反射多项式 0xEDB88320、初值 0xFFFFFFFF、结果取反）。
- 文件名编码 `Encoding.Default`（中文 Windows = GBK/ANSI）；纯 ASCII 名无差异。
- 下载物是 zip：文件名 `<程序名>.py.zip`，内部条目 `<程序名>.py/<程序名>.py`；deflate level 6；官方生成的本地头 csize 写成 `0xFFFFFFFF`（自制 zip 可能要补这个字段，需实测机器人是否宽容）。
- 无线（参考）：TCP **10086** 心跳、**8890** 文件；UDP 7777 扫描。串口（USB-C/CH340）走同一套帧协议，只是承载在串口上。
- 权威参考：`逆向资料/下载分析/协议规格.md`（606 行，WiFi 版；串口差异见 C# `SK9`/`LibUart`）。

### 2.7 Android 侧信息

- 机器人端"大脑 APP"：`Controller_43.apk` = `com.abilix.controller` v1.0.43（versionCode 43，minSdk 21/targetSdk 27），**未声明 debuggable**，不可 `run-as`；组件 `RunningService(:running)`、`ProtocolService(:protocolservice)`、Netty TCP 10086/8890、UDP 7777/9999。
- 位置：`D:\Program Files\AbilixScratch3.0\StreamingAssets\standalonewindows\hot_update_dir\extenddatas\brainApk\6F\Controller_43.apk`（**千万不要用 PC 端源码里的旧固件覆盖真机**，除非已备份）。
- `AbilixSetting_25.apk`（设置）、`AbilixUpdate_1.apk`（升级）、`BlocklyC_V103.apk`（Chart C 运行端，40B 定长帧，不含 Python 运行时）。
- adb 现状：`C:\platform-tools\adb.exe` 可用（1.0.41/37.0.0），但 CH340 口不是 ADB；**要 adb 必须另找途径**（WiFi adbd 改造、串口 console、root 后开 adbd、或直接改 Controller）。

---

## 3. 最终判定（两板通讯"能不能做"）

### 3.1 方向 1：一条线连两板 1 号口，A 直接读/改 B 的"数据地址" → ❌ 不可行

| 层 | 结论 | 原因 |
|---|---|---|
| 应用层 | ❌ | 积木/Python API 里没有任何"发送/接收/串口"方法；`get_ee/set_ee` 只作用于**本板** STM32 |
| 协议层 | ❌ | MTK↔STM32 的帧里没有"把本板 EE 读写请求转发到某个 I/O 口"的命令；STM32 无端口 UART 透传分支 |
| 电气层 | ❌ | I/O 口由 MTK/端口芯片自主轮询采样，不是"对外总线"；直接把两板 1 号口用普通 RJ11 线对插还有 **VCC-VCC 顶牛**风险 |
| 固件层 | ❌ | EE 区在 STM32 片内 Flash，只有本板 MTK 能经 AIDL 访问；I/O 口没有引出 SWD/存储总线 |

**但方向 1 的"变体"可行**（见 §4-W5）：A `set_do(portX,1/0)` → B `get_ai(portX)`/`get_touch(portX)` 读电平变化（bit-bang），
需自制 **GND+SIG 两针线 + 串联 1kΩ**，先单板自环验证空置端口可读外部电平；**禁止**普通 RJ11 直插。

### 3.2 方向 2："传感器自身既能收又能发" → ❌ 固件不支持

- STM32 自主轮询采样，读取动作不触发任何发射；没有"端口自定义串口"、没有"端口发射"命令。
- 但"用**执行器**（灯/喇叭/电机）发、用**传感器**（光敏/麦克风/灰度）收"是可行的，属于替代方案：

| 链路 | 收发器件 | 实测/预期速率 | 备注 |
|---|---|---|---|
| 声音 OOK | A 播放 mp3 响/静 → B `get_mic` | 1~10 bps | `get_mic` 只有声强，无音高 → 只能 OOK/长短音 |
| 光链路 | A 彩灯/智能灯/屏幕 → B 光敏/颜色光敏/灰度 | 10~50 bps | 实验 03 已写程序；遮光可提高信噪比 |
| 端口 bit-bang | A `set_do` → B `get_ai/get_touch` | ~10~100 bps | 方向1 的物理实现，需自制线；实验 02 已写 |
| 传感器对射（灰外/红外/超声） | 固件自主采样，对方无法控制发射时序 | 不可控 | 仅黑盒试，别当方案 |

### 3.3 结论变化速览（相对 turn 1 主报告）

- WiFi 纯 Python（socket）路线：**❌ 已实测关闭**。
- USB-C 有线通道：**✅ 新发现，已握手成功** → 可做"PC→机器人程序下发/运行期控制"。
- 两板通讯现状：**没有现成的"板↔板"无线/总线通道**；可行路径只剩：
  1. **C 用户程序 + libc socket**（若可行，两板同 WiFi 路由器可 TCP 直连，最优，待实测）；
  2. **PC 中继**（两板各自连 PC：一板 USB-C，另一板 USB-C/或 WiFi 10086；PC 转发）；
  3. **端口 bit-bang**（保底，慢但确定）；
  4. **声 / 光**（非接触保底）。

---

## 4. 下一步 WBS（新会话按序做，每步都有成功判据）

> 通用：PC 侧脚本用 Python3 + pyserial（已装）；机器人侧 Python 必须 **3.4 兼容**（不能用 f-string/socket）；
> 每改一处都记录"证据文件路径 + 时间戳"；**不碰升级/刷机**，除非 §4-W7 备份完成。

### W0（5 分钟，成本最低）先用串口终端"扫"一下 COM3

- 用 PuTTY / Tera Term 打开 **COM3**：先 115200 8N1，再试 921600 8N1（本地回显、日志开起来），看有没有启动日志/控制台/shell 提示符。
- 目的：确认这个 USB-C 口到底接的是 **MT6580 的调试 UART**（可能直接给 shell/ADB 开关）还是 **STM32 的 UART**（只认官方协议帧，115200 下应是乱码/静默）。
- 若出现 shell：先找 `adb`/`usb debugging`/`setprop service.adb.tcp.port 5555` 之类开关——**这比刷机安全得多，优先尝试。**
- 同时试一次 **1,000,000 8N1 + 手发 `55 55 11`**（机器人侧 TransSerial 协议，见 §0.4 第 4 条）：若回 `0x61`，说明这条口也能直接进"PC 下载"状态机（比 AA55 文件协议更简单）；若静默/乱码，以 937500 AA55 为准（已实测成功）。
- 若只是乱码/静默：不用折腾，回到 W1 用 USBPcap 抓官方协议。

> **W0 实测结果（2026-11-11 21:15，新会话首轮，脚本 `实验/实验12_W0_串口扫描与TransSerial探测.py`，原始日志 `_分析临时/研究证据/W0_串口扫描/2026-11-11_2115_W0_raw.log`）**：
> ① **115200 / 921600 被动监听 2s：0 字节** → 这个口**不是 MT6580 调试串口**，没有启动日志/shell 提示符（W0 的"找 shell 开 adb"分支关闭，不用再试 PuTTY）。
> ② **1,000,000 8N1 发 `55 55 11` ×3：0 字节** → 机器人侧 TransSerial 握手**没有**在这条物理口上出现（要么 CH340 接的是另一颗 UART，要么机器人端 TransSerial 未进入接收状态；947500 对照成功说明口是通的，不是线/供电问题）。
> ③ **937,500 AA55 握手：成功**（本次收到 **两帧**应答：`AA 55 00 09 6F B0 01 00 00 00 01 01 2A` + `AA 55 00 09 6F B0 01 00 00 00 02 01 2B`，seq=1、2，payload 都是 01）→ 通道在线；"双应答"现象待后续抓包解释，不影响握手判据。
> → **结论：COM3 只认官方 AA55 协议（937500）；后续下载/控制一律走 AA55，TransSerial 1M 路线的物理口未定位，暂不投入。**

### W1（10 分钟）复现握手 + 抓官方软件的真实下载序列

- 复现：`py -3 双板通讯研究/实验/实验09_有线握手_CH340.py --port COM3` → 应打印 `HANDSHAKE OK`（已验证）。
- 抓包（二选一）：
  - **推荐**：装 Wireshark（自带 USBPcap）→ 抓 `USBPcap1`（CH340 bulk）→ 打开官方软件下载一个程序 → 导出 USB 流量，按 `AA 55` 过滤，得到官方完整帧序列（对齐 §2.6）。
  - 备选：com0com 建虚拟串口对（COM10↔COM11），写"串口代理"：官方连 COM10 ↔ 我们的代理 ↔ COM3 真板；同时设置官方 PlayerPrefs `portName=COM10` 保证优先选它（Unity PlayerPrefs 在注册表 `HKCU\Software\<公司>\<产品>`）。
- 成功判据：拿到"官方软件从握手到 160,3 成功"的完整十六进制流水，且与 §2.6 一致。

### W2（30 分钟）用自写脚本下载一个 Python 程序到主板

- 目标：`hello.py`（打印 + 写 EE）→ 打包 `<name>.py.zip`（内部条目 `<name>.py/<name>.py`，deflate6）→ 按 W1 序列发送。
- 关键参数：串口 937500/8N1；帧见 §2.6；`type=111`（请求）/`0`（分块）；分块 1024B；结束帧后等 `160,3`。
- 若 `160,2`（CRC 错）→ 检查 CRC32 是否 zlib、len 字段 LE；若超时 → 试 `type=111` 发分块、试在请求后补心跳、降低分块到 512B。
- 成功判据：机器人屏幕出现 hello 程序输出（或 EE 值变化）；官方软件"已存在的程序"列表能看到它。
- 产出：`双板通讯研究/实验/实验11_有线下载_自写协议.py` + 结果记录。

### W2.5（新增，优先，零风险）打通 8890 无鉴权通道（机器人 WiFi 侧）

- **目标**：PC 用 Python socket 连机器人 **8890**（同 2.4G 路由器/热点），按 AA55 帧发文件；先传无害文件/APK 到 `/sdcard/Abilix/update`，再发 `cmd2=9` 观察是否自动安装。
- **前置**：知道机器人 IP（机器人「设置→WLAN」看；或扫 10086 端口；PC 与机器人同网段、关 AP 隔离）。
- **成功判据**：`/sdcard/Abilix/update/` 出现文件；若装的是新包名自签名 APK 且安装成功 → 说明 grandar 服务不设白名单（**可直接装自己的 App，不必 root**）。
- 失败时记录：10086 心跳是否正常、8890 是否直接 RST、安装报错（需 logcat/界面提示）。
- **注意**：8890 无鉴权、有路径穿越，实验只用无害文件；成功后立即删除测试文件。

> **W2.5 实测结果（2026-11-11 21:2x~21:35，已打通 8890 文件通道）**
> ① 机器人 WiFi IP = `192.168.1.103`（用户提供，PC WLAN `192.168.1.102`）；`ping` 4ms；**TCP 10086 / 8890 均 OPEN**（5555/22/8080/9999 关闭）。
> ② 心跳：`node WER_VSCode_工具/vscode-extension/src/werProtocol.js ping 192.168.1.103` → `{"ok":true,"robotType":111,"latencyMs":1113}`。
> ③ 文件下载：`node werProtocol.js download 192.168.1.103 样例_W2PROBE.py W2PROBE` → 请求帧 `aa 55 00 20 6f 01 01 ...`（appType=3、fileType=21、len LE、CRC32 LE）→ 机器人回 `160,1` 允许 → 272B 分块 → 回 `160,3` 成功，耗时 1292ms，`{"ok":true,"bytes":272}`。
> ④ 证据日志：`_分析临时/研究证据/W2.5_8890无线下载/2026-11-11_2135_W2.5_首次下载.log`；测试程序 `双板通讯研究/实验/样例_W2PROBE.py`（不会自动运行）。
> → **结论：PC ↔ 机器人 WiFi 文件通道（8890，无应用层鉴权/无配对）实测可用，后续 C 程序下发（W4）与 APK 投递（W2.5 第二步）都以它为基座。** 第二步"远程装 APK"仍按红线先征得用户同意。

### W2.6（新增，需用户明确同意）testkey 换 Setting 拿 system UID → 开 ADB

- **前提**：W2.5 已能投递并安装 APK（或找到其它投递/触发方式）；从 AOSP 公开仓库取 `testkey.pk8`/`testkey.x509.pem`（`build/target/product/security/`）。
- **步骤**：用 apksigner 签一个最小 APK（package `com.abilix.controller.setting`、`sharedUserId="android.uid.system"`、versionCode≥26、`WRITE_SECURE_SETTINGS`）→ 8890 fileType=1 投 `/sdcard/Abilix/update` → cmd2=9 安装 → 装后写 `Settings.Global adb_enabled=1` 或 `setprop service.adb.tcp.port 5555; stop adbd; start adbd` → PC `adb connect <IP>:5555`。
- **回滚**：保留官方 `AbilixSetting_25.apk`（`D:\Program Files\AbilixScratch3.0\...\brainApk\6F\`），失败可原样再投递；安装失败一般不影响现有设置 App（INSTALL_FAILED_* 会拒绝更新）。
- **成功判据**：`adb devices` 出现设备 / `adb shell getprop ro.build.version.release` 有输出。
- **风险**：替换 system UID 应用属于高风险改动；**先问用户**，并保证官方 APK 已备份、电量充足。

### W3（30 分钟）验证 USB 通道"运行期"能力（决定 PC 中继是否成立）

- 问题：程序**运行中**，PC 能否通过 USB-C 发命令（读传感器/写 DO/读 EE）？还是只能下载？
- 手段：官方协议里 `cmd1=17 (STM32Common)`、`cmd1=176 (AbilixChart)` 两类命令；先在 C#/协议规格里找它们支持的子命令，再用 W1 抓包看官方 UI 在"连接但未下载"时发什么（心跳 0,2/0,4 之外）。
- 若"运行期命令"可用 → **PC 中继方案成立**（PC 读取 A 的传感器/写 B 的 DO），两板通讯可通过 PC 软件实现；
- 若不可用 → 中继只能靠"下载阶段"离线写程序，运行期无法交互，PC 中继降级为"预编排"。

### W4（关键，1 小时）C 用户程序能否用 libc socket（WiFi 两板直连的生死判据）

- 前提（**APK 证据已把"编译"打通**）：8890 传 C（`fileType=20`）落 `/sdcard/Abilix/tmp` 后，`ControllerService.handleProgramZip` 会解压并 `CompileUtil.compile`（机器人本机 gcc4.8.2，`-pie -fPIC -lm -lRobot -shared`）；产物复制为 `filesDir/libuser.so` 后由 JNI `JCC_Main` 在 Controller 进程内加载。**待验证点只剩"如何触发起跑"**（ProgramRepo/运行指令/官方 C 模式入口）。
- 若 8890 不方便，也可走 USB-C 串口把 zip 塞给 `TransSerial`（55 55 11 @ 1M）→ `/sdcard/Abilix/tmp/tmp.zip`（zip 内需 `zip_temp/` 前缀）。
- 测试程序（最小）：
  ```c
  #include <sys/socket.h>
  #include <netinet/in.h>
  #include <arpa/inet.h>
  int main(){ int fd = socket(AF_INET, SOCK_STREAM, 0); /* 连 PC 或另一板 */ }
  ```
  编译：`arm-linux-androideabi-gcc test.c -pie -fPIC -L. -lm -lRobot -shared -o librobot_test.so`（或与官方 C 工程一致），复制为 libuser.so 执行。
- 同时探测：`getprop`、`/proc/net/tcp` 可读性、能否 `os.system()`（Python 侧 `os` 可用，尝试 `os.system('getprop ro.build.version.release')` 写 EE）——低成本高价值。
- 成功判据：C 程序能 `socket()` 成功并 `connect()` 到 PC（PC 监听 12345）；若成功 → 两板同 2.4G 路由器 + 静态 IP，C 程序 TCP 直连，**两板通讯成立（最优方案）**。
- 失败判据：`socket()` 返回 EACCES/EPERM 或 SELinux 拒绝 → 记录 errno，转向 W5 保底 + W6 Android 改造。

> **W4 进展（2026-11-11 21:26，C 程序包已成功下发并触发机器人自编译）**
> ① 静态逆向已把链路读穿（证据在 `_分析临时/apk分析/提取/`）：8890 收 `fileType=20` 的 zip → `ControllerService$5.onStateChanged` COMPLETED → `handleProgramZip()`：解压到 `DIR_TMP/<millis>` → 要求顶层目录名 = zip 名去 `.zip` → 扫第一个 `.c/.js/.py` 文件 → 覆盖同名程序 → 改名到 `DIR_PROGRAM/<v5>` → `insertOrReplace` → **fileType==20 时调 `CompileUtil.compile()`**（`/system/xbin/gcc4.8.2/bin/arm-linux-androideabi-gcc *.c -pie -fPIC -L. -lm -lRobot -shared -o librobot_<name>.so`，编译失败写同目录 `error.log`）。运行链 `ProgramAndInterfaceC.startRunning()`：`.so` 不存在→编译；`error.log` 存在→把错误 print 到机器人屏幕并返回 -1；成功→复制为 `filesDir/libuser.so` → `ProgramMainThread` → native `JCC_Main` → `dlsym("Main")`。
> ② 包格式按逆向构造：zip 名 `W4PROBE.c.zip`、内部条目 `W4PROBE.c/W4PROBE.c`（镜像 PY 的 `<name>.py.zip`）。探针源码 `双板通讯研究/实验/实验14_W4_C探针/W4PROBE.c`（不 include Robot.h，导出 `int Main(int,char**)`，连接 PC `192.168.1.102:12345` 回传 pid/getprop/`/proc/net/tcp`/`/proc/self/maps`，并写 `/sdcard/Abilix/tmp/w4log.txt`）。
> ③ 下发脚本 `双板通讯研究/实验/实验14_W4_C程序下发.js`（复用 `werProtocol.js` 的 HeartbeatClient/FileTransferClient，appType=3、**fileType=20**）执行结果：`160,1` 允许 → 2261B → `160,3` 成功，耗时 567ms（即机器人已解压、落库并调用 gcc 编译；编译成败协议不返回）。
> ④ 证据日志：`_分析临时/研究证据/W4_C程序/2026-11-11_W4_首次C程序下发.log`；PC 侧监听脚本 `实验14_W4_PC监听.py`（12345，等待 C 程序主动连接）。
> ⑤ **W4 实测结果：✅ 成功（2026-11-11 21:28）**。用户在机器人屏幕运行 `W4PROBE.c` 后，PC 12345 监听器收到两次 TCP 连接（21:28:05 / 21:28:58，来源 `192.168.1.103:43309/43310`），回传：`W4PROBE socket ok pid=1325`、`getprop`=**Android 5.1 / LMY47I / 机型 abilix_c9_l / 指纹 ...user/test-keys**、`/proc/net/tcp`（`6701A8C0:A92D→6601A8C0:3039 st=01 ESTABLISHED uid=10017`，uid 为普通应用 10017 不是 system/root）、`/proc/self/maps` 头部。→ **C 程序在 Controller 进程内 `socket()`/`connect()` 成功，`system()`/文件读取均可用；两板 WiFi TCP 直连方案成立，无需 root/ADB。**
> ⑥ 证据：`_分析临时/研究证据/W4_C程序/2026-11-11_W4_PC监听_12345.log`（87 行，含两次连接完整回传）。下一步 W5：让两块板各跑一个 C 程序做 A↔B 直连（A 监听端口当 server、B 当 client），并解决"程序自动起跑"（`startRunning` 的远程触发点尚未找到，目前只能屏幕点运行）。

### W5（1 小时）两板通讯落地（按优先级）

1. 若 W4 成功：C 程序 TCP 直连（A 服务端、B 客户端），测试吞吐/延迟（目标 ≥10kbps、<50ms）。
2. 若 W3 成立但 W4 失败：PC 中继（两板都接 PC USB-C；PC 转发 DO/AI/EE 命令）。
3. 保底 A：端口 bit-bang（`实验02`，先单板自环 → 两板；测 0.1/0.05/0.02s 位宽成功率）。
4. 保底 B：声音 OOK（`实验01`）/光链路（`实验03`），只用于低速指令/信标。
- 全部记录到 `实验/README_实验总览与步骤.md` §7 判断表。

> **W5 进展（2026-11-11 21:41，等第二块板，用户已暂停）**
> ① 三件套已建：`实验15_W5_C探针/W5SERVER.c`（A 板回显服务器 `0.0.0.0:8888`）、`W5CLIENT.c`（B 板客户端，连 A 后 10 次 PING + 4096B 回显测吞吐）、`实验15_PC监听_多连接.py`（PC 12345 多线程观测）；另有单板自环一体程序 `W5SELFTEST.c`（server+client 同进程）。
> ② **单板方向验证 ✅（2026-11-11 21:34）**：A 板运行 `W5SERVER.c`（pid=2689）监听 8888 后，PC 直接连 `192.168.1.103:8888` 回显 3/3 成功（RTT 3.3~87.9ms），4096B 回显 10.8ms ≈ **6.1 Mbps 双向**；板侧报告通道可见 `peer connected from 192.168.1.102:63064`、`echo 10/1460/1176 bytes`。证据：`_分析临时/研究证据/W5_自环/2026-11-11_2135_W5自环_PC探针.log` + `2026-11-11_2134_W5自环_PC监听.log`。
> ③ **关键限制（新发现）**：机器人同一时刻只能运行**一个**用户程序——在 A 板上先跑 server 再跑 client，client 启动会把 server 顶掉（证据：server 报告通道 21:34:35 CLOSED，client 21:34:37 起连 8888 连续 `errno=111` 拒绝）。→ 两板方案不受影响（各跑一个）；单板自环必须用一体程序 `W5SELFTEST.c`。
> ④ 状态：`W5SERVER.c`（21:31）、`W5CLIENT.c`（21:33）、`W5SELFTEST.c`（21:35）均已 `160,3` 下装成功、已在机器人程序库；`W5SELFTEST.c` 已下发但用户暂停未运行（PC 监听已停）。
> ⑤ 明天第二块板到位后：① 板连同一 WiFi，报 IP；② 我扫 10086/8890 确认 SKCON9（心跳 robotType=111）；③ 下发 `W5CLIENT.c` 到 B；④ A 跑 `W5SERVER.c` → B 跑 `W5CLIENT.c`，PC 12345 观测 PING/吞吐；⑤ 若 `errno=111`/超时，先查路由器 AP 隔离、两板网段、机器人 WiFi 休眠。
> ⑥ **W5 两板实测结果：✅✅ 成功（2026-11-12 12:51，项目核心目标达成）**。新网络环境：PC `192.168.47.192`、掩码 `255.255.254.0`（⇒ `192.168.46.x` 与 `192.168.47.x` 同属 /23 网段，ARP 同接口）、网关 `192.168.47.254`；A 板（旧）`192.168.46.109`、B 板（新）`192.168.47.199`，两台心跳均回 robotType=111。按上述步骤把源码内 `PC_IP` 改为 `192.168.47.192`、`SRV_IP` 改为 `192.168.46.109` 后重下：A 板 `W5SERVER.c`（2334B/838ms/160,3）、B 板 `W5CLIENT.c`（2608B/671ms/160,3）。运行后：B 连 A `192.168.46.109:8888` 成功（A 侧 `peer connected from 192.168.47.199:35548`）；**10/10 PING 正确**（RTT min 7.75 / avg 34.92 / max 63.61ms），**4096B 回显 57.8ms ≈ 1134 kbps 双向**，`BYE` 正常关闭。证据：`_分析临时/研究证据/W5_两板/2026-11-12_1251_W5两板_PC监听.log`。**至此两板 WiFi TCP 直连方案闭环。**

### W6（可选，风险高）Android 侧改造

- 先做**只读侦察**：确认 Android 版本、是否有 root、USB 调试开关是否可开、是否允许装第三方 APK（用 AbilixSetting/系统设置试）。
- 只在 W4 死路 + PC 中继不可接受时才考虑：root（MTKClient BROM）→ 开 adbd/装 Frida → hook `com.abilix.controller`；或 apktool 改 APK 重签替换（会被官方升级覆盖，且可能砖）。
- **任何写分区/刷机前必须先 §4-W7 全盘备份。**

### W7（安全前置，必须最先想清楚）

- MTKClient `readflash` 全盘备份（或至少 boot/preloader/system/userdata）；确认 BROM 未锁、有救砖路径；准备 SP Flash Tool + 官方固件（先找 `AbilixUpdate_1.apk`/OTA 包里的固件）。
- 电池电量 ≥50%；不边充电边操作；不短接；不把电机口(7.4V)接 I/O。

### W8（已完成，2026-11-12 晚）「双板通讯」原生积木 + 读写数据持久化

- **成果**：AbilixScratch3.0 左侧新增「双板通讯」分类，4 个积木：设置对方主板 IP / 发送 [值] 到地址 [ ] / 接收地址 [ ] 的信息（数字型，可当变量）/ 把地址 [ ] 的信息保存到读写数据。用户在 IDE 拖积木 + 真机运行全部通过（m01022 任务闭环）。
- **安装/还原**：`WER_函数库/安装包_双板通讯/`：右键管理员运行 `install_dual.cmd`（关 IDE → 自动备份当前 browser_assets → 替换 → 校验 sha256，失败回滚）；`restore_dual.cmd` 一键还原。补丁 sha256 `a2515601e51174f4649722883849a94e4a47629eaef5a8af34802f22d5cb3b3b`（6647 条目只改 4 个）。
- **重新构建**（改了积木/运行时后）：`py -3 WER_函数库/工具/双板通讯/构建双板通讯扩展.py` → 生成新 `browser_assets.patched` + 自动写入 sha 的安装脚本；自检会校验“只改 2 + 新增 2”且其余条目逐字节不变。
- **运行时**：prelude 注入到生成代码 `robot = Robot()` 之后；用 os.system/fork+pipe 调机器人自带 gcc4.8.2 把内嵌 C 助手编译到 `/data/data/com.abilix.controller/files`（`/sdcard` noexec），C 助手 UDP 8990 收发，Python 侧“地址→最新值”字典 + EEPROM 持久化（节流 1s/地址、仅变化时写；重启未收到时回读旧值；未写槽=0）。
- **边界**：对方完全不运行程序时收不到（需 Android 常驻服务，属高风险改造，需用户明确同意）。
- **证据**：`_分析临时/研究证据/实验20_读写数据持久化/README_实验20记录.md`（含 EETEST 两次照片、端到端结论）、`_分析临时/研究证据/实验19_双板通讯积木原型/`、`_分析临时/研究证据/实验18_Python网络可行性/`。
- **源码位置**：`双板通讯研究/实验/实验19_双板通讯积木原型/`（wl_prelude.py + 生成测试程序.py）、`WER_函数库/工具/双板通讯/构建双板通讯扩展.py`。

---

## 5. 已就绪资产（新会话直接复用，不要重造）

| 路径 | 内容 |
|---|---|
| `双板通讯研究/README_可行性研究主报告.md` | 主报告（含 §0.0 实测更新；§2 方向1、§3 方向2、§5 验证清单） |
| `双板通讯研究/分报告_方向1_端口与内存.md` | EE 边界、端口架构、DO→AI 方案、电气安全（420 行） |
| `双板通讯研究/分报告_方向2_传感器与光声链路.md` | 传感器电学表、发射源清单、链路速率排序（337 行） |
| `双板通讯研究/分报告_运行环境与替代链路.md` | CPython3.4/StarCore、ProbeEnv、WiFi/PC 中继/ADB/蓝牙评估（288 行） |
| `双板通讯研究/分报告_APK与串口协议.md` | 3 个 APK manifest、串口、帧格式、C/Python 执行链（298 行） |
| `双板通讯研究/分报告_STM32固件与串口协议.md` | STM32 结论卡片、EE 位置、无透传（233 行） |
| `双板通讯研究/实验/` | 00 接线安全、README 总览、01 声音、02 端口、03 光、05+05b 环境、08 WiFi、**09 有线握手（已验证成功）**、**10 能力深挖探测（新，待下载运行）**、实验5返回结果.txt |
| `双板通讯研究/新会话提示词.md` | 可直接粘贴给新会话的启动提示词（本文附录 A 的单文件版） |
| `双板通讯研究/工具下载清单_安卓与逆向.md` | 给用户的工具下载清单（精简版） |
| `双板通讯研究/_交接素材/工具清单_素材.md` | 工具清单**详细核实版**（2026-11 版本号/哈希/官方来源/安装顺序/风险，156 行） |
| `双板通讯研究/_交接素材/APK证据_素材.md` | **APK 侧证据（465 行）**：adb.exe 死文件、Setting testkey/system UID、更新链/8890 无鉴权、TransSerial 55 55 11、C 程序路径、导出组件清单、复现方法（Q1~Q7 + 附录） |
| `_分析临时/研究证据/运行环境/` | ProbeEnv（24 模块探测）、TCP A/B 样例、UDP 发现、PC 中继服务器 |
| `逆向资料/下载分析/协议规格.md` | 606 行 WiFi 下载协议规格（帧/命令/CRC/zip/GBK） |
| `逆向资料/decompiled/Assembly-CSharp.decompiled.cs` | 关键类：BaseSK 94897、SK9 95161、LibUart 95287、UartManager 95827、UsbManager 96120、buildProtocol 99580 |
| `_分析临时/stm32分析/`、`_分析临时/apk分析/`、`_分析临时/brainApk分析/6F/` | STM32/APK/机器人 APP 证据 |
| `WER_VSCode_工具/` | 官方 VSCode 扩展协议实现、mock 机器人、api 目录 |

---

## 6. 未解问题 / 需要用户或下一步回答

1. 主板 Android 版本？是否 root？USB 调试能否打开？（W6 侦察）
2. 官方 VSCode 工具支持 C 程序下载/运行吗？C 模式怎么进？（决定 W4 前提）
3. 两板是否都有 Type-C 数据线可同时接 PC？（PC 中继前提；也可一板 USB、一板 WiFi 10086）
4. 官方软件下载时是否已在 AbilixScratch 里看到"已连接 SKCON9"？（验证 CH340 通道对官方软件同样可用）
5. 用户是否愿意在 W4/W6 阶段承担 root/刷机风险（需先备份）？
- 6. 机器人 WiFi IP 是多少？8890/10086 从 PC 是否可达（同网段、AP 隔离关闭）？
- 7. grandar 安装服务是否对第三方签名/新包名设白名单？（决定能否直接装自己的 App）
- 8. testkey 路径是否真能更新 Setting（关注 INSTALL_FAILED_SHARED_USER_INCOMPATIBLE / UPDATE_INCOMPATIBLE）？
- 9. `TransSerial` 的 1M/`55 55 11` 与 PC 的 937500/AA55 的对应关系（是否同一物理口、是否自适应波特率）？
- 10. C 程序编译后如何触发起跑（ProgramRepo / startProgram 指令 / 官方 C 模式）？

---

## 7. 红线

- **不**用普通 RJ11 直通线对插两板同一端口；端口实验必须自制 GND+SIG 且串 1kΩ，先单板自环。
- **不**把电机口（7.4V/1.5A）接到 I/O 口。
- **不**在未备份情况下写 STM32/MTK 分区；**不**用 PC 端旧 APK 覆盖真机（版本必须匹配 6F/brainApkVersion）。
- EEPROM 11~20 是官方保留区；`set_ee` 不要放循环里狂写（Flash 寿命）。
- 机器人 Python 是 3.4：别写 f-string；别 import socket（会失败）。
- **远程安装 APK / 替换 system UID 应用（Setting）属于高风险实验**：必须先备份官方 APK、先问用户、只递无害测试包；不要尝试替换 Controller/Update（厂商 key，装不上还浪费一次升级流程）。
- 8890 无鉴权 + 路径穿越：只在自有设备、同网段做验证，测试文件用完即删，不外传利用方法。
- 不要相信 `adb.exe`（死文件）：本项目 Android 侧没有现成 ADB 通道，别在它上面浪费时间。
- PC 端"编译"只是 Python3.7.3 语法检查，不代表机器人能跑。

---

## 附录 A：新会话提示词（可直接整段粘贴）

```
你是这个工作区（D:\UserData\Documents\WER\2026普级赛）的新任 AI 研究员，接手"能力风暴 SKCON9 两块主板通讯"项目。
请先按顺序读：
  1) 双板通讯研究/交接文档_下一步Android与真机验证.md（最重要，含硬事实、判定、WBS）
  2) 双板通讯研究/README_可行性研究主报告.md 的 §0.0（2026-11-11 实测更新）
  3) 双板通讯研究/实验/README_实验总览与步骤.md 和 实验09_有线握手_CH340.py
  4) 逆向资料/下载分析/协议规格.md（第 1-160 行即可）
  5) 双板通讯研究/工具下载清单_安卓与逆向.md 与 双板通讯研究/_交接素材/APK证据_素材.md
已知事实（不要重新论证）：主板=SKCON9(111)；USB-C=CH340 COM3，937500 8N1，握手已实测成功（AA 55 00 08 6F B0 01 ... → 收到 176,1 payload=01）；
机器人 Python 3.4.5 无 socket（实验5返回结果.txt 已证实）；EE 在本板 STM32 Flash；端口不能读对方地址、传感器不能主动发射；APK 侧：adb.exe 是死文件、AbilixSetting 是 testkey+system UID、8890 无鉴权可投递/装 APK、C 程序可经 8890 fileType=20 自动编译并调 libc socket（无 root）、另有 TransSerial 1M 55 55 11 握手。
你的任务：按交接文档 §4 的 W1→W7 顺序推进，优先做 W2.5（8890 无鉴权通道，零风险）和 W4（C 程序 libc socket 探测）；W2.6（testkey 换 Setting）必须先征得用户明确同意。
每一步先向用户说明"要做什么/为什么/成功判据"，需要用户动手或下载工具时明确列出；遇到危险操作（root/刷机/写分区）先停下来要用户确认。
约束：PC 侧脚本用 Python3+pyserial；机器人侧 Python 必须 3.4 兼容；接线遵守交接文档 §7 红线；新证据写到 双板通讯研究/实验/ 或 _分析临时/研究证据/。
```

## 附录 B：工具下载清单

见同目录 `工具下载清单_安卓与逆向.md`（含下载链接、用途、优先级、风险）。

## 附录 C：本机环境速查

- 工作区：`D:\UserData\Documents\WER\2026普级赛`
- 主板串口：**COM3**（CH340，VID_1A86&PID_7523），已被官方驱动 3.9.2024.9 识别
- adb：`C:\platform-tools\adb.exe`（1.0.41 / 37.0.0；当前无设备）
- Python：`py -3` = 3.13.2；`python` = 3.12.4；已装 `pyserial 3.5`
- 官方软件：`D:\Program Files\AbilixScratch3.0`（StreamingAssets 内有 3 个手册 PDF、BlocklyC_V103.apk、brainApk、adb.exe）
- Web GUI（本会话）：http://127.0.0.1:51613 （新会话地址会变，不影响文件）

## 附录 D：关键字节速查

```
握手  TX: AA 55 00 08 6F B0 01 00 00 00 01 28
      RX: AA 55 00 09 6F B0 01 00 00 00 00 01 29   (payload 01)
帧    AA 55 | len=(total-4)BE | type cmd1 cmd2 | 00 00 00 | seq | data | sum8
应答  type=111, cmd1=160(0xA0), cmd2=1/3/4/2/7, data 从帧偏移 11
请求  type=111, cmd(1,1), data=[3,21, len LE32, crc32 LE32, filename GBK]
分块  type=0,   cmd(1,3), data=zip 前 1024B 块
结束  type=0,   cmd(1,4), data=空 → 等 160,3
CRC32 = zlib（0xEDB88320 / 初值 0xFFFFFFFF / 结果取反）
```
