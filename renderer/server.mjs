import http from 'node:http';
import { createReadStream } from 'node:fs';
import { realpath, stat } from 'node:fs/promises';
import { randomBytes } from 'node:crypto';
import path from 'node:path';

const MIME = {'.html':'text/html; charset=utf-8','.htm':'text/html; charset=utf-8',
  '.js':'text/javascript; charset=utf-8','.mjs':'text/javascript; charset=utf-8',
  '.css':'text/css; charset=utf-8','.svg':'image/svg+xml','.png':'image/png',
  '.jpg':'image/jpeg','.jpeg':'image/jpeg','.gif':'image/gif','.webp':'image/webp',
  '.woff':'font/woff','.woff2':'font/woff2','.ttf':'font/ttf','.json':'application/json',
  '.mp4':'video/mp4','.webm':'video/webm'};
const inside = (root, target) => {
  const relative = path.relative(root, target);
  return !relative.startsWith('..' + path.sep) && relative !== '..' && !path.isAbsolute(relative);
};

export async function startServer(source) {
  const entry = await realpath(source);
  const root = await realpath(path.dirname(source));
  if (!inside(root, entry)) throw new Error('Исходный файл — ссылка за пределы папки презентации.');
  const token = randomBytes(24).toString('hex');
  const server = http.createServer(async (req, res) => {
    const finish = code => {res.writeHead(code); res.end();};
    if (!['GET', 'HEAD'].includes(req.method)) return finish(405);
    try {
      // Inspect raw path before URL normalization to reject encoded traversal.
      const raw = decodeURIComponent(req.url.split('?')[0]);
      const prefix = '/' + token + '/';
      if (!raw.startsWith(prefix)) return finish(404);
      const relative = raw.slice(prefix.length);
      if (relative.includes('\0') || relative.includes('\\') || relative.split('/').includes('..') || relative.includes(':')) return finish(403);
      const target = path.resolve(root, relative);
      if (!inside(root, target)) return finish(403);
      const actual = await realpath(target);
      if (!inside(root, actual)) return finish(403);
      const info = await stat(actual);
      if (!info.isFile()) return finish(404);
      res.writeHead(200, {'Content-Type': MIME[path.extname(actual).toLowerCase()] || 'application/octet-stream',
        'Content-Length': info.size, 'Cache-Control':'no-store', 'X-Content-Type-Options':'nosniff',
        'Referrer-Policy':'no-referrer'});
      if (req.method === 'HEAD') return res.end();
      createReadStream(actual).on('error', () => res.destroy()).pipe(res);
    } catch (err) {finish(err instanceof URIError ? 400 : 404);}
  });
  await new Promise((resolve, reject) => {server.once('error',reject); server.listen(0, '127.0.0.1',resolve);});
  const origin = `http://127.0.0.1:${server.address().port}`;
  return {origin, base:`${origin}/${token}/`, url:`${origin}/${token}/${encodeURIComponent(path.basename(entry))}`,
    close: () => new Promise(resolve => {server.close(resolve); server.closeAllConnections();})};
}
