#!/usr/bin/env node
/*
 * deploy_program.js —— 兼容 .py / .c 的用户程序下发（8890 文件通道）
 *
 * 用法：
 *   node deploy_program.js <robotIp> <本地文件.py|.c> [程序名]
 * 例：
 *   node deploy_program.js 192.168.1.103 AICAMQR.py AICAMQR
 *
 * 依据：
 *   .py  appType=3, fileType=21, zip 内 <名字>.py/<名字>.py
 *   .c   appType=3, fileType=20, zip 内 <名字>.c/<名字>.c（机器人端 gcc 编译）
 */
'use strict';

const fs = require('fs');
const path = require('path');

const WER_PROTO = path.join(__dirname, '..', '..', '..', 'WER_VSCode_工具', 'vscode-extension', 'src', 'werProtocol.js');
const wer = require(WER_PROTO);
const { buildZip } = require(path.join(__dirname, '..', '实验14_W4_C程序下发.js'));

const ROBOT_TYPE_SKCON9 = 111;

function log(lvl, msg) {
  console.log(`[${lvl}] ${msg}`);
}

async function main() {
  const pos = process.argv.slice(2);
  const ip = pos[0] || '192.168.1.103';
  const file = path.resolve(pos[1] || 'AICAMQR.py');
  const ext = path.extname(file).toLowerCase();
  if (ext !== '.py' && ext !== '.c') throw new Error('只支持 .py 或 .c: ' + file);
  const baseName = pos[2] || path.basename(file, ext);

  const srcBuf = fs.readFileSync(file);
  const dirName = `${baseName}${ext}`;
  const remoteName = `${dirName}.zip`;
  const zipBuf = buildZip(dirName, [{ name: `${dirName}/${dirName}`, data: srcBuf }]);
  const fileType = ext === '.py' ? 21 : 20;

  log('info', `文件: ${file} (${srcBuf.length} 字节)`);
  log('info', `zip: ${remoteName} (${zipBuf.length} 字节) 条目 ${dirName}/${dirName}`);
  log('info', `appType=3 fileType=${fileType}  目标 ${ip}`);

  const hb = new wer.HeartbeatClient({ ip, robotType: ROBOT_TYPE_SKCON9, timeoutMs: 8000, log });
  const ft = new wer.FileTransferClient({ ip, robotType: ROBOT_TYPE_SKCON9, log });

  let result;
  try {
    const hr = await hb.connect();
    log('info', `心跳成功 robotType=${hr.robotType} ${hr.latencyMs}ms`);
    await ft.connect();
    result = await ft.sendFile({
      fileBuffer: zipBuf,
      fileName: remoteName,
      appType: 3,
      fileType,
      chunkSize: 10240,
      progress: (p) => log('info', `进度 ${p.percent}% ${p.message}`),
      onStart: () => { hb.pause(); log('info', '暂停心跳（传输期间）'); },
      log,
    });
    if (result.fileExists) log('warn', '机器人已有相同 CRC 的文件，本次跳过（160,7）');
    else log('info', `机器人已接收并校验通过（160,3）`);
  } finally {
    ft.close();
    hb.close();
  }

  console.log(JSON.stringify({
    ok: !!result && result.ok,
    remoteName,
    bytes: zipBuf.length,
    fileExists: !!result.fileExists,
    code: result.code,
    message: result.message,
  }, null, 2));
}

if (require.main === module) {
  main().catch((e) => {
    console.error('FAILED:', e && e.message ? e.message : e);
    process.exit(1);
  });
}
