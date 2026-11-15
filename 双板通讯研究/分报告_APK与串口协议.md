# 分报告：APK 逆向 —— 机器人端 API 实现与 STM32 串口协议

> **更新注记（Lead 汇总，2026-11-10）**：本报告的"待确认"项已由 `分报告_STM32固件与串口协议.md` 与 `分报告_运行环境与替代链路.md` 补齐：①6F=机型值 111=**SKCON9**（非"最可能"）；②EEPROM 确认在 **STM32 内部 FLASH**（≈0x0801F000，128×32B）；③`setSendCmd/setTTLCmd` 写入的槽载荷，STM32 按固定语义处理、**无转发到 I/O 口 UART 的分支**；④`/dev/ttyMT0` 为 **PC 下装/升级通道**（3 字节握手→zip 落盘），不是用户可用的透明串口。其余 APK/协议/执行链事实仍然成立。

> 任务：task-4（逆向研究员 apk-dex）。工作目录 `D:\UserData\Documents\WER\2026普级赛`。
> 证据目录：`_分析临时/apk分析/`（脚本可复现；提取文件在 `_分析临时/apk分析/提取/`）。
> 证据格式：`相对路径:行号`；文中【事实】= 反编译/字符串可直接证明，【推断】= 由实现逻辑推断，【待实测】= 需上机验证。
> 工具：`pip install androguard 4.1.4`（网络可用），用其 `DEX`/`AXMLPrinter` 做解析与指令级反汇编；未使用 jadx/apktool（本机无 java）。产物：3 个 APK 全量解包 + AndroidManifest 文本 + DEX 字符串/方法/类名清单 + 重点类全量 Dali 反汇编。

---

## 0. 一句话结论（先看这里）

1. 【事实】**官方安装目录里有两套机器人端 APP，都在 `/dev/ttyMT1` 上与 STM32 通信，协议同源（下行帧头 `AA 55`，上行帧头 `BB 66`，校验=字节累加和）**：
   - `BlocklyC_V103.apk`（`com.example.blocklyc`，旧）：固定 **40 字节**双向帧，`ttyMT1 @ 1,000,000 bps`（`SerialProcess.addProtocol`/`sendProtocol`）。
   - `Controller_43.apk`（`com.abilix.controller`，2020，6F 版；SKCON9 最可能对应它）：下行 **32 字节**帧（含 1~4 循环序号）/上行 **72 字节**帧，`ttyMT1 @ 2,000,000 bps`（`Protocol$MasterUART` + `MasterSerial`）。
2. 【事实】**Controller 另有一个透明转发串口 `/dev/ttyMT0` @ 1,000,000 bps**（`TransSerial` + `Protocol$TransUART`），是独立的第二路 UART，可收发裸字节（转发通道）。
3. 【事实】用户 C 程序**在机器人上本机编译**：`/system/xbin/gcc4.8.2/bin/arm-linux-androideabi-gcc *.c -pie -fPIC -lm -lRobot -shared -o librobot_xxx.so`，产物复制为 App 私有目录 `libuser.so`，再由 `libRobot.so` 的 JNI `JCC_Main` 加载执行（`CompileUtil.compile`、`ProgramAndInterfaceC.startRunning`）。
4. 【事实】用户 Python 程序由 **StarCore（srplab）运行时**执行：模板 `#!/usr/bin/python3 ... import libstarpy ... robot = Robot()`，依赖另一个系统 App `com.srplab.starcore`（`/data/data/com.srplab.starcore/lib/libstar_java.so`）与 `/system/lib/python/libpython3.4m.so`。
5. 【事实·方向1关键】Controller 的 `IControllerApi`（AIDL）**已对外暴露 `setSendCmd/getSendCmd/getSendCmdBuffer/getRecvCmd/getRecvCmdBuffer`**，且 `Protocol$MasterUART` 提供 `setTTLCmd(byte[])` 把任意字节写入循环发送帧的载荷区；`Robot.h` 中同名 API 经 `ProgramAndInterfaceC.CCJ_Interface` 字符串分发到 `IControllerApi` —— **用户程序存在"向 STM32 串口注入自定义字节"的现成通道**（受固定帧头/校验约束，详见 §4.5）。
6. 【事实·方向2关键】传感器（AI、灰度、超声、颜色、编码器等）**不是逐次"发命令-等回包"**：STM32 在**每一帧**上行数据里广播全部通道值，App 只从缓存 `recvCmd[]` 读取 → 采样率 = 串口帧周期上限（Controller 2M baud/32+72B → 理论数百 Hz，实际受主循环），**不存在逐传感器阻塞超时**。
7. 【事实】**EEPROM 不在 MTK 本地**：`SetEE/GetEE` 只是 3 参数/2 参数 API（`IControllerApi` 无 EE 方法；`CCJ_Interface` 把 `SetEE/GetEE` 转给 `application/Robot` → 串口/协议层），可判定为 STM32 侧存储（地址空间/读写命令字待 stm32-re 的 stm32.bin 侧确认）。BlocklyC 的 `Robot.getEE/setEE` 亦走 `Protocol`+`SerialProcess`。
8. 【事实】下载/控制网络服务在 `ControllerService.onCreate`：**TCPNettyServer(10086)、TCPNettyServer(8890)、UDPNettyServer(7777, 9999)**。`BlocklyC` 里另有 `ServerTcp`（下载/文件接收）。
9. 【事实】`Controller_43.apk`：`package=com.abilix.controller`，versionCode 43 / versionName 1.0.43，minSdk 21 / targetSdk 27，**无 `android:debuggable`（=false，release）**；`ProtocolService`、`UVCService` 带 `intent-filter` 且未写 `android:exported` → targetSdk<31 默认 **exported=true**；`MainActivity` 为 HOME+LAUNCHER（exported=true）。6E(`Controller_14`) 与 6F 的 manifest 仅版本号不同。
10. 【推断】`6E/6F` 是同一 App 的两代版本，6F(43) 更新；两包均 `com.abilix.controller`，**无法仅凭 manifest 区分 SKCON9**（需靠 brainApkVersion/机器人机型配置或运行日志，建议交 runtime-alt）。

---

## 1. 对象与提取结果

| APK | 路径 | 大小/文件 | 包名/版本 | 关键 |
|---|---|---|---|---|
| BlocklyC_V103 | `…/StreamingAssets/update/BlocklyC_V103.apk` | 2.1MB / 143 | `com.example.blocklyc` v1 | 旧 40B 协议、独立 `Robot` Java API、WebView JavaScriptActivity |
| Controller_43 (6F) | `…/hot_update_dir/extenddatas/brainApk/6F/Controller_43.apk` | 6.7MB / 898 | `com.abilix.controller` v43 | MasterUART 32/72B 协议、AIDL API、本机 gcc、StarCore Python、netty 服务 |
| Controller_14 (6E) | `…/brainApk/6E/Controller_14.apk` | 6.7MB / 901 | 同上 v14 | 仅版本号不同（`提取/manifest_Controller6E.xml`） |

提取命令与脚本（可复现）：`_分析临时/apk分析/extract_apks.py` → `apk_BlocklyC/`、`apk_Controller6F/`、`apk_Controller6E/`、`提取/filelist_*.txt`、`提取/manifest_*.xml`。
DEX 导出：`dex_dump.py`（BlocklyC：9319 strings/769 classes/7774 methods，`提取/dex_strings.txt` 等）、`dump_dex.py`（Controller：classes.dex 55109 strings/6185 classes/65082 methods + classes2.dex，`提取/dexstrings_Ctrl6F_classes*.txt` 等）。
反汇编：`dex_disasm.py`、`disasm_dex.py`、`scan_calls.py`（按调用点检索上下文）。

---

## 2. AndroidManifest（P0）

### 2.1 BlocklyC（`提取/manifest_BlocklyC.xml:1-31`）
【事实】`package="com.example.blocklyc"`，versionCode 1 / versionName 1.0，minSdk 16 / targetSdk 18，**`android:debuggable="false"`**，`allowBackup=true`，application `CameraApplication`。
- 权限：SYSTEM_ALERT_WINDOW、SYSTEM_OVERLAY_WINDOW、WRITE_EXTERNAL_STORAGE、MOUNT_UNMOUNT_FILESYSTEMS、WAKE_LOCK、ACCESS_WIFI_STATE、INTERNET、RECORD_AUDIO。
- 组件：`MainActivity`（MAIN/HOME/DEFAULT/LAUNCHER，exported 隐式 true）；`PrintfActivity/ProgramActivity/MotorActivity/SensorActivity/SettingActivity/EepromActivity/UpdateActivity/JavaScriptActivity/QRScanActivity/AIScanActivity` 无 intent-filter（targetSdk18 默认 exported=false）。
- => 【事实】无 debuggable，`run-as`/`adb shell` 直接读私有目录不可行；【推断】可 `adb shell am start` 启动 LAUNCHER 组件（shell 权限通常允许）。

### 2.2 Controller_43 / Controller_14（`提取/manifest_Controller6F.xml:1-51`）
【事实】`package="com.abilix.controller"`，versionCode 43 / versionName 1.0.43，minSdk 21 / targetSdk 27；**无 android:debuggable 属性（默认为 false）**；`allowBackup=true`、`supportsRtl=true`；application `com.abilix.controller.application.ControllerApp`。
- 权限：INTERNET、ACCESS_NETWORK_STATE、CHANGE_NETWORK_STATE、ACCESS_WIFI_STATE、CHANGE_WIFI_STATE、WRITE/READ_EXTERNAL_STORAGE、CAMERA、RECORD_AUDIO、BLUETOOTH、BLUETOOTH_ADMIN、SYSTEM_ALERT_WINDOW、SYSTEM_OVERLAY_WINDOW、WAKE_LOCK；`uses-feature`：bluetooth_le(required)、glEsVersion 2.0(required)。
- Activity：MainActivity（MAIN/VIEW/HOME/LAUNCHER，launchMode=2）；ProgramActivity；ProgrammingActivity；SensorActivity；ControlActivity；DataActivity；`RunningActivity`（`:running` 进程）；Service：`ControllerService`、`ProtocolService`（进程 `:protocolservice`，intent-filter action `com.abilix.controller.IControllerInterface`）、`RunningService`（`:running` 进程）、`CodeGeneratorService`（blockly 生成，**exported=false**）、`UVCService`（`:uvcservice`，两个 intent-filter action）。
- 【事实】按 Android 规则（targetSdk 27 < 31，未声明 exported 时以"有无 intent-filter"决定）：`ProtocolService`、`UVCService` 默认 **exported=true**；`MainActivity` exported=true；其余无 intent-filter 的 Activity exported=false。
- 【事实】`ProtocolService` 处于独立进程 `:protocolservice`，其 Binder 即下文 `IControllerApi`（AIDL）。
- 【推断】第三方 App/注入的 dex 可 `bindService(com.abilix.controller.service.ProtocolService, action=com.abilix.controller.IControllerInterface)` 直接调用 `setMotor/getAI/setSendCmd/...`；adb shell 自身不能直接 bind AIDL，但 `am start/broadcast`、`content` 等命令可启动组件 —— **可用性交 runtime-alt 实测**。

---

## 3. 串口设备与波特率（P0，事实）

| App | 类 | 设备 | 波特率 | 证据 |
|---|---|---|---|---|
| BlocklyC | `com.example.blocklyc.SerialProcess` | `/dev/ttyMT1` | **1,000,000** | `提取/disasm_com_example_blocklyc_SerialProcess.txt:190,120`（`initSerialPort(1000000)`，`new SerialPort(File("/dev/ttyMT1"), baud, 0)`） |
| Controller | `com.abilix.controller.api.serial.MasterSerial` | `/dev/ttyMT1` | **2,000,000** | `提取/scan_ctrl_tty.txt`（MasterSerial.<init>：`const-string "/dev/ttyMT1"`，`const v1, 2000000`） |
| Controller | `com.abilix.controller.api.serial.TransSerial` | `/dev/ttyMT0` | **1,000,000** | 同上（TransSerial.<init>：`/dev/ttyMT0`，`const v1, 1000000`） |

- 串口底层库：`org.winplus.serial.utils.SerialPort`（`libserial_port.so` / 名为 `libserial.so`）。ELF 仅 2 个 JNI 符号：`Java_org_winplus_serial_utils_SerialPort_open`、`_close`，字符串含 `Invalid baudrate`、`Opening serial port %s with flags 0x%x`、`tcgetattr/tcsetattr failed`、`java/io/FileDescriptor` → 【事实】通用开源串口库，**设备路径/波特率全部由 Java 侧传参**（证据：`提取/serial_so.txt` 由 `_extract.py`/strings 生成；`apk_BlocklyC/lib/*/libserial_port.so`）。
- 【事实】Controller 同时打开 **两路 UART**（MasterSerial→ttyMT1 主控 STM32；TransSerial→ttyMT0 转发）。BlocklyC 只开 ttyMT1。
- 附：BlocklyC 有 `/Download/Blockly/update/stm32.bin`（STM32 固件下载路径）与 `UpdateStm32/UpdateFirmware`；Controller 有 `assets/stm32/stm32.bin` 与 `Protocol$MasterUART.setUpdate(B)`。**stm32.bin 二进制本身不在本报告范围（task-5 stm32-re）。**

---

## 4. 串口协议（核心）

### 4.1 BlocklyC：40 字节固定帧（下行 MTK→STM32 = 0xAA55）

【事实】`SerialProcess.addProtocol(byte[])`（`提取/disasm_com_example_blocklyc_SerialProcess.txt:106-145`）：
```
总长 = payload_len + 5
[0]=0xAA [1]=0x55 [2]=len_hi [3]=len_lo  [4..4+payload-1]=payload  [末]=checksum
len = payload_len + 1（大端；含末字节校验位，即"除 2B 帧头外全部"）
checksum = sum(bytes[0..总长-2]) & 0xFF        ← 8 位累加和
```
【事实】`SerialProcess.sendProtocol()` 主循环发送的是**固定 40 字节帧**（`提取/disasm_com_example_blocklyc_SerialProcess.txt:489-721`）：

| 偏移 | 字段 | 来源 |
|---|---|---|
| 0 | `sHead1`=**0xAA** | `Protocol.sHead1`（`Protocol.<clinit>`：`const/16 -86`，`提取/disasm_com_example_blocklyc_Protocol.txt:295-298`）|
| 1 | `sHead2`=**0x55** | `const/16 85`（同上 :297-298）|
| 2 | `sCmd`（默认 **0xD1** = -47） | 同上 :299-300 |
| 3 | `sLen`=**40**（0x28） | 同上 :301-302 |
| 4 | M0 speed | `sM0` |
| 5 | M0S（模式/停止位） | 默认 **100**（=100，即 0 速偏移） |
| 6 | M0AL 编码器低字节 | |
| 7 | M0AH 编码器高字节 | |
| 8-11 | M1 / M1S / M1AL / M1AH | 4 个电机 |
| 12-15 | M2 / M2S / M2AL / M2AH | |
| 16-19 | M3 / M3S / M3AL / M3AH | |
| 20 | DO（数字输出位图） | `sDO` |
| 21 | LED（智能灯/板载灯） | `sLED` |
| 22-38 | DAT0..DAT16（17 字节通用命令数据） | `sDAT0..16` |
| 39 | checksum | `sCheck`=sum(bytes[0..38])&0xFF |

（依据：`sendProtocol` 逐字节 `aput` 序列，行 496-693；缺省值为 `Protocol.<clinit>` 行 152-338。）

### 4.2 BlocklyC：40 字节固定帧（上行 STM32→MTK = 0xBB66）

【事实】`SerialProcess.recvProtocol()`（`提取/disasm_com_example_blocklyc_SerialProcess.txt:209-465`）：读入 `recvBuff[90]`，校验：
- `recvBuff[0]==0xBB`(-69) 且 `recvBuff[1]==0x66`(102)；否则 `recv log "recv head error"`；
- 累加 `recvBuff[0..39-1]` 与 `recvBuff[39]` 比较（`getRecvCount()-1` 处为末字节）→ 【事实】上行同样是 **40 字节定长**帧，checksum 同算法。
- 字段映射（逐字节 `setrXXX`）：
```
[0]=0xBB [1]=0x66 [2]=Cmd [3]=Len
[4..11]  = AI0..AI7     （8 路模拟量/传感器通道值）
[12..19] = AII0..AII7   （8 路"模拟量 II"，颜色/灰度扩展）
[20..27] = ENC0L,ENC0H,ENC1L,ENC1H,ENC2L,ENC2H,ENC3L,ENC3H（4 路编码器，16 位小端）
[28..30] = ColorR,ColorG,ColorB
[31]     = Ver（固件版本）
[32]     = 保留/未使用（代码从 31 跳到 33）
[33..38] = DAT0..DAT5（6 字节回传数据）
[39]     = Check
```
- 读取 API 全部是**读缓存**：`Protocol.getAI0..7/rAI*/getENC*/getColor*/getBatt/getVer/getDAT*` 直接返回静态字段（`提取/disasm_com_example_blocklyc_Protocol.txt:1127-1326`）。

### 4.3 BlocklyC 主循环时序（P3）

【事实】`SerialProcess` 构造（`提取/…SerialProcess.txt:40-172`）：
- `sendBuff[40]`、`recvBuff[90]`；`nStep` 状态机从 1 开始；
- `SENDWAITTIME=1`、**`RECVWAITTIME=8`**、`ENCWAITTIME=10`、`PROWAITTIME=2000`、`BATTWAITTIME=3000`（单位 ms）；
- `run()`（行 1149-1256）：`nStep` packed-switch → `sendProtocol()`（写 40B）→ 记录时间 → 等待/`getRecvCount()=InputStream.available()` → `recvProtocol()` → 回到发送。
- 【推断】正常控制周期 ≈ 1ms 发送 + 串口往返 + 8ms 接收窗口 ≈ **10~20ms 量级（约 50~100Hz）**，编码器 10ms、电量 3s 分别有独立节流；所有传感器值（AI0..7/AII0..7/颜色/4 编码器）**每帧都刷新**，无需单独请求 → 【事实】`GetGray/GetUltraSonic/GetColor/getAI` 类 API 只是取缓存的最近一帧。

### 4.4 Controller：MasterUART 协议（P0，最新 SKCON9 侧）

【事实】`Protocol` 常量（`提取/disasm_C_com_abilix_controller_api_Protocol.txt:1-16`）：`HEADER_AA`、`HEADER_55`、`HEADER_BB`、`HEADER_66`、`AI_COUNT`、`GYRO_AXIS_COUNT`、`MOTOR_COUNT`、`MULTIGRAY_COUNT`、`SERVO_COUNT`。

**下行帧（MTK→STM32）32 字节**，`Protocol$MasterUART.initSendCmd()`/`getSendCmdBuffer()`（`提取/disasm_C_com_abilix_controller_api_Protocol$MasterUART.txt:275-307,360-480`）：

| 偏移 | 含义 | 证据 |
|---|---|---|
| 0 | **0xAA** | initSendCmd：`const/16 -86` |
| 1 | **0x55** | `const/16 85` |
| 2 | **序号 CMD_SEND**，每帧 +1，到 5 回 1（**1~4 循环**） | `getSendCmdOrder()` :309-321 |
| 3 | **0x20 = 32**（帧长） | initSendCmd :371-373 |
| 4..7 | 4 路电机速度，**= speed+100**（默认 100=停） | `setMotor()` :515-531；init :374-394 |
| 8,9 | 0（默认） | init :383-387 |
| 10..29 | **循环载荷**：`sendCmdTemp[CMD_SEND-1]`（4 个缓冲区轮换，每个 16B？按 arraycopy 长度） | `getSendCmdBuffer()` :275-307 |
| 30 | **update 标志** | `setUpdate(B)` :693-698 |
| 31 | **checksum = sum(bytes[0..30])&0xFF** | `getSendCmdBuffer()` :293-307 |

- 载荷 `sendCmdTemp[0..3]` 承载：**伺服** `setServo`（三元组 `[ID][90+角度][速度]`，ID 1~11，角度-90~90，速度0~100；证据 :549-617）、**智能灯** `setSmartLed`（:619-681，写 `sendCmdTemp[2]`：`[port][1][R][G][B][mode 0..3][周期低][周期高][100][100][100][100]`，周期 float 0..1024 折算 0..1024）、DO `setDO`（:482-513，位图写入发送帧字节）、以及 **TTL 原始字节** `setTTLCmd(byte[])`（:683-691，`arraycopy` 到 `sendCmdTemp[3]`）。
- 接收缓存读取（`extract` 中 `Protocol$MasterUART`）：
  - `getAIValue(int i)`：`recvCmd[4+i]<<4 | recvCmdTemp[3][10+i/2]`（高低半字节；i 1~12），`getAIType(i)`：`recvCmdTemp[1][i-1]`（:65-110）
  - `getBattery()`：`recvCmd[67]` clamp 0..100（:111-121）
  - `getFwVersion()`：`recvCmd[69]`（:151-157）
  - `getEncValue(enc)`：`recvCmd[40+(enc-1)]`（:136-149）
  - `getGyro(axis)`：`byte2int_2byte(recvCmd, 44+2*axis)`，axis 0~2；特殊轴用 `recvCmdTemp[0/1]`（:159-195）
  - `getServoAngle(id)`：从 `recvCmdTemp[2/3]` 取 16 位，`((v-512)*90)/307`（:323-351）
  - `getSendCmd/getRecvCmd(cmd,index)`：通用访问器，`index` 在 `10..28` 时访问 `sendCmdTemp[cmd][index-10]`，否则直接访问 `sendCmd[index]` / `recvCmd[index]`（:197-273）
  - `getTTLCmd()` 返回 `recvCmdTemp[0]`（上行 TTL 帧，17B）（:353-358）

**上行帧（STM32→MTK）72 字节**，`Protocol$MasterUART.updateRecvCmdBuffer(byte[])`（:700-754）：
```
if b[0]==0xBB && b[1]==0x66:
    if b[71] == sum(b[0..70])&0xFF:            ← 校验位在 [71]
        recvCmd = copy(b, 0, 72)
        if b[2] in 1..4:                        ← "临时帧"分流
            copy(b[50..66], recvCmdTemp[b[2]-1], 17)
            return true
```
- => 【事实】上行帧 **72 字节**，`[0]=0xBB [1]=0x66 [2]=命令/帧类型(1~4) [71]=checksum`；`b[50..66]` 是 17 字节"扩展载荷"（TTL/传感器扩展），`recvCmd[67]=电量`、`[69]=固件版本`、`[40..43]`编码器、`[44..49]`陀螺仪、`[4..]`AI、`[10..]` AI 半字节等。
- 【推断】Controller 每 2ms 级发一帧、轮换 4 组命令（servo/智能灯/DO/TTL 分组），STM32 回 72B 帧包含全部状态 → **采样率显著高于 BlocklyC（2M baud）**。

### 4.5 `setSendCmd/getSendCmd/getRecvCmd/getSendCmdBuffer/getRecvCmdBuffer` 到底是干什么（P1）

【事实】Controller：
- AIDL 接口 `Lcom/abilix/controller/api/IControllerApi;` 共 **34 个方法**（`提取/dexmethods_Ctrl6F_classes.txt`）：`setMotor/getAI/getAIType/getAIValue/getGray/addGrayChannel/removeGrayChannel/getGyro/resetGyro/getBattery/getFwVersion/getData/setData/setDO/getHIDValue/setHIDValue/getEncoder/getInstantEncoder/resetEncoder/getMotorSpeed/getMicDbValue/getServoAngle/setServo/setSmartLed/setMotorAdvanced/setMotorOverTurn/getSysTimer/resetSysTimer/**setSendCmd(I I B)/getSendCmd(I I)B/getSendCmdBuffer(I I I)[B/getRecvCmd(I I)B/getRecvCmdBuffer(I I I)[B**`。
- 实现链：`ProtocolService$1`（Binder）→ `ControllerApi$Controller` → `Protocol$MasterUART`（`提取/dexmethods_Ctrl6F_classes.txt` 中同名方法）。
- `CCJ_Interface(String)`（`提取/disasm_C_CCJ_Interface.txt`）是 C API 名字分发器：把 native（libRobot.so）传入的 `"setSendCmd;..."/"getRecvCmdBuffer;..."/"getAI;..."/"SetEE;..."/"SetDO;..."/"SetMotor;..."` 解析参数后调用 `IControllerApi` 对应方法（:934-993 为 Send/RecvCmd 分发；:796/:842 为 SetEE/GetEE case）。即 **Robot.h 的这批 C API = 对本 App 协议层"发送帧/接收帧"的读写接口**。
- 语义【事实+推断】：
  - `setSendCmd(cmd,index,value)`：向**下一帧**写 1 字节。`index=10..28` 写第 `cmd`(1~4) 组循环载荷；其它 index 写 `sendCmd[]` 主帧（含 0/1/2/3/29/30 等）。→ 可改变帧头/长度/update 标志/载荷（但 `[2]` 序号和 `[31]` 校验每帧被重算，`[4..7]` 会被 setMotor 覆盖）。
  - `getSendCmdBuffer(cmd,index,len)` / `getRecvCmdBuffer(...)`：批量读发送帧/接收帧缓存（`byte[]`）——**等价于"拿到最近一帧原始字节"**。
  - `getRecvCmd(cmd,index)`：读最近上行帧任意字节（另含 4 个扩展帧缓存 `recvCmdTemp[cmd]`）。
- 【推断】这不是"机间通讯/与 PC 通讯"专用 API，而是**给用户 C 程序开放的"原始帧读写口"**：配合 `Protocol$MasterUART.setTTLCmd(byte[])`（TTL 透传帧）与 `TransSerial(ttyMT0)`，构成**可发裸字节的多条通道**（详见 §6）。
- 附：`Robot.h:145-153` 原型为 `void setSendCmd(int cmd,int index,int value); int getSendCmd(int,int); char* getSendCmdBuffer(...); int getRecvCmd(int,int); char* getRecvCmdBuffer(...)`，与 Java 侧 `(I I B)/(I I B)/(I I I)[B` 完全对应（`int` 值的低 8 位进帧）。

### 4.6 固件升级 / STM32 更新（旁证）

- BlocklyC：`UpdateStm32()` 先 `Protocol.setsDAT14(0xA5)` + sleep(1000) + 清零（"发送固件升级请求"，行 87-104）；`UpdateFirmware()` 用 `sendProtocol(B B B [B Z)` 走 `addProtocol` 变长帧：payload = `[1][17][2/3/4][0,0,0,0][data...]`（行 767-1140，如请求发送文件=cmd 2、数据块=cmd 3，重试 5 次）。帧 = `AA 55 lenH lenL 01 11 sub 00 00 00 00 data... chk`。
- Controller：`Protocol$MasterUART.setUpdate(B)` 写下行帧 [30]；`assets/stm32/stm32.bin` 为固件。**stm32.bin 内容归 task-5。**

---

## 5. 用户程序执行路径（P4）

### 5.1 C 程序：机器人上本机 gcc 编译 → libuser.so → JNI 加载执行（【事实】）
- `com.abilix.utils.ProgramAndInterfaceC.<clinit>`（`提取/scan_ctrl_loadlib.txt:1-11`）：
  - `FILE_LIBUSER_SO = FileUtil.getFilePath(<dir>, "libuser.so")`
  - `System.loadLibrary("Robot")` → `libRobot.so`
  - `public native String JCC_Main(int, String)`、`JCC_Exit(int, String)`；`public native` 即 Robot.h 的 `Java_com_abilix_utils_ProgramAndInterfaceC_JCC_1Main/_Exit` 实现（Robot.h 在本 APK 的 `assets/program_c/Robot.h`，与任务给的文件一致）。
- `ProgramAndInterfaceC.startRunning(String cFile)`（`提取/disasm_C_com_abilix_utils_ProgramAndInterfaceC.txt:1517-1596`）：
  1. `mCFile = new File(cFile)`；不存在 → 返回 -2；
  2. `CompileUtil.getTargetLinkLibName(file)` → `librobot_<名字>.so`（`CompileUtil` :getTargetLinkLibName：前缀 `librobot_`，`.c`→`.so`）；
  3. 目标 .so 不存在 → `CompileUtil.compile(cFile)`；编译日志 `error.log` 存在 → `printText(log)` 返回 -1；
  4. 存在 → `FileUtil.copyFile(编译产物, FILE_LIBUSER_SO)` + `sleep(60)` + 启动 `ProgramMainThread`（线程内调 `JCC_Main`，`ProgramAndInterfaceC$ProgramMainThread.run`）。
- `CompileUtil.compile`（`提取/disasm_C_com_abilix_utils_CompileUtil.txt`）：
  - 拼接 shell 命令（`ShellUtil.execCommand(List, boolean, boolean)` = `Runtime.exec`/ProcessBuilder）：
    `export PATH=/system/xbin/gcc4.8.2/bin:$PATH`
    `cd <compileDir>`
    `cp -rf <源/依赖> .`（含 `Robot.h`、`libRobot.so` 等）
    `arm-linux-androideabi-gcc *.c -pie -fPIC -L. -lm -lRobot -shared -o librobot_xxx.so`
  - 【事实】机器人系统镜像自带 `/system/xbin/gcc4.8.2/bin` 交叉 gcc（Android 4.4/MTK6580 风格）。
- 【推断】所以"用户 C 程序"是**机器人本机编译成 .so 后当 native 库加载**，API 符号由 `libRobot.so` 提供（其内部再调 Java 的 `CCJ_Interface` 分发到协议层）。**libRobot.so 二进制细节归 task-5，本报告不展开。**

### 5.2 Python 程序：StarCore（srplab）+ libstarpy（【事实】）
- `com.abilix.utils.ProgramAndInterfacePython`（`提取/disasm_C_com_abilix_utils_ProgramAndInterfacePython.txt`）：`runPython(String)` → `PythonTask.start()`；接口与 C 版对称（printText/clearScreen/showImage/startCamera）。
- 模板字符串（`提取/dexstrings_Ctrl6F_classes.txt` 索引 00687）：
  ```
  #!/usr/bin/python3
  import threading
  import time
  import libstarpy
  robot = Robot()
  ```
- 运行时依赖字符串（同文件 01821-01852）：`/data/data/com.srplab.starcore/files`、`/data/data/com.srplab.starcore/lib/libstar_java.so`、`/sdcard/srplab/tmp`、`/system/lib/python`、`/system/lib/python/libpython3.4m.so`、`/system/lib/python/python3.4.zip`。
- 【推断】Python 执行依赖**另一个系统 App `com.srplab.starcore`（StarCore 运行时）+ 系统分区 Python 3.4**；`robot` 对象由 `com.abilix.controller.python.IRobot/PythonCallBack` + StarCore 绑定（`libstarpy`）。
- assets 生成器：`assets/abilix/python_generators.js`（4.8KB）把积木生成 `robot.set_motor(channel,speed)`、`robot.set_do(port,state)`、`robot.get_ai(channel)`、`time.sleep(ms/1000)`、`def main(): ... main()`（`apk_Controller6F/assets/abilix/python_generators.js`）；`assets/js/math.js`(1.74MB) 与 BlocklyC 同源（Chart 3.0 积木定义）。
- 【事实】`assets/abilix/{generators,javascript_generators,python_generators}.js` 均为积木代码生成器；未见"通信/发送/接收/数据"专类积木（`abilix_blocks.json`/`abilix_toolbox_basic.xml` 中无 comm 积木；`setSendCmd` 等未出现在 JS 生成器里，只出现在 native/C API 层）。

### 5.3 程序槽/文件路径（旁证）
【事实】Controller 字符串：`/Download/Blockly`、`/Download/Blockly/lib`、`/Download/Blockly/update/stm32.bin`、`/Download/Blockly/AIMode.txt`、`/mnt/sdcard/Blockly/`；BlocklyC 的 `Protocol.<clinit>` 定义 `programPath=<外部存储>/Download/Blockly`、`updatePath=.../update`、`updateFile=.../stm32.bin`、`libFile=.../lib/math.js`、`musicPath`、`tmpFile`、`aitxtFile`（`提取/disasm_com_example_blocklyc_Protocol.txt:159-286`）。
【推断】PC 端通过 adb 安装 APK/推送文件到 `/sdcard/Download/Blockly/`；`.c/.py` 程序文件与 `lib/`、`update/stm32.bin` 同目录管理；程序列表由 `ProgramActivity/ProgramAdapter/ProgramRepo/ProgramDB` 管理（Controller 有 Room/DB：`dao/ProgramDB`、`ProgramRepo`）。

---

## 6. 对"方向1/方向2"的直接结论

### 方向1（双板通讯/主从/UART 透传）
- 【事实】**存在第二路 UART `/dev/ttyMT0`@1M（TransSerial/TransUART）**：Controller 内部有独立的收发类与 `OnSerialListener`，与 STM32 主链路（ttyMT1）分离；`Protocol$TransUART` 存在但方法极少（9 行 dump，仅 `<init>` 级），实际转发逻辑可能在 native/服务层。
- 【事实】**可注入自定义字节的通道至少 3 条**：
  1. `setTTLCmd(byte[])` → 写入循环下行帧 `sendCmdTemp[3]`（每 4 帧发一次，载荷区 ~12/16B，帧头/校验自动生成）；
  2. `setSendCmd(cmd,index,value)`（Robot.h 同名 C API）→ 直接改写下行帧任意字节（10..28 → 4 组循环载荷；0..9/29/30 → 主帧字段）；
  3. `TransSerial(ttyMT0)` 裸串口（1M baud）。
  - 约束：**不能任意改帧头/校验**（头 AA55 固定语义、[31] 校验每帧重算、[2] 序号自动递增、[4..7] 电机值会被 setMotor 覆盖）；但**载荷区（10..29）内容不受限** → 若对端（第二块板/外设）能解析"AA55 + 序号 + 32 + 自定义 16B"帧，即可实现主从通讯；若要完全自定义协议，只能用 ttyMT0 或改 APK/替换串口。
- 【事实】`ProtocolService`（`:protocolservice` 独立进程）exported（见 §2.2），AIDL 暴露 `setMotor/getAI/setSendCmd/...` → 【推断】外部 App 可 bind 后**以 50~100Hz 级调用控制/读传感器**，但 adb shell 直接 bind 需辅助 App；【待实测】runtime-alt 验证。
- 【事实】TCP 10086/8890 + UDP 7777/9999 是机器人端**下载/控制服务**（ControllerService），PC 端 Chart 3.0 通过 WiFi 连接（下载链路细节见任务 2/3 报告，避免重复）。

### 方向2（传感器通讯/时序）
- 【事实】传感器值是**每帧广播**（上行帧 AI0..7、AII0..7、颜色 RGB、4×编码器、陀螺仪等），App 端 API 只是读缓存，**不存在"逐传感器发命令+阻塞等回包"**；因此"传感器协议时序"= 串口帧周期：
  - BlocklyC：1M baud / 40B 双向 + 8ms 接收窗 → 约 50~100Hz 上限，实测受 `sleep/available` 循环；
  - Controller：2M baud / 32B 下行 + 72B 上行 + 4 组轮换 → 单组刷新率 ≈ 帧率/4，全量传感器刷新约每 4 帧一次（≈ 数百 Hz 上限，实际受主循环/线程调度）。
- 【事实】`getAIValue` 精度：Controller 用 `recvCmd[4+i]<<4 | recvCmdTemp[3]` 半字节拼接 → 12 位值（0~4095），通道 1~12；BlocklyC 为 8 位/通道（AI0..7、AII0..7）。智能灯 `setSmartLed(port,mode,cycle,r,g,b)` 参数语义已解出（见 §4.4）。多通道灰度 `MULTIGRAY_COUNT`/`getGray/addGrayChannel`、巡线 `Walkline` 类均存在（`Lcom/abilix/controller/api/Walkline;`）。
- 【推断】对"双板传感器数据转发"：主板上行帧已含全部传感器，第二块板若作为**从机挂在 ttyMT0**，需要自行定义 ttyMT0 协议（APK 只做字节转发）；若从机挂 ttyMT1（与 STM32 同总线）则必须伪装成标准帧格式。

---

## 7. 已确认 / 未确认清单

**已确认（事实）**
- 3 个 APK 的 package/版本/debuggable/导出组件（§2）；BlocklyC `debuggable=false`；Controller 无 debuggable 属性（=false），ProtocolService/UVCService/MainActivity 隐式 exported。
- 串口设备/波特率：BlocklyC ttyMT1@1M；Controller MasterSerial ttyMT1@2M；TransSerial ttyMT0@1M。
- BlocklyC 40B 双向帧格式、头 AA55/BB66、len、8 位累加校验、全部字段映射、主循环 8ms 接收窗/2s/3s 节流、A5 固件升级请求。
- Controller MasterUART 32B 下行/72B 上行帧、序号 1~4 轮换、校验位置、字段映射（AI/电量/版本/编码器/陀螺仪/伺服角）、setTTLCmd/setSendCmd 语义。
- 用户 C 程序本机 gcc 编译→libuser.so→JCC_Main；用户 Python 程序经 StarCore/libstarpy + com.srplab.starcore + libpython3.4m.so。
- IControllerApi 34 方法全表；CCJ_Interface 为 Robot.h C API 的字符串分发器（含 send/recv cmd、SETEE/GETEE 等）。
- netty 端口 10086/8890(TCP)、7777/9999(UDP)。

**未确认（待后续）**
- STM32 侧对 32B 下行帧各字段/子命令的完整语义（需 stm32.bin 逆向，task-5）；EE 地址空间/命令字；`0xC8/0x1E` 初始化三元组含义。
- `Protocol$TransUART` 的完整实现（dump 仅 9 行，逻辑疑在 native/服务层）；ttyMT0 是否默认打开、由谁使用。
- Controller 的 72B 上行 `[2]` 主帧命令值全表（当前只知 1~4 为扩展帧分流）。
- 6E vs 6F 对应机型（SKCON9？）——manifest 无差异，需机型配置/运行日志。
- adb shell 能否直接 bind ProtocolService / 启动非 exported Activity（交 runtime-alt 实测）。
- BlocklyC 的命令字节全表（`sCmd` 默认 0xD1；Activity 侧的命令设置点分散在 WebView/JS 回调与 `Protocol` setter，未逐一枚举）。

---

## 8. 证据文件索引（相对 `_分析临时/apk分析/`）

| 文件 | 内容 |
|---|---|
| `_extract.py`、`filelist.txt` | BlocklyC 解包脚本 + 143 文件清单 |
| `extract_apks.py`、`提取/filelist_*.txt`、`提取/manifest_*.xml` | 3 APK 解包 + 二进制 AXML → 文本 manifest |
| `dex_dump.py`、`提取/dex_strings.txt`、`dex_methods.txt`、`dex_classes.txt` | BlocklyC DEX 导出（9319 strings/7774 methods/769 classes） |
| `dump_dex.py`、`提取/dexstrings_Ctrl6F_classes*.txt`、`dexmethods_*.txt`、`dexclassnames_*.txt` | Controller 两个 dex 导出（55109+4570 strings） |
| `dex_disasm.py`、`disasm_dex.py`、`scan_calls.py` | 反汇编/调用点扫描脚本 |
| `提取/disasm_com_example_blocklyc_SerialProcess.txt` | **BlocklyC 串口协议全文（addProtocol/sendProtocol/recvProtocol/run/UpdateFirmware）** |
| `提取/disasm_com_example_blocklyc_Protocol.txt` | **BlocklyC 协议常量/字段默认值/getter** |
| `提取/disasm_com_example_blocklyc_Robot.txt`、`MyTools` | BlocklyC Java Robot API（setMotor/getEE/setEE/setDO…） |
| `提取/disasm_C_com_abilix_controller_api_Protocol$MasterUART.txt` | **Controller 32B/72B 帧、checksum、setMotor/setServo/setSmartLed/setTTLCmd/getAI…** |
| `提取/disasm_C_com_abilix_utils_ProgramAndInterfaceC.txt`、`disasm_C_CCJ_Interface.txt` | C 程序 JNI 桥、startRunning、C API 分发 |
| `提取/disasm_C_com_abilix_utils_ProgramAndInterfacePython.txt` | Python 运行入口 |
| `提取/disasm_C_com_abilix_utils_CompileUtil.txt` | **本机 gcc 编译命令** |
| `提取/disasm_C_com_abilix_controller_socket_netty_TCPNettyServer.txt`、`scan_ctrl_server_ctor.txt` | netty 端口（10086/8890/7777/9999） |
| `提取/scan_ctrl_tty.txt`、`scan_ctrl_loadlib.txt`、`scan_blocklyc_cmd.txt`、`scan_ctrl_starcore.txt` | 调用点扫描（串口/loadLibrary/命令分发/StarCore） |
| `apk_Controller6F/assets/abilix/python_generators.js`、`assets/program_c/Robot.h`、`assets/program_c/libRobot.so` | Python 生成器、C API 头、C 运行库（二进制归 task-5） |

**复现**：`python extract_apks.py && python dump_dex.py Ctrl6F apk_Controller6F/classes.dex apk_Controller6F/classes2.dex && python disasm_dex.py apk_Controller6F/classes.dex C 'Lcom/abilix/controller/api/Protocol$MasterUART;'`（需 `pip install androguard`；PowerShell 下设 `$env:PYTHONIOENCODING='utf-8'`）。
