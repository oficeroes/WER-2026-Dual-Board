/* 实验18 机器人运行状态观察器：连 10086 心跳通道，打印每一帧原始数据。
 * 用途：心跳应答(160,4)的 11 字节 data 里第 1 个字节据逆向是 programState（程序是否在运行），
 * 在用户"运行/停止程序"时观察该字节变化，从 PC 侧判断程序到底有没有跑起来。
 * 用法：node 实验18_HB观察.js <robotIp> <seconds>
 */
const net = require('net');
const path = require('path');
const P = require(path.join(__dirname, '..', '..', '..', 'WER_VSCode_工具', 'vscode-extension', 'src', 'werProtocol.js'));

const ip = process.argv[2] || '192.168.1.103';
const secs = parseInt(process.argv[3] || '30', 10);
const robotType = 111;

function stamp() {
  const d = new Date();
  return d.toTimeString().slice(0, 8) + '.' + String(d.getMilliseconds()).padStart(3, '0');
}

const parser = new P.FrameParser((f) => {
  const hex = P.toHex ? P.toHex(f.data) : '';
  const bytes = f.data ? Array.from(f.data) : [];
  console.log(`[${stamp()}] type=${f.type} first=${f.first} second=${f.second} dataLen=${bytes.length} data=${hex} bytes=[${bytes.join(',')}]`);
}, { log: (lvl, msg) => console.log(`[parser] ${msg}`) });

const sock = net.createConnection({ host: ip, port: 10086 }, () => {
  console.log(`[${stamp()}] connected ${ip}:10086, send heartbeat start`);
  sock.write(P.buildHeartbeatStart(robotType));
});
let timer = null;
sock.on('connect', () => {
  timer = setInterval(() => {
    try { sock.write(P.buildHeartbeatTick(robotType)); } catch (e) { /* ignore */ }
  }, 1000);
});
sock.on('data', (c) => parser.push(c));
sock.on('error', (e) => console.log(`[${stamp()}] socket error: ${e.message}`));
sock.on('close', () => { console.log(`[${stamp()}] closed`); if (timer) clearInterval(timer); });
setTimeout(() => {
  if (timer) clearInterval(timer);
  try { sock.destroy(); } catch (e) { /* ignore */ }
  console.log('monitor done');
  process.exit(0);
}, secs * 1000);
