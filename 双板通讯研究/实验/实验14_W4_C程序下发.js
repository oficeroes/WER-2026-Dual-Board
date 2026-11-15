#!/usr/bin/env node
/*
 * 实验14_W4_C程序下发.js -- 通过 8890 文件通道把 C 程序包（fileType=20）下发给机器人
 *
 * 协议依据（2026-11-11 静态逆向 + 真机实证）：
 *   1) 心跳 10086：cmd(0,2) 启动，cmd(0,4) 每 1s 一次；机器人回 160,4。
 *   2) 8890 文件传输：cmd(1,1) 请求 → 机器人回 160,1 允许 → cmd(1,3) 分块 → cmd(1,4) 结束
 *      → 机器人回 160,3 表示收完且 CRC 正确。
 *   3) fileType=20 触发机器人 ControllerService.handleProgramZip()：
 *      解压 → 在 DIR_PROGRAM 落库 → 若 fileType==20 则调 CompileUtil.compile() 用
 *      /system/xbin/gcc4.8.2 里的 arm-linux-androideabi-gcc 编译成 librobot_<name>.so。
 *
 * C 包结构（镜像 PY 的 <name>.py.zip / <name>.py/<name>.py）：
 *   zip 文件名 = <名字>.c.zip
 *   内部条目   = <名字>.c/<名字>.c
 *
 * 用法：
 *   node 实验14_W4_C程序下发.js [robotIp] [本地C文件] [程序名(不含.c)] [--extra <附加文件> ...]
 * 例：
 *   node 实验14_W4_C程序下发.js 192.168.1.103 实验14_W4_C探针/W4PROBE.c W4PROBE
 *   node 实验14_W4_C程序下发.js 192.168.47.199 实验17_性能压测/PERF_SERVER.c PERFSERVER --extra ../库/werlink.h
 *
 * --extra 可多次使用，把附加文件（如头文件库 werlink.h）一起塞进 <程序名>.c/ 目录，
 * 机器人端 gcc *.c 时从同目录 #include "werlink.h" 即可。
 *
 * 作者：DSH AI（2026-11-11，W4 实验）
 */
'use strict';

const fs = require('fs');
const path = require('path');
const zlib = require('zlib');

const WER_PROTO = path.join(__dirname, '..', '..', 'WER_VSCode_工具', 'vscode-extension', 'src', 'werProtocol.js');
const wer = require(WER_PROTO);

const ROBOT_TYPE_SKCON9 = 111;

function ts() {
  const d = new Date();
  const p = (n, w) => String(n).padStart(w || 2, '0');
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}:${p(d.getSeconds())}.${p(d.getMilliseconds(), 3)}`;
}
function log(level, msg) {
  console.log(`[${ts()}] [${level}] ${msg}`);
}

function dosDateTime(d) {
  const year = Math.max(1980, d.getFullYear());
  const dosTime = ((d.getHours() & 0x1F) << 11) | ((d.getMinutes() & 0x3F) << 5) | ((Math.floor(d.getSeconds() / 2)) & 0x1F);
  const dosDate = (((year - 1980) & 0x7F) << 9) | (((d.getMonth() + 1) & 0x0F) << 5) | (d.getDate() & 0x1F);
  return { dosTime, dosDate };
}

/** 与 werProtocol.buildProgramZip 相同的 zip 结构，只是目录名可自定义（支持 .c） */
function buildZip(dirName, entries) {
  const { dosTime, dosDate } = dosDateTime(new Date());
  const localParts = [];
  const centralParts = [];
  let offset = 0;

  for (const entry of entries) {
    const nameBuf = Buffer.from(entry.name, 'utf8');
    const crc = wer.crc32(entry.data);
    const compressed = zlib.deflateRawSync(entry.data, { level: 6 });

    const local = Buffer.alloc(30 + nameBuf.length);
    local.writeUInt32LE(0x04034b50, 0);
    local.writeUInt16LE(20, 4);
    local.writeUInt16LE(0x0000, 6);
    local.writeUInt16LE(8, 8);
    local.writeUInt16LE(dosTime, 10);
    local.writeUInt16LE(dosDate, 12);
    local.writeUInt32LE(crc, 14);
    local.writeUInt32LE(0xFFFFFFFF, 18);   // 与官方软件一致：本地头写 -1
    local.writeUInt32LE(entry.data.length >>> 0, 22);
    local.writeUInt16LE(nameBuf.length, 26);
    local.writeUInt16LE(0, 28);
    nameBuf.copy(local, 30);

    const central = Buffer.alloc(46 + nameBuf.length);
    central.writeUInt32LE(0x02014b50, 0);
    central.writeUInt16LE(0x0033, 4);
    central.writeUInt16LE(20, 6);
    central.writeUInt16LE(0x0000, 8);
    central.writeUInt16LE(8, 10);
    central.writeUInt16LE(dosTime, 12);
    central.writeUInt16LE(dosDate, 14);
    central.writeUInt32LE(crc, 16);
    central.writeUInt32LE(compressed.length >>> 0, 20);
    central.writeUInt32LE(entry.data.length >>> 0, 24);
    central.writeUInt16LE(nameBuf.length, 28);
    central.writeUInt16LE(0, 30);
    central.writeUInt16LE(0, 32);
    central.writeUInt16LE(0, 34);
    central.writeUInt16LE(0, 36);
    central.writeUInt32LE(0, 38);
    central.writeUInt32LE(offset, 42);
    nameBuf.copy(central, 46);

    localParts.push(local, compressed);
    centralParts.push(central);
    offset += local.length + compressed.length;
  }

  const centralBuf = Buffer.concat(centralParts);
  const eocd = Buffer.alloc(22);
  eocd.writeUInt32LE(0x06054b50, 0);
  eocd.writeUInt16LE(0, 4);
  eocd.writeUInt16LE(0, 6);
  eocd.writeUInt16LE(entries.length, 8);
  eocd.writeUInt16LE(entries.length, 10);
  eocd.writeUInt32LE(centralBuf.length, 12);
  eocd.writeUInt32LE(offset, 16);
  eocd.writeUInt16LE(0, 20);
  return Buffer.concat([...localParts, centralBuf, eocd]);
}

async function main() {
  const rawArgs = process.argv.slice(2);
  const extras = [];
  const pos = [];
  for (let i = 0; i < rawArgs.length; i++) {
    if (rawArgs[i] === '--extra' && rawArgs[i + 1]) {
      extras.push(path.resolve(rawArgs[++i]));
    } else {
      pos.push(rawArgs[i]);
    }
  }
  const ip = pos[0] || '192.168.1.103';
  const cPath = pos[1]
    ? path.resolve(pos[1])
    : path.join(__dirname, '实验14_W4_C探针', 'W4PROBE.c');
  const baseName = pos[2] || path.basename(cPath, '.c');

  if (!fs.existsSync(cPath)) {
    throw new Error(`C 源文件不存在: ${cPath}`);
  }
  const srcBuf = fs.readFileSync(cPath);
  const dirName = `${baseName}.c`;
  const remoteName = `${dirName}.zip`;
  const entries = [{ name: `${dirName}/${dirName}`, data: srcBuf }];
  for (const ex of extras) {
    if (!fs.existsSync(ex)) throw new Error(`附加文件不存在: ${ex}`);
    const exBuf = fs.readFileSync(ex);
    const exName = path.basename(ex);
    entries.push({ name: `${dirName}/${exName}`, data: exBuf });
    log('info', `附加文件: ${ex} (${exBuf.length} 字节) → ${dirName}/${exName}`);
  }
  const zipBuf = buildZip(dirName, entries);

  log('info', `C 源文件: ${cPath} (${srcBuf.length} 字节)`);
  log('info', `zip 包: ${remoteName} (${zipBuf.length} 字节), 共 ${entries.length} 个条目（首条目 ${dirName}/${dirName}）`);
  log('info', `目标机器人: ${ip}:10086(心跳) + ${ip}:8890(文件)`);

  const hb = new wer.HeartbeatClient({
    ip, robotType: ROBOT_TYPE_SKCON9, timeoutMs: 8000,
    log: (lvl, msg) => log(lvl, msg),
  });
  const ft = new wer.FileTransferClient({
    ip, robotType: ROBOT_TYPE_SKCON9,
    log: (lvl, msg) => log(lvl, msg),
  });

  let result;
  try {
    const hr = await hb.connect();
    log('info', `心跳成功，机器人类型 ${hr.robotType}，耗时 ${hr.latencyMs}ms`);

    await ft.connect();
    const started = Date.now();
    result = await ft.sendFile({
      fileBuffer: zipBuf,
      fileName: remoteName,
      appType: 3,          // AppType.Scratch（与 PY 下载一致，实测可用）
      fileType: 20,        // FileType_C → 机器人 handleProgramZip 里触发 gcc 编译
      chunkSize: 10240,
      progress: (p) => log('info', `进度 ${p.percent}% ${p.message}`),
      onStart: () => { hb.pause(); log('info', '机器人已允许传输，暂停心跳（与官方行为一致）'); },
      log: (lvl, msg) => log(lvl, msg),
    });
    result.ms = Date.now() - started;
    if (result.fileExists) {
      log('warning', '机器人上已存在相同 CRC 的文件，本次被跳过（160,7）');
    } else {
      log('info', `机器人已接收并校验通过（160,3），耗时 ${result.ms}ms`);
      log('info', '→ fileType=20 的后续动作：解压 + 落库 DIR_PROGRAM + 触发 gcc 编译（编译结果不通过协议返回）');
    }
  } finally {
    ft.close();
    hb.close();
  }

  console.log(JSON.stringify({
    ok: !!result && result.ok,
    remoteName,
    bytes: zipBuf.length,
    ms: result.ms,
    fileExists: !!result.fileExists,
    code: result.code,
    message: result.message,
  }, null, 2));
}

if (require.main === module) {
  main().catch((e) => {
    console.error('FAILED:', e && e.code ? `${e.code} ${e.message}` : e);
    console.error(e && e.stack ? e.stack : '');
    process.exit(1);
  });
}

module.exports = { buildZip, buildCZip: (baseName, cSourceBuffer, extraEntries = []) => {
  const dirName = `${baseName}.c`;
  const entries = [{ name: `${dirName}/${dirName}`, data: cSourceBuffer }].concat(extraEntries);
  return { zipBuf: buildZip(dirName, entries), remoteName: `${dirName}.zip` };
} };
