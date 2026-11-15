# APK 证据素材（SKCON9 / Abilix 九代板）

> 交接文档。分析时间 2026-11-11。来源：官方 PC 安装目录（只读）+ brainApk 6F 三件套（AbilixSetting_25 / AbilixUpdate_1 / Controller_43）+ 既有解包产物。
> 除注明外均为**静态逆向**，未在真机验证；"待验证"表示字节码已读到、但需要在设备/串口上实测确认。
> 工作区：`D:\UserData\Documents\WER\2026普级赛`。临时反编译目录在 `C:\Users\s1325\AppData\Local\Temp\wer_apk\`（可能被清理，复现脚本见附录 C）。

## 0. 结论速览

| # | 问题 | 结论 |
|---|------|------|
| 1 | 官方 adb.exe 谁调用 | **不可行**：随包分发但全工程无调用点，字符串仅作为常量存在 |
| 2 | Android 侧开 ADB | **间接可行（待实测）**：无现成开关；但 Setting 是 `sharedUserId=android.uid.system` + AOSP testkey 签名，可用 testkey 自签"设置"更新包拿到 system UID |
| 3 | 官方更新/装 APK | **可行（有条件）**：/sdcard/Abilix/update 投放 → 广播 `ACTION_SW_UPDATE` → 系统 `com.grandar.installservice` 安装；只比 versionCode，无签名/hash 校验；同包名替换仍受 Android 签名校验约束（Setting 因 testkey 可替换，Controller 不行） |
| 4 | 有线下载协议（CH340→ttyMT0） | **可行**：机器人侧 `55 55 11` 握手 + 15B 头 + 2064B 分片 + 8 位和校验，可自写串口工具；PC 侧另有一套 AA55 帧（cmd1=176 握手 / cmd1=1 传文件），波特率 937500 与机器人 1000000 不一致，**需实测** |
| 5 | C 用户程序 | **可行（受应用沙箱限制）**：.c 打包经 fileType=20/串口 zip 下发 → 机器人端 gcc4.8.2 编译 → 复制为 `filesDir/libuser.so` → 在 com.abilix.controller 进程内 dlopen/JCC_Main，可调 libc（socket/open/system），但无 root |
| 6 | 8890 文件传输 | **可行且无鉴权**；存在路径穿越/任意写风险（fileName 未过滤 `../`；appType>4 直接 `new File(fileName)` 绝对路径；zip 解压未做 canonical 校验） |
| 7 | 其他 Android 入口 | **可行**：8890/10086 TCP、7777/9999 UDP 无鉴权；Controller `ProtocolService`/`UVCService`、Setting `SettingReceiver`/WelcomeActivity、Update `UpdateReceiver`/`ApkManageService` 均默认或显式导出 |

## 0.1 本轮最重要的新发现（先读这 5 条）

1. **AbilixSetting_25.apk = 系统 UID + AOSP testkey**（决定性）：
   - `AndroidManifest.xml` 第 1 行：`android:sharedUserId="android.uid.system"`；
   - 签名证书 subject 与 AOSP testkey 完全一致：`C=US, ST=California, L=Mountain View, O=Android, OU=Android, CN=Android, emailAddress=android@android.com`，notBefore `2008-04-15 22:40:50 UTC`，SHA-256 `c8a2e9bccf597c2fb6dc66bee293fc13f2fc47ec77bc6b2b0d52c11f51192ab8`（即公开的 AOSP testkey 指纹）。
   - 含义：该 ROM 的平台签名极可能就是 testkey。用公开 testkey 私钥自签一个 `com.abilix.controller.setting` 更新包（versionCode>25、sharedUserId 相同），经官方更新链安装后即可获得 **system UID**，从而写 `Settings.Global` 开 adb、静默装应用、读写任意目录。**待实测**（安装服务是否放行、/data 更新是否保留 system UID）。
2. **8890 TCP 文件传输无任何鉴权**，且 `fileType=1` 直接落 `/sdcard/Abilix/update`；传完发 `cmd2=9` 即触发 `ACTION_SW_UPDATE` 广播 → 自动扫描安装。整条"远程投递 APK → 自动安装"链路成立（同网段即可）。
3. `adb.exe` 是死文件：C# 里只有 `COMMANDEXEC="adb.exe"` 常量，无引用；所有 Managed DLL/EXE/Lua 无 adb 调用。
4. 有线下载协议两套都读全了：机器人 `TransSerial` 的 `55 55 11` 直接收 zip 状态机；PC `UsbManager` 的 AA55 文件传输帧。可自写工具，但**波特率/握手对应关系需实测**（见 Q4）。
5. C 用户程序不是独立进程/不是 root：编译产物被复制成 `filesDir/libuser.so`，在 Controller 应用进程内 `dlopen`，`JCC_Main` 是 JNI 入口。

---

## Q1. 官方 adb.exe 的使用方式

### 结论：**不可行**（官方程序不调用 adb.exe；adb 通道在本机型上不存在）

### 证据

1. 文件确实随包分发：
   - `D:\Program Files\AbilixScratch3.0\AbilixScratch3.0_Data\StreamingAssets\adb\adb.exe`（908,800 B，2026-04-23 16:44）
   - 同目录 `AdbWinApi.dll`（96,256 B）
2. C# 反编译里只有一个"声明"，没有调用：
   - `逆向资料/decompiled/Assembly-CSharp.decompiled.cs:110819`
     ```csharp
     public static string COMMANDEXEC = "adb.exe";
     ```
     所在类 `PartnerX.Abilix.PCScratch.Common.Constants`；`COMMANDEXEC` 在 121,060 行全文件中**仅出现 1 次**（`grep -c COMMANDEXEC` = 1），无 `Process.Start`/`ShellUtil` 引用。
   - 邻近常量：`110821 BLOCKLYPATH`、`110829 UPDATEPATH = Application.streamingAssetsPath + "/update/BlocklyC_V103.apk"`、`110831 VERSION = 103`。可见 `adb.exe` 与资源路径同属"随包工具"常量表。
3. 二进制层面确认字符串只是资源：
   - `Managed/Assembly-CSharp.dll` 的 UTF-16 `#US` 堆偏移 `0x1e437b` 处为 `adb.exe`，前后是 `hide`、`/Blockly_Code/`、`/img/title.png`、`/Blockly_Code/AILearn/AILearn.exe`、`/ai_temp/`、`/update/BlocklyC_V103.apk`、`abilixProjectConfig.txt` 等字符串，属常量池，不是可执行路径拼接。
   - 对 `AbilixScratch3.0.exe`、`Managed/*.dll`、`Plugins/xlua.dll`、`Plugins/zf_cef.dll`、`Mono/mono.dll` 全量扫描（ASCII + UTF-16）：**除上述一处外无 `adb` 命中**；`zf_cef.dll` 的 CH340/adb 命中是 USB 设备数据库文本，不是调用。
4. 官方 Lua（`逆向资料/xlua明文/` 约 500 个 .lua）搜 `adb`、`tcpip`、`5555`、`5556`、`pm install`、`adb shell`、`push`、`pull`、`logcat`：**0 命中**。
5. 设备侧事实（上一轮已确认）：USB-C 插 PC 枚举为 CH340 串口 COM3，`adb devices` 看不到设备 → 设备没有对外 adb 接口，即使调用 adb.exe 也无设备可连。

### 对新会话的建议动作
- 若要彻底闭环：用 Process Monitor 抓 `AbilixScratch3.0.exe` 启动时的子进程，确认运行期是否拉起 `adb.exe`（静态看不会）。
- `StreamingAssets/adb/` 更可能是给"其他机型/售后工具"预留；不要在这条线上投入。
- 转向 Q2 的 testkey 路径或 Q4 串口路径。

---

## Q2. Android 侧是否存在 ADB 开启可能

### 结论：**现成开关不存在（不可行）；但存在 testkey + system UID 的间接路径（待实测，优先级最高）**

### 证据

1. Setting 里唯一的 ADB 相关代码是**只读查询**，且是死代码：
   - `C:\Users\s1325\AppData\Local\Temp\wer_apk\disasm\Setting\com_abilix_controller_setting_application_Common.txt`，方法 `AdbEnabled()Z`（文件第 64 行起）：
     ```smali
     invoke-virtual {v0}, ContentResolver
     const-string v1, "adb_enabled"
     invoke-static {resolver, v1, 0}, Settings$Global;->getInt(...)I
     if-ne v0, 1, :cond
     ```
     返回 boolean；**不写**。
   - 全 Setting 反编译检索 `Common;->AdbEnabled`：**0 个调用点**（只在定义处出现）。
2. 权限不允许写全局设置：
   - Setting manifest 权限（`manifest_decoded.xml`）：`WRITE_SETTINGS`、`WRITE_EXTERNAL_STORAGE`、`DEVICE_POWER`、`KILL_BACKGROUND_PROCESSES`、`SYSTEM_ALERT_WINDOW` 等；**无 `WRITE_SECURE_SETTINGS`、无 `INSTALL_PACKAGES`、无 `REBOOT`**。
   - 全 APK 字符串检索 `Settings$Global;->putInt`：0 命中；`adb_enabled` 仅上述 1 处 `getInt`。
3. 没有任何 adbd/tcpip/USB 调试字符串：
   - Setting / Update / Controller(6F) / BlocklyC 的 strings 与 dex 字符串表中搜 `tcpip`、`5555`、`5556`、`adbd`、`UsbDebugging`、`ro.debuggable`、`serial console`、`telnet`：**0 有效命中**（Controller 的 `loadByRowId` 是误匹配；`maybeSuperUser` 是 Netty 的 `PlatformDependent` 内部方法，见 Q7）。
4. 但 Setting 的**签名与 UID 暴露了系统钥匙**（本轮关键发现）：
   - `AbilixSetting_25/manifest_decoded.xml:1`：
     ```xml
     <manifest ... android:sharedUserId="android.uid.system" ... package="com.abilix.controller.setting">
     ```
   - 证书（`androguard` 读取 `META-INF/CERT.RSA`）：subject 为 `C=US, ST=California, L=Mountain View, O=Android, OU=Android, CN=Android, emailAddress=android@android.com`；notBefore `2008-04-15 22:40:50`；SHA-256 `c8a2e9bccf597c2fb6dc66bee293fc13f2fc47ec77bc6b2b0d52c11f51192ab8` —— 与公开的 **AOSP testkey** 一致。
   - 对照：`Controller_43.apk` 与 `AbilixUpdate_1.apk` 证书为 `CN=Abilix`（notBefore `2016-08-23 07:06:54`，SHA-256 `188885cea4d35c748f6b80fb2ea80fcd38a635e06e1376f2f61fa757476750f5`），是厂商发布 key，不能伪造。
   - 推论：该 ROM 的平台签名 = testkey（否则 Setting 无法以 `android.uid.system` 共享 UID 运行）。用公开 testkey 私钥签一个同包名、versionCode>25、同 sharedUserId 的 APK，替换 Setting 后即获得 system UID；system UID 可 `WRITE_SECURE_SETTINGS`（写 `adb_enabled=1`）、可 `setprop service.adb.tcp.port 5555` 并重启 adbd、可静默安装。
5. 其他"开发者选项"入口：Setting 的布局有 `fragment_hot/fragment_sysup/fragment_wifi/fragment_bluetooth`、`activity_settings`、`dialog_data_editor`，**没有** developer/adb 相关界面；Controller 也没有。

### 对新会话的建议动作
1. **优先验证 testkey 路径**（成本低、收益最大）：
   - 用 AOSP `build/target/product/security/testkey.pk8` + `testkey.x509.pem` 签一个最小 APK：package `com.abilix.controller.setting`、`sharedUserId="android.uid.system"`、versionCode 26、声明 `WRITE_SECURE_SETTINGS`；
   - 通过 Q6 的 8890 文件传输（fileType=1）投到 `/sdcard/Abilix/update`，再发 cmd2=9 触发安装；
   - 装后 `adb_enabled=1` 或直接 `Runtime.exec("setprop service.adb.tcp.port 5555; stop adbd; start adbd")`。
   - 失败时抓 `logcat` 的 `INSTALL_FAILED_*`（`INSTALL_FAILED_SHARED_USER_INCOMPATIBLE` = UID/签名不匹配；`INSTALL_FAILED_UPDATE_INCOMPATIBLE` = 签名不匹配）。
2. 备选：查设备是否已开 `ro.debuggable=1`（串口 shell 或 `/system/build.prop`），但当前无入口读。
3. 若无安装权限，回到 Q4 串口，直接给机器人发指令。

---

## Q3. 官方"更新/安装 APK"机制

### 结论：**可行（有条件）**——链路完整、无签名/hash 校验，但同包名替换受 Android 签名约束；Setting 因 testkey 可替换，Controller/Update 不行

### 证据

1. 更新服务（`AbilixUpdate_1.apk`，package `com.abilix.controller.updateservice`，v1/1.0.1，targetSdk 27）：
   - Manifest（`AbilixUpdate_1/manifest_decoded.xml`）：
     ```xml
     <service android:name="com.abilix.controller.service.ApkManageService">
       <intent-filter><action android:name="com.abilix.controller.service.action_UPDATE_SERVICE"/></intent-filter>
     </service>
     <receiver android:name="com.abilix.controller.updateservice.UpdateReceiver" android:exported="true">
       <intent-filter><action android:name="com.abilix.controller.service.ApkManageService.ACTION_SW_UPDATE"/></intent-filter>
     </receiver>
     ```
     服务带 intent-filter → targetSdk 27 下默认导出；receiver 显式 `exported="true"`。
   - `UpdateReceiver.onReceive`（`disasm\Update\com_abilix_controller_updateservice_UpdateReceiver.txt`）：只判断 action 是否等于上面的字符串 → 打日志 `"启动更新服务！"` → `startService(ApkManageService)`。**无调用方包名/权限校验**。
2. 扫描与版本比较（`disasm\Update\com_abilix_controller_service_ApkManageService.txt`）：
   - `initUpdateApkArray()`：`new File(FileUtil.DIR_UPDATE).listFiles(后缀 .apk)`；`Common.getPackageArchiveInfo(path)` 取 `packageName/versionName/versionCode`；
     - 已装同包且 `installed.versionCode >= apk.versionCode` → 日志 `"[%s] 已安装相同或更高版本: %d >= %d, 删除apk文件！"` 并删文件；
     - 解析失败 → `"[%s]文件错误, 删除apk文件！"`；
     - 其余加入 `mPkgOrders`，但**显式跳过 `com.abilix.controller` 与 `com.abilix.controller.updateservice`**，循环结束后追加到队尾（保证自身最后装）。
   - 无签名校验、无 hash、无机型字段；只比 versionCode。
3. 安装动作：
   - `installUpdateApkByOrder()`（同文件第 294 行起）：`Intent("com.abilix.controller.service.ACTION_INSTALL")`，`putExtra("ApkPath", ...)`、`putExtra("PackageName", ...)`，`sendBroadcast`；日志 `"安装序号："`、`"安装完成！"`。
   - `ApkInstallReceiver`（`disasm\Update\com_abilix_controller_service_ApkManageService_ApkInstallReceiver.txt`）收到 `ACTION_INSTALL`（第 662 行）→ `ApkManager.installApk(path, pkg)`。
   - `ApkManager`（`..._ApkManageService_ApkManager.txt`）：`bindService(Intent("com.grandar.installservice.AIDLInstallService").setPackage("com.grandar.installservice"))`，调用 `AIDLInstallService.installApk(path, pkg)`；卸载走 `com.grandar.deleteservice/AIDLDeleteService.deleteApk(pkg)`。
   - 即真正安装由**预置的系统服务 `com.grandar.installservice`** 完成；`AbilixUpdate_1.apk` 只是客户端（内含 `com/grandar/installservice/AIDLInstallService$Stub` 等 AIDL 类）。
4. 安装触发入口：
   - 8890 文件传输：`ProtocolDatagramHandler` 在 `ControllerService.txt` 字节码偏移 1012 处，日志 `"apk文件传输完成，开始安装apk"` → `sendBroadcast(Intent("com.abilix.controller.service.ApkManageService.ACTION_SW_UPDATE").setFlags(32))`；
   - 或任意应用直接发上述广播（receiver 导出，无权限）。
5. 第三方签名能否装：
   - 目标包已存在时，Android PackageManager 强制同包名同签名，`com.grandar.installservice` 不能绕过（除非它用特权手段，服务实现不在我们拿到的 APK 里，**待验证**）；
   - `com.abilix.controller.setting` 是 testkey，**可**用 AOSP testkey 自签替换（见 Q2）；
   - `com.abilix.controller` / `com.abilix.controller.updateservice` 是厂商 `CN=Abilix` key，无法伪造；
   - **新包名**（自己的应用）只要 `com.grandar.installservice` 不做白名单，就能装——这是 U 盘/8890 装第三方 App 的现成通道。
6. 另一条更新通道（非 adb）：`BrainApkUpgradeController`（`逆向资料/decompiled/Assembly-CSharp.decompiled.cs:28323-28342`）通过局域网服务推送 brainApk（`BRAIN_APK_RELATIVE_PATH="extenddatas/brainApk/"`、`BRAIN_APK_VERSION_NAME="brainApkVersion.txt"`），PC 端只负责下发，安装仍落到机器人侧上面的链路。

### 对新会话的建议动作
- 先做无风险实验：把一个自签名的新包名 APK 放进 `/sdcard/Abilix/update`，广播 `com.abilix.controller.service.ApkManageService.ACTION_SW_UPDATE`，看是否安装成功（验证 grandar 服务是否白名单）。
- 再做 testkey 替换 Setting 的实验（Q2），这是拿 system UID 的最短路径。
- 抓 `logcat`（如果拿到 shell）确认 `INSTALL_FAILED_*` 具体码。

---

## Q4. 有线下载协议（USB-C → CH340 → 机器人 ttyMT0）

### 结论：**可行**——机器人侧状态机完整可实现自写下载/上传工具；PC 侧另有一套 AA55 帧协议；两套的对应关系与波特率需实测

### 证据 A：机器人侧（Controller_43，ttyMT0）

文件：`...\wer_apk\disasm\Ctrl6F\com_abilix_controller_api_serial_TransSerial.txt`

1. 端口与波特率（构造器，文件第 32 行起）：
   ```smali
   new-instance v0, Ljava/io/File;
   const-string v1, "/dev/ttyMT0"
   invoke-direct {v0, v1, File-><init>(String)V
   const v1, 1000000
   invoke-direct {v3, v0, v1, v2, TransSerial-><init>(File;II)V
   ```
   → `/dev/ttyMT0`，**1,000,000 bps**。
2. 常量（字段区）：
   - `CMD_HEAD = 85 (0x55)`、`ping_ID = 17 (0x11)`
   - `picoc_cmd_WRITECODE = 5`、`picoc_cmd_WRITECODEDONE = 6`
   - `HEAD_LEN = 15`、`TAIL_LEN = 1`、`SENDBAG = 2064`
3. 握手（`recvProtocol()`，文件第 145 行起）：读 5 字节，判断
   ```smali
   [0]==0x55 && [1]==0x55 && [2]==0x11
   ```
   成功日志 `"recvProtocol: 进入PC下载"`，置 `nPCStep=1`、`bPCDownload=true`；失败日志 `"recvProtocol:  head error: %02x %02x %02x"`。
4. 状态机（`PCDownload()`，文件第 211 行起）：
   - 正确请求回 `PCSendBuff[0]=0x61`（字符 `'a'`），日志 `"step4: 回复正确请求"`；
   - 错误回 `0x65`（`'e'`），日志 `"step4: 接收错误，回复错误请求"`；
   - 数据帧：`[0]=0x55, [1]=0x55, [2]=cmd`，`[10..13]`=文件长度大端，`[14]`=文件数据 8 位累加和，**数据从 offset 15 开始**；`HEAD_LEN=15` 与此一致；每包最多 `SENDBAG=2064` 字节；
   - 结束帧 `[2]=6`（WRITECODEDONE）；
   - 校验通过日志 `"step3: 文件校验正确"`；
   - `[3..9]` 字节含义未在反编译中体现（恒 0 或保留），**待实测确认**。
5. 落盘与解压（`processFile([B)`，文件第 94 行起）：写 `/sdcard/Abilix/tmp/tmp.zip`，然后 `FileUtil.handleProgramZip(file)`。
6. 解压逻辑（`...\disasm\Ctrl6F\com_abilix_utils_FileUtil.txt`，约第 761 行）：
   - `unZipFile(file, DIR_TMP)`；
   - 检查 `DIR_TMP/zip_temp` 目录（zip 内需有 `zip_temp/` 前缀）；
   - 遍历其中 `.c/.py/.js`，取最后一个 `rename` 到 `DIR_PROGRAM`；
   - 错误码：-1 解压错误、-2 `zip_temp` 不存在、-3 `"没有找到可执行文件！"`、-4 rename 失败。

### 证据 B：PC 侧（C# 串口）

文件：`逆向资料/decompiled/Assembly-CSharp.decompiled.cs`

1. `LibUart : ISender`（第 95285 行起）：
   - `m_nBaudRate = 937500`（95293）、`m_nReadTimeout = 1000`、`READCOUNT = 12`；
   - `OpenSerialPort`（95367-95369）：`new SerialPort("\\\\?\\" + portName, m_nBaudRate)`；
   - `TryConnectSerialPort`：遍历 `SerialPort.GetPortNames()`，优先 `PlayerPrefs.GetString("portName")`；对每个口发 3 次连接包（10ms/100ms 间隔）。
2. `UsbManager : SingletonMono<UsbManager>`（96130 起）：
   - `m_nBaudRate = 937500`（96139）、`m_nReadTimeout = 600`、`fRetryConnectUsbInterval = 3f`、`nSendBytesOnce = 2064`、`nResendMaxNum = 6`；
   - 握手 `SendConnectProtocol`（96223-96227）：`RobotUtils.buildProtocol(1, 176, 1, null)` 写入串口；
   - `TryConnectSerialPortCoroutine`（96368）：发后 `Thread.Sleep(500)`，读 20 字节，校验 `recvBuff[5]==176 && recvBuff[6]==1 && recvBuff[11]==1` 才算成功，失败 3 秒重试；
   - `RequestSendFile(byte appType, byte fileType, string filepPath)`（96517）：
     ```
     payload[0]=appType; payload[1]=fileType;
     payload[2..5]=intToByteArray(fileLength);   // 大端
     payload[6..9]=intToByteArray(CRC32(file));  // 大端
     payload[10..]=UTF8(fileName)
     发送 buildProtocol(1, 1, 1, payload)
     ```
   - `SendThreadHandler`：按 2064 字节分块，`buildProtocol(1, 1, 3, chunk)`，每块 `Thread.Sleep(200)`；EOF 发 `buildProtocol(1, 1, 4, null)`；
   - `OnReceive`（应答均 `bytes[5]==160`）：`[6]=1` 开始、`2`+`[11]=0` CRC 错、`3` 完成、`4` 继续（isWait=false）、`5` 暂停（isWait=true）、`7`+`[11]=0` 文件已存在；
   - `SendData(string path)` 直接 `RequestSendFile(2, 4, path)`（96262）。
3. 帧格式（`RobotUtils.buildProtocol`，99580）：
   ```
   AA 55 lenH lenL type cmd1 cmd2 00 [08] 00 seq payload... checksum
   len = 总长 - 4（即 8 + payload 长度）
   [08] = 1 当 cmd1==0 && cmd2==0，否则 0
   [10] = seq（DATA_PACKAGE_INDEX++ % 255）
   末字节 = 前面所有字节 8 位累加和
   总长 = 12 + payload 长度
   ```
   握手包 = `AA 55 00 08 01 B0 01 00 00 00 seq cs`（12 字节）。
4. Lua 调用点（官方 PC 端"下载到机器人"）：
   - `逆向资料/xlua明文/ui/pc_chart/downloadPCView.lua:91`：`cs.WifiManager.instance:DownloadFile(0x02, 0x04, filePath)`
   - `逆向资料/xlua明文/ui/pc_chart/connector/wifiConnectPCView.lua:116`：同样 `DownloadFile(0x02,0x04,zipPath)`
   - `ScratchProgrammingView.lua:1032/1046` 注册 `onDownLoadFileResultHandler`。
   → 官方 PC 端确实通过"文件传输"通道（appType=2、fileType=4）下发；`DownloadFile` 绑定到 C# 的 `_m_RequestSendFile`（23458）。

### 证据 C：机器人侧 8890/TCP 同构协议（供对照）

- `Datagram`（`...\disasm\Ctrl6F\com_abilix_controller_conn_Datagram.txt`）解析：`[0..1]=AA 55`、`[2..3]=length`（BE）、`[4]=type`、`[5]=cmd1`、`[6]=cmd2`、`[7..9]=reserved`、`[10]=seq`、`[11..len-2]=data`、`[len-1]=checksum`。
- `ProtocolDatagramHandler` cmd1：`176(0xB0)` 连接/保活、`10(0x0A)` 编程、`1` 文件传输、`160(0xA0)` 应答；default `"no handler for case: "`。

### 关键未决点（必须实测）
- **波特率矛盾**：PC 两处 `SerialPort` 都是 **937500**，机器人 `ttyMT0` 是 **1000000**。可能是：PC 端 937500 只用于旧机型/USB dongle，SK9 另有路径；或 `TransSerial` 的 1M 只用于 55 55 11 工具，AA55 走别的 UART。建议先按 1M 试，失败再试 937500。
- **握手对应**：PC 发 AA55+B0 握手，机器人 `recvProtocol` 只认 `55 55 11`。两种可能：AA55 走 Datagram 处理器（不是 recvProtocol），55 55 11 是工厂/独立 PC 工具入口。两条都实现即可覆盖。
- 参考上一轮结论：`双板通讯研究/分报告_APK与串口协议.md`（ttyMT1@2M 主链路、ttyMT0@1M PC 下装通道、40B/32B/72B 帧）。

### 对新会话的建议动作
1. 写 Python `pyserial` 脚本（COM3）：
   ```python
   ser = serial.Serial('COM3', 1000000, timeout=1)  # 失败改 937500
   ser.write(bytes([0x55,0x55,0x11]))
   ack = ser.read(1)  # 0x61 成功 / 0x65 错误
   # 之后每帧: 55 55 05 + 9 字节保留 + size_be(4) + sum8 + data(<=2064)
   # 结束帧: 55 55 06 + ... + size_be + sum8
   ```
2. 先用 100 字节小文件验证"写 tmp.zip → 解压 → 文件出现在 /sdcard/Abilix/program"（通过 8890 或 App 界面观察）。
3. 同时抓 PC 官方软件下载时的串口波形/逻辑分析仪（CH340 TX/RX），确认波特率与首包字节，一次性解决 Q4 的两个未决点。

---

## Q5. C 用户程序路径（gcc4.8.2 / JCC_Main / libuser.so / -lRobot）

### 结论：**可行**——编译在机器人端执行，产物在 Controller 应用进程内加载；C 代码可调 libc（socket/open/system），但受 Android 应用沙箱限制，无 root

### 证据

1. 编译命令（`...\wer_apk\disasm\Ctrl6F\com_abilix_utils_CompileUtil.txt`）：
   - 第 230 行：`"export PATH=/system/xbin/gcc4.8.2/bin:$PATH"`
   - 第 398 行：`"arm-linux-androideabi-gcc *.c -pie -fPIC -L. -lm -lRobot -shared -o "`
   - 另有 `"compile result:"`（446）、`"compileDir:%s"`（176）；由 `ShellUtil.execCommand` 执行（上一轮已确认）。
   - 即：gcc4.8.2 工具链在机器人 `/system/xbin/gcc4.8.2/bin`，用户 .c 在当前目录编译成 `librobot_xxx.so`（`-shared`），链接厂商 `libRobot.so`（`-lRobot`）。
2. JNI 入口与 libuser.so：
   - `...\disasm\Ctrl6F\com_abilix_utils_ProgramAndInterfaceC.txt`
     - `<clinit>`（文件第 10-50 行）：
       ```smali
       ControllerApp.getAppContext().getFilesDir().getAbsolutePath()
       const-string "libuser.so"
       FileUtil.getFilePath(dir, "libuser.so") -> FILE_LIBUSER_SO
       const-string "Robot"; System.loadLibrary("Robot")
       ```
     - `startRunning(String)`（文件 ~1500 行附近）：
       - 校验 .c 存在；
       - `CompileUtil.getTargetLinkLibName(file)` 得产物名，`FileUtil.getFilePath(parent, name)`；
       - 不存在则 `CompileUtil.compile(path)`；
       - 编译日志存在则读出并显示，返回 -1；
       - 产物存在则 `FileUtil.copyFile(产物, FILE_LIBUSER_SO)`，`sleep(60)`；
       - `new ProgramMainThread(...).start()` → 调用 native `JCC_Main(int, String)`（`ProgramMainThread` 中 `invoke-virtual JCC_Main(I Ljava/lang/String;)Ljava/lang/String;`）。
   - `libRobot.so`（`_分析临时/brainApk分析/6F/lib_armeabi-v7a_libRobot.so`）字符串：
     - `Java_com_abilix_utils_ProgramAndInterfaceC_JCC_1Main`
     - `Java_com_abilix_utils_ProgramAndInterfaceC_JCC_1Exit`
     - `libc.so`、`dlopen`、`dlsym`、`libdl.so`、`liblog.so`、`libm.so`、`libRobot.so`
     → 原生库导出 JNI 入口，内部 dlopen/dlsym 加载 `libuser.so`。
   - `Robot.h`（`_分析临时/brainApk分析/6F/assets_program_c_Robot.h`）：
     - 第 19 行 `#define main      Main`（用户 `main()` 被改名，由 JCC_Main 调）；
     - 第 32/40 行 JNI 声明 `Java_com_abilix_utils_ProgramAndInterfaceC_JCC_1Main/JCC_1Exit`；
     - 提供 `SetMotor/SetMotorTime/SetServo/WER_InitRobot` 等 API（`-lRobot` 链接）。
3. 运行时权限：
   - C 程序作为 `libuser.so` 在 **com.abilix.controller 进程**内加载（同一 UID，非 root、非独立进程）。
   - 可调用 libc 的 `socket/open/system/popen` 等（链接 libc，`libRobot.so` 依赖 `libc.so`；无 seccomp/沙箱证据）。
   - 受 Android 应用沙箱限制：
     - 有 `INTERNET` 权限（Controller manifest），可建 TCP/UDP；
     - 有 `READ/WRITE_EXTERNAL_STORAGE`，可读写 `/sdcard`（含 `/sdcard/Abilix`）；
     - 不能写 `/data/local/tmp`、不能 `su`、不能改系统属性（除非 system UID，见 Q2）。
4. 如何下载到机器人：
   - 8890/TCP：`FileTrans` appType/fileType，`fileType=20 (C)` → `getDstDir` 落 `/sdcard/Abilix/tmp` → 完成后 `ControllerService$5.onStateChanged` 对 fileType 20/21 调 `handleProgramZip` → 解压、找 `.c`、`CompileUtil.compile`；
   - 串口：`55 55 11` 收 zip → `/sdcard/Abilix/tmp/tmp.zip` → `FileUtil.handleProgramZip` → 解压出 `.c`（不自动编译，需 App/接口触发）；
   - PC 官方 Lua `DownloadFile(0x02,0x04,...)` 是 appType=2/fileType=4（BIN），不是 C 程序主路径。

### 对新会话的建议动作
1. 写最小 C 程序验证沙箱边界（放到 zip 的 `zip_temp/` 下）：
   ```c
   #include <stdio.h>
   #include <sys/socket.h>
   int main(){ FILE*f=fopen("/sdcard/Abilix/probe.txt","w"); if(f){fputs("ok",f);fclose(f);} 
               int s=socket(AF_INET,SOCK_STREAM,0); return s; }
   ```
   通过 8890 fileType=20 发送，观察 `/sdcard/Abilix/probe.txt` 与进程日志。
2. 若要 root：C 程序本身拿不到；必须借 Q2 的 system UID 路径。
3. 注意 `JCC_Main` 的 `int` 参数与 `String`（libuser.so 路径）——自写 .so 可绕过编译直接替换 `filesDir/libuser.so`（需写 filesDir 权限，即 App 自身或 system UID）。

---

## Q6. 8890 文件传输协议（appType/fileType/路径拼接/穿越）

### 结论：**可行且无鉴权**；路径穿越/任意写在字节码层面成立（待真机验证落点）

### 证据

1. 服务端（`...\disasm\Ctrl6F\com_abilix_controller_service_ControllerService.txt`）：
   - `onCreate`：`TCPNettyServer(10086)`（mTcpCmdNettyServer）+ `TCPNettyServer(8890)`（mTcpTransNettyServer）；`TransSerial`（ttyMT0）；`mFileTrans`。
   - 8890 监听器 `ControllerService$3.onChannelRead`：`new Datagram((byte[]) obj)` → 按 `mTcpTransSequenceNum` 去重 → `ProtocolDatagramHandler(17, datagram)`。
   - 无 token/密码/白名单/来源 IP 校验（通读该类未发现）。
2. 帧（`Datagram`）：`AA 55 | len(BE) | type | cmd1 | cmd2 | 00 00 00 | seq | data | checksum`；`build(byte type, byte cmd1, byte cmd2, byte[] data)`。
3. 文件信息 payload（`FileTrans` 构造，`...\com_abilix_controller_conn_FileTrans.txt`）：
   - 偏移：`[0]=appType`、`[1]=fileType`、`[2..5]=fileSize`（BE）、`[6..9]=CRC32`（BE）、`[10..]=fileName`（UTF-8）。
   - 枚举：`TRANS_TYPE_APK=1, ZIP=2, BIN=4, ELF=14, MP3=16, C=20, PY=21`。
   - 状态：`PREPARED=1, PAUSED=2, CANCELLED=3, FAILED=4, COMPLETED=5, FILE_EXIST=6, ERR=16`。
   - 目标目录 `getDstDir(int fileType)`：
     - 默认 `FileUtil.DIR_TMP`（`/sdcard/Abilix/tmp`）；
     - `fileType==1` → `FileUtil.DIR_UPDATE`（`/sdcard/Abilix/update`）；
     - `fileType ∈ {2,4,0x0E,0x10,0x14,0x15}` → `DIR_TMP`；
     - 其他 → 日志 `"未知类型: "`，仍 `DIR_TMP`。
   - `checkFileIsExisted()`（文件第 103 行起）：按 `appType` packed-switch：
     - appType 1/2/3 → `FileUtil.getFile(DIR_PROGRAM, fileName)`；
     - appType 0/4 → 直接跳到日志/CRC 段，按字节码该路径未给 dstFile 赋值（可能只对 1/2/3 有意义，**待验证**）；
     - default（appType 不在 0..4）→ `new File(fileName)`，**按绝对路径处理**。
   - `prepare(boolean)`：目标存在且 CRC 相同 → 日志 `"文件已存在,不重复下载"`；否则建 dstFile + 临时文件 + `BufferedOutputStream`；`write()` 写临时文件并更新 CRC32。
   - `complete()`：CRC32 匹配后 `dstFile.delete()` + `tmpFile.renameTo(dstFile)`，否则 FAILED。
4. 路径拼接无过滤（`com_abilix_utils_FileUtil.txt`）：
   - `getFilePath(dir,name)`（约第 717 行）：`dir + File.separator + name`，**没有 `../` 过滤、没有 canonical 校验**；
   - `getFile(dir,name)` 直接 `new File(getFilePath(...))`；
   - `unZipFile(File,dir)`（约第 1091 行）：对每个 `ZipEntry` 调 `getFile(dir, entryName)`，**未校验 entry 的 canonical path → ZipSlip 成立**（可写 `../../` 到 dir 之外）。
5. 完成后的处理（`ControllerService$5.onStateChanged`，`...ControllerService_5.txt`）：
   - `state` packed-switch `{1..6}` → 对应 PREPARED/PAUSED/CANCELLED/FAILED/COMPLETED/FILE_EXIST；
   - COMPLETED 分支再对 `getFileType()` sparse-switch `{1,2,4,14,16,20,21}`：
     - **20/21** → `ControllerService.handleProgramZip(file)`（解压→找 .c/.js/.py→`DIR_PROGRAM`→`ProgramRepo.insertOrReplace`；fileType 20 再 `CompileUtil.compile`）；
     - **1/2/4/14/16** → 不解压，仅回"文件接收成功"；
   - 字节码证据：sparse-switch keys `1 2 4 e 10 14 15`，targets 中 20/21 指向 handleProgramZip 调用（offset 352 区块），其余指向 offset 382（`const/4 v6,0`）。
6. 安装触发：`ProtocolDatagramHandler` 偏移 1012 `"apk文件传输完成，开始安装apk"` → 广播 `ACTION_SW_UPDATE`；偏移 1056 `"批量查询Apk版本号"`；偏移 610 `"APP请求发送文件"`；508 `"APP发送文件数据"`；460 `"APP发送完成"`；562 `"APP取消传输"`。
7. 风险判断：
   - **fileName 穿越**：`fileName="../../../../sdcard/evil"` 会拼成 `/sdcard/Abilix/tmp/../../../../sdcard/evil`，POSIX 解析后写到 `/sdcard/evil`（app 有 sdcard 权限）；写 `/data/local/tmp` 不行（无权限）。
   - **绝对路径**：appType>4 时 `new File(fileName)` 可用 `/sdcard/...` 绝对路径（但仍受 UID 权限限制）。
   - **ZipSlip**：zip 内 entry 名 `../../` 可写到 DIR_TMP 之外。
   - **无 CRC 之外的完整性校验**：CRC32 只防传输错误，不防篡改；无签名。
   - **无鉴权**：同网段任意主机可连 8890 发文件。

### 对新会话的建议动作
1. 先确认 8890 可达：`nc <robot-ip> 8890` 或 Python socket；发 `AA 55` 帧查询 APK 版本（cmd2=8）验证。
2. 用 `fileType=1` 传一个小 APK 到 `/sdcard/Abilix/update`，发 cmd2=9，观察是否自动安装（Q3）。
3. 路径穿越实验用**无害文件**：fileName=`../../../../sdcard/Abilix/tmp/probe.txt` 或 zip entry `../../probe.txt`，验证后立即删除。
4. 把 8890 协议写成 Python 库（帧编解码 + 文件分片 + CRC32），作为后续所有实验的基础工具。

---

## Q7. 其他 Android 侧接入入口

### 结论：**可行**——导出组件与未鉴权 TCP/UDP 端口多，足以在不改系统的情况下控制机器人/装应用

### 证据

1. Controller_43（package `com.abilix.controller`，targetSdk 27）manifest（`_分析临时/apk分析/提取/manifest_Controller6F.xml`）：
   - `MainActivity`（MAIN/VIEW + LAUNCHER）→ 导出；
   - `ProtocolService`（`:protocolservice`）带 `<intent-filter><action android:name="com.abilix.controller.IControllerInterface"/></intent-filter>` → targetSdk 27 下**默认导出**；内部是 AIDL `IControllerApi`（34 个方法，上一轮报告已列）；
   - `UVCService`（`:uvcservice`）带 `com.serenegiant.service.IUVCService` / `IUVCSlaveService` → 默认导出；
   - `CodeGeneratorService` 显式 `exported="false"`；
   - `ProcessLifecycleOwnerInitializer` provider `exported="false"`；
   - `ControllerService` / `RunningService` 无 intent-filter → 不导出（但 8890/10086 是它开的 socket）。
2. Setting（`com.abilix.controller.setting`，sharedUserId=android.uid.system）：
   - `SettingsActivity`（MAIN/VIEW + LAUNCHER）→ 导出；
   - `WelcomeActivity` 带 `android.intent.action.app.welcome` → 导出；
   - `SettingReceiver` **exported="true"**，actions：
     - `android.intent.action.ACTION_SHUTDOWN`
     - `com.abilix.controller.action.ACTION_SHUTDOWN`
     - `com.abilix.controller.action.SCREEN_OFF`
     - `com.abilix.controller.action.SCREEN_ON`
     - `com.abilix.controller.action.SET_SLEEP_TIMEOUT`
     → 任意应用可发广播让机器人关机/熄屏/改休眠。
3. Update（`com.abilix.controller.updateservice`）：
   - `ApkManageService` 带 `...action_UPDATE_SERVICE` → 默认导出；
   - `UpdateReceiver` **exported="true"**，action `com.abilix.controller.service.ApkManageService.ACTION_SW_UPDATE` → 可直接触发更新流程（Q3）。
4. 网络端口（ControllerService）：
   - TCP `10086`（命令）、`8890`（文件传输，无鉴权）；
   - UDP `7777`、`9999`（上一轮报告；`SocketPortType7777/9999/8890/10086` 字符串在 Assembly-CSharp.dll 中亦可见）。
5. 调试/root/console：
   - 全 APK 搜 `telnet`、`adbd`、`busybox`、`getprop`、`setprop`、`/system/bin/su`、`superuser`、`Runtime.exec`、`ProcessBuilder`：**无有效命中**；
   - `maybeSuperUser` / `maybeSuperUser0` 仅出现在 `io.netty.util.internal.PlatformDependent`（`_分析临时/apk分析/提取/dexstrings_Ctrl6F_classes2.txt:3717-3718`），是 Netty 判断 root 环境的内部方法，不是 Abilix 功能；
   - Controller manifest 无 `android:debuggable`，Setting/Update 亦无；
   - 系统属性读写未见 Abilix 代码使用。
6. 隐式广播限制：targetSdk 27 下静态注册的隐式广播（如 `ACTION_SHUTDOWN`）仍可被外部显式 intent 触发（指定 component 即可），不受 Android 8 隐式广播限制影响。

### 对新会话的建议动作
1. 写一个外部 App（或 PC 上的 `am`/`adb`——若 Q2 成功）绑定 `ProtocolService`，用 `IControllerApi` 直接控制（比逆向 8890 帧更快）。
2. 若只做 PC 侧：优先 8890（文件+命令）+ 10086（命令）两条 TCP；UDP 7777/9999 可作发现/心跳。
3. 触发 `SettingReceiver` 的 `SCREEN_ON/OFF`、`SET_SLEEP_TIMEOUT` 做无害验证。
4. 不要依赖 root 字符串——本套 APK 没有 root 能力。

---

## 附录 A：产物与路径索引

### 工作区（持久）
- `双板通讯研究/分报告_APK与串口协议.md`（上一轮 300 行总报告）
- `_分析临时/apk分析/apk_Controller6F/`（Controller 6F 解包目录：classes.dex 7.35MB + classes2.dex 556KB + assets + lib）
- `_分析临时/apk分析/提取/`：
  - `manifest_Controller6F.xml`、`manifest_BlocklyC.xml`
  - `dexstrings_Ctrl6F_classes*.txt`、`dexmethods_Ctrl6F_classes*.txt`
  - `disasm_C_com_abilix_controller_api_Protocol$MasterUART.txt`、`disasm_C_com_abilix_utils_CompileUtil.txt`、`disasm_C_com_abilix_utils_ProgramAndInterfaceC.txt`、`disasm_C_CCJ_Interface.txt`、`disasm_combined.txt`
  - `scan_ctrl_tty.txt`、`scan_ctrl_loadlib.txt`、`scan_ctrl_bind.txt`、`Controller_证据摘要.md`
- `_分析临时/brainApk分析/6F/`：`AndroidManifest.xml`、`assets_program_c_Robot.h`、`assets_program_c_libRobot.so`、`lib_armeabi-v7a_libRobot.so`、`lib_armeabi-v7a_libserial.so`、`assets_stm32_stm32.bin`、`assets_abilix_generators.js`
- `逆向资料/decompiled/Assembly-CSharp.decompiled.cs`（121,060 行）
- `逆向资料/xlua明文/`（约 500 个 .lua）

### 临时目录（本轮生成，可能被清理）
- `C:\Users\s1325\AppData\Local\Temp\wer_apk\`
  - `Ctrl6F.apk`、`dump_classes.py`、`scan_pc.py`
  - `disasm\Ctrl6F\`（92 + 15 个类）、`disasm\Setting\`（172 个类）、`disasm\Update\`（43 个类）
  - `AbilixSetting_25\`、`AbilixUpdate_1\`（原 APK 解包 + `manifest_decoded.xml`/`strings.txt`/`methods.txt`）

### 官方安装目录（只读）
- `D:\Program Files\AbilixScratch3.0\AbilixScratch3.0_Data\StreamingAssets\`
  - `adb\adb.exe`、`adb\AdbWinApi.dll`
  - `update\BlocklyC_V103.apk`
  - `standalonewindows\hot_update_dir\extenddatas\brainApk\6F\{AbilixSetting_25.apk, AbilixUpdate_1.apk, Controller_43.apk}`、`brainApkVersion.txt`
  - `pythoncompile\`、`SKCON9_User_Guide.pdf`

## 附录 B："未找到"清单（搜索过的路径与关键字）

| 关键字 | 搜索范围 | 结果 |
|---|---|---|
| `adb`, `adb.exe`, `adb shell` | `Assembly-CSharp.decompiled.cs`、全部 Managed/*.dll、`AbilixScratch3.0.exe`、xlua 明文、Controller/Setting/Update/BlocklyC dex+strings | 仅 `Constants.COMMANDEXEC` 1 处；无调用 |
| `tcpip`, `5555`, `5556` | 同上 | 0 |
| `pm install`, `PackageInstaller`, `installPackage` | 同上 | 0（安装走 grandar AIDL） |
| `logcat`, `push`, `pull` | PC C#/Lua | 0（App logger 用 logcat 类，但不是 adb） |
| `UsbDebugging`, `adb_enabled` 写, `adbd`, `ro.debuggable`, `serial console` | 4 个 APK 的 dex strings/methods + manifest | 仅 Setting `AdbEnabled()` 只读 1 处 |
| `telnet`, `busybox`, `su`, `superuser`, `Runtime.exec`, `ProcessBuilder`, `/system/bin/su` | 4 个 APK | 0 有效（`maybeSuperUser` 为 Netty 内部） |
| `sharedUserId` | Setting/Update/Controller manifest | 仅 Setting = `android.uid.system` |

## 附录 C：复现方法

1. 解包 APK：Python `zipfile`（仅 manifest/dex/assets/lib）。
2. 反编译 dex：`androguard 4.1.4` + `dump_classes.py`（`C:\Users\s1325\AppData\Local\Temp\wer_apk\dump_classes.py`），参数 `apk outdir 前缀...`，输出 smali 风格指令 + 字段。
3. Manifest：`AXMLPrinter(APK.get_android_manifest_axml().get_xml())`。
4. 证书：`APK.get_certificates()` → `subject.native`、`sha256`。
5. 反编译 C#：dnSpy/ILSpy 对 `Managed/Assembly-CSharp.dll`（已有 121,060 行文本）。
6. 二进制关键字：Python 定长切片扫描（不要用 `grep -a` 带 `.{0,N}` 正则扫 18MB exe，会超时）。

## 附录 D：待验证清单（按优先级）

1. **testkey 替换 Setting → system UID → 开 ADB**（Q2，收益最大）。
2. 8890 是否可从 PC 直连（无鉴权）→ 传 APK → cmd2=9 自动安装（Q3/Q6）。
3. 串口 55 55 11 握手 + 1M/937500 波特率实测（Q4）。
4. C 程序沙箱边界（socket/open/写 /sdcard）（Q5）。
5. 路径穿越/ZipSlip 实际落点（Q6）。
6. grandar 安装服务是否对第三方签名/新包名设白名单（Q3，决定"装自己的应用"是否可行）。
