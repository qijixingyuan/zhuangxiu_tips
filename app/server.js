'use strict';

const crypto = require('crypto');
const fs = require('fs');
const http = require('http');
const path = require('path');
const { spawn } = require('child_process');

const host = process.env.RENOVATION_HOST || '127.0.0.1';
const port = Number(process.env.RENOVATION_PORT || 3188);
const dataRoot = process.env.RENOVATION_DATA_DIR || path.join(__dirname, 'data');
const databasePath = path.join(dataRoot, 'renovation.sqlite3');
const uploadRoot = path.join(dataRoot, 'uploads');
const dbHelper = path.join(__dirname, 'db.py');
const maxJsonSize = 2 * 1024 * 1024;
const maxImageSize = 12 * 1024 * 1024;

fs.mkdirSync(uploadRoot, { recursive: true });

function send(response, status, body, headers = {}) {
  response.writeHead(status, { 'Content-Type': 'application/json; charset=utf-8', 'Cache-Control': 'no-store', 'Access-Control-Allow-Origin': '*', ...headers });
  response.end(JSON.stringify(body));
}

function readBody(request, limit) {
  return new Promise((resolve, reject) => {
    const chunks = [];
    let size = 0;
    request.on('data', (chunk) => {
      size += chunk.length;
      if (size > limit) { reject(new Error('请求内容过大')); request.destroy(); return; }
      chunks.push(chunk);
    });
    request.on('end', () => resolve(Buffer.concat(chunks)));
    request.on('error', reject);
  });
}

function runDb(action, payload) {
  return new Promise((resolve, reject) => {
    const child = spawn('python3', [dbHelper, action, databasePath], { stdio: ['pipe', 'pipe', 'pipe'] });
    let out = '';
    let err = '';
    child.stdout.on('data', (chunk) => { out += chunk; });
    child.stderr.on('data', (chunk) => { err += chunk; });
    child.on('error', reject);
    child.on('close', (code) => {
      try {
        const parsed = JSON.parse(out || '{}');
        if (code !== 0 || parsed.error) reject(new Error(parsed.error || err || '数据库操作失败'));
        else resolve(parsed);
      } catch (_) { reject(new Error(err || '数据库响应格式错误')); }
    });
    child.stdin.end(action === 'put' ? JSON.stringify(payload) : '');
  });
}

function safeMime(value) {
  return ['image/jpeg', 'image/png', 'image/webp'].includes(value) ? value : '';
}

const server = http.createServer(async (request, response) => {
  try {
    const url = new URL(request.url, `http://${request.headers.host || 'localhost'}`);
    if (request.method === 'OPTIONS' && url.pathname.startsWith('/api/')) {
      response.writeHead(204, {'Access-Control-Allow-Origin':'*', 'Access-Control-Allow-Methods':'GET, POST, PUT, OPTIONS', 'Access-Control-Allow-Headers':'Content-Type'});
      return response.end();
    }
    if (request.method === 'GET' && url.pathname === '/api/health') return send(response, 200, { ok: true });
    if (request.method === 'GET' && url.pathname === '/api/state') return send(response, 200, await runDb('get'));
    if (request.method === 'PUT' && url.pathname === '/api/state') {
      if (!String(request.headers['content-type'] || '').startsWith('application/json')) return send(response, 415, { error: '需要 JSON 数据' });
      const body = await readBody(request, maxJsonSize);
      const result = await runDb('put', JSON.parse(body.toString('utf8')));
      return send(response, result.conflict ? 409 : 200, result);
    }
    if (request.method === 'POST' && url.pathname === '/api/uploads') {
      const mime = safeMime(String(request.headers['content-type'] || '').split(';')[0]);
      if (!mime) return send(response, 415, { error: '只支持 JPG、PNG 或 WebP 图片' });
      const body = await readBody(request, maxImageSize);
      if (!body.length) return send(response, 400, { error: '图片为空' });
      const extension = mime === 'image/png' ? 'png' : mime === 'image/webp' ? 'webp' : 'jpg';
      const id = `${Date.now()}-${crypto.randomBytes(10).toString('hex')}.${extension}`;
      const temporary = path.join(uploadRoot, `.${id}.tmp`);
      fs.writeFileSync(temporary, body, { mode: 0o644 });
      fs.renameSync(temporary, path.join(uploadRoot, id));
      return send(response, 201, { url: `/uploads/${id}` });
    }
    return send(response, 404, { error: '接口不存在' });
  } catch (error) {
    console.error(new Date().toISOString(), error.message);
    return send(response, 500, { error: error.message || '服务器处理失败' });
  }
});

server.listen(port, host, () => console.log(`renovation-api listening on http://${host}:${port}`));
