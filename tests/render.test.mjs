import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdtemp, rm, writeFile, cp } from 'node:fs/promises';
import path from 'node:path';
import http from 'node:http';
import { capture } from '../renderer/capture.mjs';

async function run(source, options={}) {
  const work = await mkdtemp(path.resolve('tmp/capture-'));
  try { return await capture({source:path.resolve(source), work, width:1000,height:600,
    delayMs:80,timeoutMs:5000,count:0,nextKey:'ArrowRight',...options}, ()=>{}); }
  finally { await rm(work, {recursive:true}); }
}

for (const [file, count, mode] of [['01-simple',3,'static'],['02-javascript',3,'navigation'],
  ['03-animation',3,'navigation'],['04-resources',3,'static'],['05-ratio',3,'static'],['06-reveal',4,'reveal']]) {
  test(`capture ${file}: exact order and identity`, async () => {
    const result = await run(`examples/${file}.html`);
    assert.equal(result.slides.length, count);
    assert.equal(result.mode, mode);
    assert.deepEqual(result.slides.map(s=>s.index),Array.from({length:count},(_,i)=>i));
    if (file === '05-ratio') assert.ok(Math.abs(result.width/result.height-4/3)<0.01);
    if (file === '06-reveal') {
      assert.match(result.slides[1].text, /Окончательное состояние/);
      assert.match(result.slides[2].text, /вертикальный B/);
    }
  });
}

test('stuck navigation fails rather than exporting repeated current slide', async () => {
  const root = await mkdtemp(path.resolve('tmp/stuck-'));
  const source = path.join(root,'index.html');
  await writeFile(source,'<style>.slide{width:800px;height:450px}</style><div class="slide">First</div><div class="slide" hidden>Second</div>');
  try { await assert.rejects(run(source), /переход|навигац/i); }
  finally {await rm(root,{recursive:true});}
});

test('structurally distinct identical slides are retained', async () => {
  const root = await mkdtemp(path.resolve('tmp/same-'));
  const source = path.join(root,'index.html');
  await writeFile(source,'<style>.slide{width:800px;height:450px;background:navy;color:white}</style><div class="slide">Same</div><div class="slide">Same</div>');
  try { assert.equal((await run(source)).slides.length,2); }
  finally {await rm(root,{recursive:true});}
});

test('unknown layout requests manual configuration', async () => {
  const root = await mkdtemp(path.resolve('tmp/unknown-'));
  const source = path.join(root,'index.html');
  await writeFile(source,'<h1>One unknown canvas</h1>');
  try {await assert.rejects(run(source), /ручн/i);}
  finally {await rm(root,{recursive:true});}
});

test('manual single-canvas deck follows configured key and detects a repeated frame', async () => {
  const root=await mkdtemp(path.resolve('tmp/manual-'));
  const source=path.join(root,'index.html');
  await writeFile(source,`<div id="canvas" style="width:800px;height:450px;background:navy;color:white;font-size:80px">Первый</div>
    <script>let n=0;document.addEventListener('keydown',e=>{if(e.code==='Space'){n++;document.getElementById('canvas').textContent=n===1?'Второй':'Третий'}})</script>`);
  try {
    const result=await run(source,{count:3,nextKey:'Space',captureSelector:'#canvas'});
    assert.equal(result.mode,'manual');
    assert.deepEqual(result.slides.map(s=>s.text),['Первый','Второй','Третий']);
    await assert.rejects(run(source,{count:4,nextKey:'Space',captureSelector:'#canvas'}),/повторяется/);
  } finally {await rm(root,{recursive:true});}
});

test('external resources are blocked with an actionable error', async () => {
  const root=await mkdtemp(path.resolve('tmp/external-'));
  const source=path.join(root,'index.html');
  await writeFile(source,'<link rel="stylesheet" href="https://example.invalid/theme.css"><div class="slide" style="width:800px;height:450px">External</div>');
  try {await assert.rejects(run(source),/Заблокированы внешние ресурсы/);}
  finally {await rm(root,{recursive:true});}
});

test('missing local fetch data fails instead of exporting placeholder content', async () => {
  const root=await mkdtemp(path.resolve('tmp/data-'));
  const source=path.join(root,'index.html');
  await writeFile(source,'<div class="slide" style="width:800px;height:450px">Loading chart...</div><script>fetch("missing.json").then(r=>r.json()).catch(()=>{})</script>');
  try {await assert.rejects(run(source),/ресурс/);}
  finally {await rm(root,{recursive:true});}
});

test('explicit external permission loads a requested script', async () => {
  const root=await mkdtemp(path.resolve('tmp/allowed-'));
  const source=path.join(root,'index.html');
  const server=http.createServer((req,res)=>{res.writeHead(200,{'Content-Type':'text/javascript'});res.end('document.querySelector(".slide").textContent="Внешний скрипт загружен";');});
  await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
  await writeFile(source,`<div class="slide" style="width:800px;height:450px">Waiting</div><script src="http://127.0.0.1:${server.address().port}/content.js"></script>`);
  try {assert.equal((await run(source,{allowExternal:true})).slides[0].text,'Внешний скрипт загружен');}
  finally {await new Promise(resolve=>{server.close(resolve);server.closeAllConnections();});await rm(root,{recursive:true});}
});

test('Reveal lazy image is validated only when its slide becomes current', async () => {
  const root=await mkdtemp(path.resolve('tmp/reveal-lazy-'));
  const source=path.join(root,'index.html');
  await cp(path.resolve('examples/assets'),path.join(root,'assets'),{recursive:true});
  await writeFile(source,`<link rel="stylesheet" href="assets/reveal/dist/reveal.css">
    <div class="reveal"><div class="slides"><section><h1>First</h1></section>
    <section><h1>Second</h1><img data-src="assets/diagram.svg"></section></div></div>
    <script src="assets/reveal/dist/reveal.js"></script><script>Reveal.initialize({viewDistance:0})</script>`);
  try {assert.equal((await run(source)).slides.length,2);}
  finally {await rm(root,{recursive:true});}
});
