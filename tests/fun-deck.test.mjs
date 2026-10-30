import test from 'node:test';
import assert from 'node:assert/strict';
import path from 'node:path';
import { mkdir } from 'node:fs/promises';
import { chromium } from 'playwright';
import { launchOptions, capture } from '../renderer/capture.mjs';
import { startServer } from '../renderer/server.mjs';

const source=path.resolve('examples/07-fun-lab.html');
const scratch=path.resolve('tmp');
Object.assign(process.env,{TEMP:scratch,TMP:scratch,TMPDIR:scratch});

test('offline fun deck: keyboard navigation, interactive controls and layout', async () => {
  await mkdir(scratch,{recursive:true});
  const server=await startServer(source);
  const browser=await chromium.launch(launchOptions());
  try {
    const context=await browser.newContext({viewport:{width:1600,height:900}});
    const page=await context.newPage();
    const errors=[];
    page.on('pageerror',err=>errors.push(err.message));
    await context.route('**/*',route=>new URL(route.request().url()).origin===server.origin ? route.continue() : route.abort());
    await page.goto(server.url);
    assert.equal(await page.locator('.slide').count(),9);
    assert.equal(await page.locator('.slide:visible').count(),1);
    await page.keyboard.press('ArrowRight');
    assert.equal(await page.locator('.slide:visible').getAttribute('id'),'s2');
    await page.keyboard.press('ArrowRight');
    const initial=await page.locator('#joke-text').innerText();
    await page.locator('#joke-next').click();
    assert.notEqual(await page.locator('#joke-text').innerText(),initial);
    await page.keyboard.press('ArrowRight');
    await page.locator('#coffee').focus();
    await page.keyboard.press('End');
    assert.equal(await page.locator('#coffee-value').innerText(),'100');
    assert.equal(await page.locator('.slide:visible').getAttribute('id'),'s4');
    await page.locator('#next').click();
    await page.locator('#bug').click();
    assert.equal(await page.locator('#bug-score').innerText(),'1');
    await page.locator('#next').click();
    await page.locator('#flip-card').click();
    assert.equal(await page.locator('#flip-card').getAttribute('aria-pressed'),'true');
    await page.locator('#next').click();
    await page.locator('[data-answer="commit"]').click();
    assert.match(await page.locator('#quiz-feedback').innerText(),/Верно/);
    await page.locator('#next').click();
    await page.locator('#panic-button').click();
    assert.match(await page.locator('#panic-status').innerText(),/главный/);
    await page.locator('#next').click();
    await page.locator('#party-button').click();
    assert.ok(await page.locator('.confetti-piece').count()>0);
    await page.locator('#restart').click();
    assert.equal(await page.locator('.slide:visible').getAttribute('id'),'s1');
    await page.keyboard.press('End');
    assert.equal(await page.locator('.slide:visible').getAttribute('id'),'s9');
    for(const size of [{width:1600,height:900},{width:1024,height:768},{width:390,height:844}]) {
      await page.setViewportSize(size);
      for(let i=0;i<9;i++) {
        await page.evaluate(i=>window.funDeck.goTo(i),i);
        await page.evaluate(()=>Promise.all(document.getAnimations().map(animation=>animation.finished.catch(()=>{}))));
        const overflow=await page.locator('.slide:visible').evaluate(el=>({
          x:el.scrollWidth>el.clientWidth+2,y:el.scrollHeight>el.clientHeight+2
        }));
        assert.deepEqual(overflow,{x:false,y:false},`overflow at slide ${i+1}, ${size.width}`);
      }
    }
    assert.deepEqual(errors,[]);
    await context.close();
  } finally {await browser.close();await server.close();}
});

test('converter captures all nine fun slides in order', async () => {
  const result=await capture({source,work:path.resolve('test-results/fun-deck/capture'),delayMs:80,timeoutMs:10000},()=>{});
  assert.equal(result.mode,'navigation');
  assert.equal(result.slides.length,9);
  assert.match(result.slides[0].text,/характер/);
  assert.match(result.slides[8].text,/выдыхать/);
  assert.equal(new Set(result.slides.map(s=>s.hash)).size,9);
});
