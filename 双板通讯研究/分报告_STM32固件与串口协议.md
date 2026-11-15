# 分报告：STM32 固件与 MTK↔STM32 串口协议（二进制逆向）

> 负责人：stm32-re（task-5）｜状态：**P0 基本确认，P1 部分确认，P2 结论可给**｜
> 素材：`_分析临时/brainApk分析/6F/`（libRobot.so、stm32.bin、libserial.so）＋ 从 `Controller_43.apk` 的 `classes.dex` 提取的 Java 实现（只读解析，未反编译 APK 资源）。
> 脚本与原始转储：`_分析临时/stm32分析/`（01~12，见文末"证据文件索引"）。
> 证据标记：【事实】=反汇编/字节码直接可见；【推断】=多证据合理外推；【待实测】=需真机验证。

---

## 结论卡片（给 Lead / 主报告直接引用）

1. **【事实】libRobot.so 根本不碰串口。** 它把每个 C API 变成 ASCII 字符串（如 `SetMotor&1&80`、`GetEE&5`）经 JNI 调 Java 方法 `ProgramAndInterfaceC.CCJ_Interface(String):String`，由 Java 层完成全部串口与协议。**真正的 MTK↔STM32 协议不在 .so 里，而在 APK 的 classes.dex**（`com.abilix.controller.api.Protocol$MasterUART`、`conn.Datagram`、`api.serial.MasterSerial`）。证据：`CCJ_Interface @libRobot.so:0x2550`；`.rodata` 常量 `CCJ_Interface`(0x64e5)、签名 `(Ljava/lang/String;)Ljava/lang/String;`(0x64f3)、格式串 `%s&%d&%d`(0x6573)；`SetMotor@0x29b9`、`SetEE@0x2e99`、`GetEE@0x2f18` 反汇编。
2. **【事实】两条串口，物理分开：**
   - MTK↔STM32 主链路：**`/dev/ttyMT1`，2,000,000 bps**（`MasterSerial.<init>(Handler)` 常量：`File("/dev/ttyMT1")`、baud `2000000`；对应字段 `Protocol$MasterUART.BAUD_RATE_2000000`）。
   - PC 下装/透传链路：**`/dev/ttyMT0`，1,000,000 bps**（`TransSerial.<init>(OnSerialListener)`：`File("/dev/ttyMT0")`、baud `1000000`；字段 `Protocol$TransUART.BAUD_RATE_1000000`）。它收发 PC 下装握手/zip 文件（`recvProtocol()` 里 `CMD_HEAD,CMD_HEAD,ping_ID` 三字节握手→"进入PC下载"→`processFile` 落盘 `tmp.zip`→`FileUtil.handleProgramZip`）。
   - 【推断】这两条是**主板内部两颗芯片之间的固定链路**（MTK 的 UART1/UART0），不是用户程序可重映射的 12 个 I/O 口。
3. **【事实】下行帧（MTK→STM32）固定 32 字节，上行帧（STM32→MTK）固定 72 字节，均字节和校验：**
   ```
   下行 32B：AA 55 | 序号/槽位(1..4) | 0x20(32) | 电机[4..7] | DO位图[8..9] | 槽载荷[10..29] | [30]升级/更新字节 | [31]=SUM([0..30])&0xFF
   上行 72B：BB 66 | 槽位(1..4)     | 0x44(68) | AI原始值[4..15] 编码器[40..43] 陀螺[44..49] | 槽载荷[50..66] | [67]电量 | [69]固件版本 | [71]=SUM([0..70])&0xFF
   ```
   证据（Java 侧）：`Protocol$MasterUART.initSendCmd`（写 AA 55 01 20、电机初值 100、槽初始化）、`getSendCmdBuffer`（`sendCmd[2]=order`、槽载荷拷到 `[10]`、`[31]` 存和校验）、`updateRecvCmdBuffer`（校验 `buf[0]==0xBB && buf[1]==0x66`、`buf[71]==getCheckSum(buf,0,71)`、`byte[2]∈1..4 → recvCmdTemp[byte2-1]=buf[50..66]`）；STM32 侧：`0x080051F8` 函数校验 `buf[0]==0xAA && buf[1]==0x55`，按 `buf[2]` switch 到 4 组处理，在 `buf+0x64` 回填 `BB 66 | id | 0x44`，即上行 72B 帧。另有**变长 Datagram**（PC/固件升级用）：`AA 55 LEN(HL) type cmd1 cmd2 reserved[3] seq data... chk`，校验同为字节和；命令字常量名见 `Datagram` 类：`CMD1_CONN_*/PROGRAM_*/SERIAL_*/TRANS_*`、`CMD2_CONN_IN_00…0B/60/61`、`CMD2_TRANS_IN_01…09` 等。
4. **【事实】轮询式主从：** MTK 每 ≥1.5ms 发一帧命令（`MasterSerial.process` 中 `sendProtocol()`：取 `MasterUART.getSendCmdBuffer()` 直接 write），槽位 1→4 轮转；STM32 每收一帧回一帧（72B，含该槽的传感器/状态数据）。**不是事件/中断驱动的双向数据流**，也不存在通用的"任意字节收发"通道。
5. **【事实→推断】EEPROM 极可能落在 STM32 内部 FLASH（EE 仿真），不是 MTK 本地文件。** 证据链：C `SetEE/GetEE` → Java 方法码 13/14（`CCJ_Interface` 字符串分派表）→ `ControllerApi.getData/setData` → AIDL `IControllerInterface` → 服务进程；STM32 固件含完整内部 FLASH 擦写例程：解锁键 `0x45670123/0xCDEF89AB`（字面量 @`0x08005D34/0x08005D3C`，写入 `FLASH_R+0x04 KEYR` @`0x08005D28`）、页擦除（`CR|=2; AR=页地址; CR|=0x40` @`0x08005C64`）、半字编程（`CR|=1; strh` @`0x08005CD8`）；且代码引用 **0x0801F108 / 0x0801F1A0** 两个高地址字面量（@`0x08004594`、`0x0800805C`），指向镜像之外的 FLASH 尾部 **0x0801F000 附近**——典型 EE 仿真页。【推断】EE 区 ≈ 0x0801F000 起的最后数页；"128 槽"若按 4KB/128=32B/槽吻合，但**槽数/命令字未解**。【待实测】真机改 EE 前后 dump STM32 flash 0x0801F000 段对比。
6. **【事实】方向 2（用可收可发传感器在两板间传数据）在固件层没有"端口自定义串口"能力。** 协议是固定槽位轮询 + 固定语义（电机/DO/AI/编码器/舵机/智能灯/TTL）。用户 C API 中唯一接近"发自定义字节"的是 `setSendCmd(port,idx,val)` / `setTTLCmd(bytes)`：前者只把 val 写进**某一槽 19 字节载荷的固定偏移**（`sendCmdTemp[slot][idx-10]`，`idx∈[10,28]`），后者把字节数组拷进**槽 4 载荷（`sendCmdTemp[3]`）**；STM32 对槽 4 走固定处理分支，未见"把这些字节原样转发到某个 I/O 口 UART"的代码（4 个 case 处理函数：`0x08007958/0x080077A4/0x08007EA4/0x08007CE8` 等，均为内部外设处理）。→ **方向 2"任意字节互传"：否（固件不支持），除非绕过固件从端口引脚电气层做（另见主报告）。**
7. **【事实】方向 1（A 板读写 B 板 EEPROM）在固件层没有"对外暴露的 EE 总线"**：EE 在各自 STM32 内部 FLASH，只能由本板 MTK 经 `SetEE/GetEE` 命令访问；端口上没有 I²C/单总线 EE 协议窗口（STM32 固件**未引用 I2C1/I2C2 外设地址、未引用 ADC1**）。→ **方向 1"通过端口直接读改 B 板地址"：否。**
8. **【推断】端口电气：** STM32F103 3.3V IO，12 路端口由 STM32 GPIO 直驱/采样（固件引用 GPIOA/B/C/D/E），**5V 容忍需查原理图**；两板端口对接时大概率是"输出 vs 输出"或"输出 vs 输入"的直连冲突风险，**不是 UART 电平**。传感器类型由 STM32 采集后放进上行帧 `recvCmdTemp[1]`（AI 类型 1..12 对应 12 口），MTK 只做查表→`AI_TYPE_*`。类型识别失败时 MTK 侧 `AI_TYPE_UNKNOWN=0`、读值返回 0（`getAIType` 取 0，`getAIValue` clamp 后判 0）——【事实】`Protocol$MasterUART.getAIType/getAIValue` 反编译；【待实测】UNKNOWN 时端口电平行为。
9. **【重要修正】stm32.bin 的加载基址不是 0x08000000，而是 0x08004000。** 向量表复位向量 `0x08004145` 对应文件偏移 0x144，此处正是 `ldr r0,[pc]; blx r0`（SystemInit）+`ldr r0,[pc]; bx r0`（跳 main）的标准启动桩；若按 0x08000000 解释会有多个向量落在文件外。说明该 bin 是**APP 镜像（0x08004000 起，24,172B → 至 0x08009E6C）**，0x08000000-0x08004000 为 STM32 自带 bootloader（不在 bin 内），OTA 时由 bootloader 写入。后续所有地址按 0x08004000 基址。
10. **【给主报告的判定】** 用户程序（C/Python）**没有任何路径**把 12 个 I/O 口变成自由收发串口；两板端口直连不能互通任意字节；能做的只有：①同一根线让两板某口做 DO/AI（电平/模拟量）级别"约定信号"；②用传感器自身发射（超声 ping、红外/颜色 LED）做单向调制（需实测响应速度/时序）；③EE 只在本板内。

---

## 一、P0：MTK 侧（libRobot.so + APK dex）

### 1.1 libRobot.so 不是协议实现，是 JNI 字符串 RPC【事实】

- ELF：ARM 32bit ET_DYN，**未 strip**（.symtab 513 项 + 完整 .debug_*），文本 0x2514-0x6074，.rodata 0x64c0，.data 0x8000。
- `CCJ_Interface @0x2550`（Thumb）反汇编骨架：
  `g_AbilixJVM->AttachCurrentThread → GetObjectClass(g_AbilixJobject) → GetMethodID(cls, "CCJ_Interface", "(Ljava/lang/String;)Ljava/lang/String;") → NewStringUTF(参数串) → CallObjectMethod → GetStringUTFChars → 结果写回调用者缓冲`。
- 所有 C API 都是同一模板：`sprintf(buf, "<API名>&%d&%d...", 参数...)` → `CCJ_Interface`。
  例：`SetMotor@0x29B9`：`sprintf(sp+0x90, "%s&%d&%d", "SetMotor", port, speed)`；`SetEE@0x2E99`：`"%s&%d&%d"`（addr, value）；`GetEE@0x2F18`：`"%s&%d"`（addr）；`getSendCmdBuffer@0x3AAD`：`"%s&%d&%d&%d"`；`getRecvCmd@0x3B88` 返回值走 `atoi`。
- 因此：P0 的"帧格式/命令字/回包"必须去 Java 层（classes.dex）找；libRobot 只保留**API 名与参数顺序表**（.rodata 0x64c0-0x694E 全部为 `%s&...` 格式串 + API 名，可依此还原 C API ↔ Java 参数映射）。
- 旁证：`libRobot.so` 导入 `dlopen/dlsym` 但 .rodata 无任何 `.so` 路径字符串；`libserial.so` 单独提供 JNI 串口 open/read/write/close（Java `com.abilix.utils.SerialPort` 用）。

### 1.2 串口参数【事实】（classes.dex 字节码）

- `com/abilix/controller/api/serial/MasterSerial.<init>(Landroid/os/Handler;)V`：
  `new File("/dev/ttyMT1")` → `BaseSerial.<init>(File, 2000000, 0)` → `startProcess()`。
- `com/abilix/controller/api/serial/TransSerial.<init>(OnSerialListener)`：
  `new File("/dev/ttyMT0")` → `BaseSerial.<init>(File, 1000000, 0)` → `startProcess()`。
- 对照字符串表：`/dev/ttyMT0`、`/dev/ttyMT1`、`SerialPort(%s, %d, %d)`（JNI），`libserial.so` 提供 `open/close/read/write`。
- 【推断】第三个参数 0 = flags/dataBits？libserial 的 JNI `open(String,int,int)` 通常 (baudrate, flags)；即 8N1 无流控，待实测确认。

### 1.3 主链路帧格式（MTK↔STM32 32B/72B）【事实】

下行（MTK→STM32，写 `sendCmd`，32 字节）：

| 偏移 | 长度 | 含义 | 证据 |
|---|---|---|---|
| 0..1 | 2 | 固定 `AA 55` | `initSendCmd`：conST 0xAA/-86、0x55/85 |
| 2 | 1 | 槽位/序号 1..4（`getSendCmdOrder` 循环 +1，到 5 归 1） | `getSendCmdOrder`、`getSendCmdBuffer` |
| 3 | 1 | 固定 `0x20`（32，整帧长） | `initSendCmd` |
| 4..7 | 4 | 电机 1..4 速度 +100（100=停） | `setMotor`：`sendCmd[(port+4-1)]`；`initSendCmd` 全 100 |
| 8..9 | 2 | DO 位图（口 1-8、9-12） | `setDO`：`sendCmd[8]`/`sendCmd[9]` 置/清位 |
| 10..28 | 19 | 当前槽载荷（见 1.4） | `getSendCmdBuffer` 把 `sendCmdTemp[order-1]` 拷到 `[10]` |
| 29 | 1 | 保留（initSendCmd=0） | `initSendCmd` |
| 30 | 1 | 升级/更新模式字节 | `setUpdate(b)`→`sendCmd[30]` |
| 31 | 1 | 校验 = `SUM(sendCmd[0..30]) & 0xFF` | `getSendCmdBuffer` 循环求和 |

上行（STM32→MTK，读 `recvCmd`，72 字节；固定长，字段由 getter 反推）：

| 偏移 | 含义 | 证据 |
|---|---|---|
| 0..1 | `BB 66` | `updateRecvCmdBuffer` 强校验 (-69/102) |
| 2 | 槽位 1..4 → 该帧属于哪个槽 | 同上：复制到 `recvCmdTemp[id-1]` |
| 3 | 固定 68（=0x44，与 STM32 侧吻合） | STM32 `0x0800521A`：`strb r2(=0x44)` |
| 4..15 | AI 原始值（12 口，每口 1 字节高半字节） | `getAIValue`：`recvCmd[port-1+4]<<4` |
| 26,29,32,35… | 编码器 3 字节/口（ControllerApi.getEncoder 走 `getRecvCmdBuffer(0, 26+3*(port-1), 3)`） | `ControllerApi.getEncoder` |
| 40..43 | 4 路编码器/AD 值（`byte-127`） | `getEncValue`：`recvCmd[(port-1)+40]-127` |
| 44..49 | 陀螺 2 字节大端（轴 1..2 在 recvCmd，3..5 在 temp） | `getGyro` |
| 50..66 | 槽载荷 17 字节（按槽位复制到 `recvCmdTemp[id-1]`） | `updateRecvCmdBuffer` |
| 67 | 电量 0..100 | `getBattery` |
| 69 | 固件版本 | `getFwVersion` |
| 70 | 保留/未知 | — |
| 71 | 校验 = `SUM(recvCmd[0..70]) & 0xFF` | `updateRecvCmdBuffer` |

【事实】STM32 侧同一协议：`0x080051F8` 函数先 `cmp buf[0],#0xAA`、`cmp buf[1],#0x55`，不符返回 0；随后在 `buf+0x64` 写 `BB 66`、`buf[2]`（槽位）、`0x44`，再按槽位 `1/2/3/4` 分派到不同处理函数组，并把结果填回 `buf+0x64+…`；校验在 MTK 端 `updateRecvCmdBuffer` 用 71 字节求和比对。

### 1.4 槽载荷（19B/17B）语义【事实/推断】

- `sendCmdTemp` = 4 槽 × 19B；`recvCmdTemp` = 4 槽 × 17B；`getSendCmd(port,idx)`：`idx∈[10,28]` 读 `sendCmdTemp[port][idx-10]`，否则读 `sendCmd[idx]`；`getRecvCmd` 同理 `[50,66]→recvCmdTemp[port][idx-50]`。
- 槽初始化（`initSendCmd`）：
  - 槽1（temp[0]）：偏移 4..12 为**舵机 1..3**（每舵机 3B：id, 角度+90, 速度=30）；`setServo(port≤3)` 写这里。
  - 槽2（temp[1]）：舵机 4..7（`(port-1-3)*3`）。
  - 槽3（temp[2]）：舵机 8..11（`(port-7-1)*3`）；`[18]=0`。
  - 槽4（temp[3]）：**SmartLed / TTL 指令**：`setSmartLed` 写 `temp[3][0]=port,[1]=1,[2..4]=参数,[5]=模式0..3,[6..7]=亮度(2B),[8..11]=100`；`setTTLCmd(byte[])` 直接 `arraycopy` 到 `temp[3]`（覆盖）。**这是用户程序能注入任意字节的唯一入口。**
- 上行槽 1 = **AI 类型表**（`getAIType(port)`：`recvCmdTemp[1][port-1]`，port 1..12 clamp）；槽 3 = **AI 值低半字节**（`getAIValue`：`recvCmd[4+port-1]<<4 + (recvCmdTemp[3][10+port/2] 的高/低 nibble)`）→ 即 AI 值 = 8bit 高段（帧4..15）+4bit 低段（槽3），共 12bit；槽 2 = 舵机角度等。

### 1.5 变长 Datagram（升级/下装用）【事实】

`com/abilix/controller/conn/Datagram`：
- `build(B type, B cmd1, B cmd2, [B data)` → `AA 55 | LEN(HL, = data+8) | type | cmd1 | cmd2 | 00 00 00 | seq=0 | data | chk`，`chk = SUM(bytes[0..len-2]) & 0xFF`。
- 解析：`header[0..1]`、`contentLength=HL@2`、`type@4`、`cmd1@5`、`cmd2@6`、`reserved=[7..9]`、`seq@10`、`data=[11..len-2]`、`checksum=last`。
- 命令字常量名（值被内联，名即值域）：`CMD1_CONN_IN_00/CONN_OUT_A0/PROGRAM_IN_0A/PROGRAM_OUT_A0/SERIAL_IN_B0/SERIAL_OUT_B0/TRANS_IN_01/TRANS_OUT_A0`；`CMD2_CONN_IN_00..0B/60/61`、`CMD2_CONN_OUT_00..0A/FF`、`CMD2_PROGRAM_IN/OUT_01/02`、`CMD2_SERIAL_IN/OUT_01/02`、`CMD2_TRANS_IN/OUT_01..09`。
- `MasterSerial.sendProtocol(B B B [B Z)` = 组 Datagram + `sendBuff(frame, needReply)`（写后等回包，超时 500/3000ms）；`addProtocol([B)` 是 32B 帧的 `AA55+LEN16+…+CHK` 简化包装（**注意：源码中 addProtocol 生成的 LEN 字段=data.length+1，与 Datagram 不同，且用于 32B 控制帧组装路径**）。
- 用途：`UpdateFirmware/UpdateStm32`（stm32.bin OTA）、`TransSerial.PCDownload`（PC 程序下装、zip 落盘）。**不是用户 API。**

### 1.6 C API → 帧行为映射（P0 必答 2）【事实（Java 反推）】

| C API（Robot.h） | 数据落点/来源 | 说明 |
|---|---|---|
| SetMotor(port,-100..100) | 下行 `sendCmd[3+port]`（+100） | 每帧必带，1..4 口 |
| SetMotorTime/Encoder/OverTurn/Advanced | 由 Java `ControllerApi` 计算后写同字段 + 槽载荷 | 上层封装 |
| SetServo(port,angle,speed) | 下行槽 1/2/3 的 3B 组 | port 1..11 |
| SetDO(port,0/1) | 下行 `sendCmd[8]/[9]` 位 | 1..12 口 |
| SmartLed(port,…) | 下行槽 4 `temp[3]` | RGB/亮度/模式 |
| SetEE(addr,val)/GetEE(addr) | 见 §1.7 | Java 分派码 13/14 |
| GetAI/GetGray/GetColor/GetUltraSonic/GetInfrared/GetLight/GetTemperature/GetHumidity/GetMagnet/GetAngle/GetTouch/GetFlame | 读上行槽 1 类型 + `recvCmd[4..15]`/槽3 值 | 12 口轮询数据 |
| GetEncoder/GetInstantEncoder | 上行 `recvCmd[40..43]` 或 `ControllerApi.getRecvCmdBuffer(0,26+3*(p-1),3)` | 两种视图并存 |
| GetBattery / GetFwVersion | 上行 [67]/[69] | |
| setSendCmd(port,idx,val) | 下行槽(port) 载荷 `[idx-10]`，idx 10..28；否则 `sendCmd[idx]` | 原始字节注入 |
| getSendCmd / getSendCmdBuffer / getRecvCmd / getRecvCmdBuffer | 直接读写上述字节缓冲 | 原始字节读出 |
| setTTLCmd(bytes)/getTTLCmd() | 槽 4 载荷（19B 中直接覆盖） | "送指令"入口 |

【事实】Java 侧 `ProgramAndInterfaceC.CCJ_Interface` 是一个巨大 `if("API名".equals(cmd)) 编号` + switch 分派表；`SetEE=13, GetEE=14, setSendCmd=17, GetAI=24, SetDO=7...`（`12_ccj_interface.txt` 中逐条可见）。

### 1.7 EEPROM 实现链（P0 必答 3）【事实链 + 推断终点】

1. C `SetEE/GetEE` → 字符串 `"SetEE&addr&val"` / `"GetEE&addr"` → Java `CCJ_Interface` 编号 13/14。
2. 编号 13/14 分派到 `ControllerApi.setData(I,I)/getData(I)` → `ControllerApi$Controller.setData/getData` → AIDL `IControllerInterface`（`ProtocolService$1 extends IControllerInterface$Stub`）→ 服务端 `Protocol`/`MasterUART`。
3. STM32 固件具备内部 FLASH 读写：解锁 `KEYR`、页擦除、半字编程（§0.5 地址）；引用 FLASH 尾部地址 0x0801F108/0x0801F1A0。
4. 【推断】EE = STM32 内部 FLASH 尾部页（~0x0801F000 起），128 槽 × 32B 的假设与 4KB 页容量吻合；**具体 EE 命令字（哪个槽位/哪几个字节承载 addr/val）未解**——需在 `Protocol$MasterUART` 之外定位 `setData/getData` 的实现类（AIDL 服务端），或真机抓 ttyMT1 波形。
5. 【事实否定项】libRobot.so 无任何 `fopen/open` 文件路径字符串（.rodata 仅格式串），故 EE 不是 C 层本地文件；Java 层未见 SharedPreferences 证据（未测）。

---

## 二、P1：STM32 侧（stm32.bin，基址 0x08004000）

### 2.1 镜像与向量表【事实】

- 首字 `0x20004020`（栈顶 SRAM），复位 `0x08004145`（Thumb），**基址 0x08004000**（见结论 9）。镜像范围 0x08004000-0x08009E6C（24,172B），0x08000000-0x08004000 为 bootloader 区（不在 bin 中）。
- 中断向量：`0x0800415F` = 默认死循环（未用 IRQ），`0x08004D4D`、`0x0800593D`、`0x08006025` 等为实际 ISR；SysTick=0x08008125。
- 复位桩：`0x08004144: ldr r0,=SystemInit; blx r0; ldr r0,=main; bx r0`。

### 2.2 外设证据【事实（字面量引用）】

- USART2 `0x40004400`：@`0x08005634`、`0x080062B4`、`0x080072E8`、`0x0800888C`；`0x080055E0` 处 `ldrh r0,[USART2]`（读 SR）。
- USART1 `0x40013800`：@`0x08006460`、`0x080089CC`、`0x08008A14`、`0x08008B74`。
- USART3 `0x40004800`：@`0x08006630`、`0x080076C4`。
- UART4/5：**未引用** → 【推断】只有 3 路 USART。
- DMA1 `0x40020000`：`0x0800566C`…`0x0800573E` 一组（含发送帧 DMA：`0x08006136` 附近先构造 `AA/55` 到 DMA 缓冲→启动通道）。
- GPIOA `0x40010800`、GPIOB `0x40010C00`、GPIOC `0x40011000`、GPIOD `0x40011400`、GPIOE `0x40011800`；AFIO `0x40010000` @`0x08005F60`。
- RCC `0x40021000` @`0x08005FAC`（时钟/PLL 配置）。
- FLASH `0x40022000`：ACR/KEYR/CR/AR 操作 @`0x08005C58`、`0x08005CD8`、`0x08005D28`。
- **未见 ADC1 `0x40012400`、I2C1/2、SPI1、TIM2/3/4 的基址引用**（0x40012300 ADC 公共区也未现）→ 【推断】12 路 AI 不是 STM32 内部 ADC 采样，而是数字/定时协议由 GPIO 位操作；或该功能在另一个 MCU/被裁掉（待查端口处理函数 0x080077A4/0x08007958/0x08007CE8/0x08007EA4）。

### 2.3 帧解析/回包主流程【事实】

`0x080051F8`（被主循环调用）：
```
r0 = RX 缓冲 (RAM)
if buf[0]!=0xAA return 0; if buf[1]!=0x55 return 0;
tx = buf + 0x64            ; TX 缓冲 = RX+100
tx[0]=0xBB; tx[1]=0x66; tx[2]=buf[2]; tx[3]=0x44;
switch(buf[2]):
 1: handle(0x08007958,0x080077A4,0x08007EA4,0x08007CE8)
 2: handle(0x08007958,0x08007834,0x08007EA4,0x08007D74)
 3: handle(0x08007958,0x080078A8,0x08007EA4,0x08007DE0)
 4: ...（0x08005282 起，本次未展开）
计算某值 → tx[0x47]；写入若干全局状态
```
- 【事实】下行 32B / 上行 72B、按槽位 1..4 分派，与 MTK 侧完全一致。
- 4 个槽位分支对应：电机/DO 类、舵机类、AI/编码器采样类、SmartLed/TTL 类（对应关系为【推断】，需逐函数展开命名）。

### 2.4 端口模式 / 传感器识别【部分】

- 12 路端口 GPIO 由 STM32 直接驱动/读取（GPIOA-E 均被引用）；类型识别结果由 STM32 填上行槽 1（`recvCmdTemp[1][0..11]` = 12 口 AI 类型字节），MTK 只做映射到 `AI_TYPE_*`。
- 【未解】具体"上拉/下拉/ADC 分压/单总线 ID"探测算法：本镜像未发现 ADC/I2C 外设引用，故最可能是 GPIO 上拉+外部传感器单总线/脉冲协议；下一步：展开 0x08007200-0x08007F00 区（槽位处理函数集中区）反汇编，找 `GPIOx_CRL/CRH` 模式切换序列与输入捕获。
- 【事实】`Sensor$AiType`、`Protocol.AI_COUNT/MOTOR_COUNT=4/SERVO_COUNT=11/MULTIGRAY_COUNT/GYRO_AXIS_COUNT` 字段名存在；`Protocol$MasterUART` 亦有 `*_IN_ENC/GYRO/SERVO` 长度常量（值内联）。
- 【事实】`AI_TYPE_*` 在 libRobot.so 中是 `.data` 全局变量（地址 0x080008-0x080034，`AI_TYPE_UNKNOWN` 在 .bss 0x080044），**具体数值本次未取到**（.data 需按 R_ARM_RELATIVE 重定位+初始化路径解读，建议下一步用 `readelf -x .data`+构造函数 0x2551 前的 `$a/$d` 段解析）。

### 2.5 有无"裸 UART 透传/端口通讯/主从"【事实+推断】

- **没有**面向 12 个 I/O 口的"串口透传"命令：帧格式固定槽位、固定语义；STM32 侧 4 槽分支均为内部处理，未见把载荷字节写入 USART1/3 或切 GPIO 为 UART 的代码片段（已扫描 frame 解析函数与 4 个 case 入口附近）。
- 存在**板内**的 PC 透传链路：MTK `TransSerial`("/dev/ttyMT0"@1M) ↔ PC 下装；STM32 的 USART1/3 之一可能用于外设（如蓝牙/USB 桥），**未确认与端口相连**。
- 【推断】"第二块控制器识别"：协议中槽位/`id` 只有 1..4（子帧号），无第二个控制器地址/ID 字段 → 双主控在同一 UART 上不成立。

### 2.6 EEPROM 位置

见 §1.7：**STM32 内部 FLASH 尾部（~0x0801F000），不是 MTK 本地文件**【推断，证据为 FLASH 擦写例程+高地址字面量】。EE 的命令字/槽数未解。

---

## 三、P2 结论（可直接引用）

1. **用户程序能否把端口变成自由收发串口？否。【事实+推断】** C/Python API 无端口 UART/I²C 配置函数（Robot.h 无此类接口；协议帧无端口模式命令）；`setSendCmd/setTTLCmd` 仅向固定槽载荷注入 ≤19B，STM32 固件无"转发到端口"分支。
2. **两板端口直连时各针脚电气角色【推断，待实测】**：由 STM32F103 3.3V GPIO 直接驱动——DO 为推挽输出（0/3.3V，可能经驱动管到 5V/电池电压，需原理图），DI/AI 为输入（上拉/浮空待测），电源针脚为电池电压（SKCON9 常见 7.4V 锂电，经稳压 5V/3.3V）。**不是 UART 电平，直连两边同时输出有对驱风险。**
3. **端口自动识别失败【推断】**：STM32 填 AI 类型=0/未知 → MTK `AI_TYPE_UNKNOWN`，`getAIValue` 返回 0；端口可能停在高阻/上拉状态，不会报错到用户程序（读回 0）。
4. **方向 1（A 读改 B 的 EE）**：固件层否；EE 在各自 STM32 内部 FLASH，无对外总线窗口。
5. **方向 2（可收可发传感器互传）**：固件层否；但**物理层**上超声 ping、红外/颜色 LED 是固件主动触发的（`GetUltraSonic/GetColor` 由 STM32 侧处理函数驱动），可作为单向"光/声调制"通道——**可行性取决于传感器驱动时序是否由"读取 API"触发**，本报告未能确认"读取时才点亮 vs 常亮"，需实测（见下）。

---

## 四、未解清单 & 下一步方法

| # | 未解项 | 下一步 |
|---|---|---|
| 1 | EE 命令字（哪个槽/id/字节承载 addr/val）、槽数 128、页地址 | 解析 `ProtocolService` AIDL 服务端 / `ControllerApi$Controller` 的 `getData/setData` 实现；或真机抓 `/dev/ttyMT1` 逻辑分析仪波形对比 SetEE/GetEE |
| 2 | 12 口探测算法（上拉/脉冲/单总线）、模式切换寄存器序列 | 反汇编 0x08007200-0x08007F00 槽位处理函数；找 GPIOx_CRL/CRH 写入 + 输入捕获 |
| 3 | 灰度/颜色 LED 点亮时机、超声 ping 触发点 | 同上；重点看 AI 采样类槽位函数 0x080077A4/0x08007958/0x08007CE8/0x08007EA4 |
| 4 | AI_TYPE_* 数值、`.data` 初值 | `readelf -x .data` + 解析 R_ARM_RELATIVE；或从 Java `Sensor$AiType`/字符串顺序对齐 |
| 5 | USART1/3 用途；ttyMT0 是否接到 STM32 某 USART | 波形/原理图；展开 0x08006460/0x08006630 附近初始化 |
| 6 | 槽位↔语义精确表 | 逐函数展开 4 个 case 调用链（本次时间盒内未完成） |

---

## 五、证据文件索引（`_分析临时/stm32分析/`）

| 文件 | 内容 |
|---|---|
| `01_elf_info.txt` | libRobot.so ELF 节/符号/动态符号全表（未 strip） |
| `02_syms_strings.txt` | 全部符号 + .rodata/debug_str 字符串（API 名、`%s&%d...` 格式串、JNI 类型表） |
| `03_disasm_libRobot.txt`、`05_disasm_annot.txt` | capstone 反汇编（带 GOT/字符串注解），CCJ_Interface/SetMotor/SetEE/GetEE/getSendCmdBuffer 等 |
| `04_xrefs.txt` | 字面量池交叉引用（PIC 偏移式，说明直接 xref 扫描为空的原因） |
| `06_dex_strings_raw.txt` / `06_dex_strings_kept.txt` | classes.dex + classes2.dex 全部字符串（55,109+4,570 条）与协议关键词过滤 |
| `07_dex_focus.txt` | 协议/串口/CRC/TTL/EEPROM 相关字符串汇总 |
| `08_all_abilix_classes.txt`、`08_match_names.txt` | com.abilix.* 全部类/字段/方法签名（字段名即常量名：`OFFSET_*`、`BAUD_RATE_2000000`、`HEADER_AA/55/66/BB`…） |
| `09_keyclass_bytecode.txt`、`10_keyclass_bytecode.txt` | androguard 反汇编的 Java 字节码（Protocol、Protocol$MasterUART/TransUART、serial/*、Datagram、ControllerApi、Sensor） |
| `12_ccj_interface.txt` | `ProgramAndInterfaceC.CCJ_Interface` 全字节码（API 名→分派编号表） |
| `11_stm32_full_disasm.txt`、`11_stm32_notes.txt`、`11_stm32_consts.txt` | STM32 全量 Thumb 反汇编、外设字面量访问表、关键立即数（AA/55/BB/66、FLASH 键、0x44） |
| `01~11 *.py` | 全部可复现脚本（pyelftools/capstone/androguard） |

> 复现环境：Python 3.12 + capstone 5.0.7 + pyelftools + androguard 4.1.4（本次为解析 dex 临时安装，只读使用）。未运行任何机器人固件、未修改仓库既有文件。
