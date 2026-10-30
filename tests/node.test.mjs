import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdtemp, writeFile, rm, mkdir, symlink } from 'node:fs/promises';
import path from 'node:path';
import { startServer } from '../renderer/server.mjs';

test('loopback serves only token-authorized files inside the selected folder', async () => {
  const root = await mkdtemp(path.resolve('tmp/server-'));
  await writeFile(path.join(root, 'слайды.html'), '<h1>Привет</h1>');
  const server = await startServer(path.join(root, 'слайды.html'));
  try {
    const response = await fetch(server.url);
    assert.equal(response.status, 200);
    assert.match(await response.text(), /Привет/);
    assert.equal((await fetch(server.origin + '/missing')).status, 404);
    assert.equal((await fetch(server.base + '%2e%2e%2fpackage.json')).status, 403);
    assert.equal((await fetch(server.base + '%2e%2e%5cpackage.json')).status, 403);
    assert.equal((await fetch(server.url, {method: 'POST'})).status, 405);
  } finally { await server.close(); await rm(root, {recursive:true}); }
});

test('directory links cannot expose files outside presentation folder', async t => {
  const root=await mkdtemp(path.resolve('tmp/links-'));
  await mkdir(path.join(root,'deck'));
  await mkdir(path.join(root,'private'));
  await writeFile(path.join(root,'deck','index.html'),'<h1>Deck</h1>');
  await writeFile(path.join(root,'private','secret.txt'),'private-test-value');
  try {
    try {await symlink(path.join(root,'private'),path.join(root,'deck','linked'),'junction');}
    catch(e) {if(['EPERM','EACCES'].includes(e.code)) {t.skip('No permission for test directory junction');return;} throw e;}
    const server=await startServer(path.join(root,'deck','index.html'));
    try {assert.equal((await fetch(server.base+'linked/secret.txt')).status,403);}
    finally {await server.close();}
  } finally {await rm(root,{recursive:true});}
});
