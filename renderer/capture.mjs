import { chromium } from 'playwright';
import { createHash } from 'node:crypto';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { mkdir } from 'node:fs/promises';
import { startServer } from './server.mjs';
import { detect, activeIndex, selectReveal, slideHandle } from './adapters.mjs';

const PROJECT_TMP=fileURLToPath(new URL('../tmp/',import.meta.url));
async function prepareScratch() {
  await mkdir(PROJECT_TMP,{recursive:true});
  // Playwright creates its temporary Chrome profile via the Node process's os.tmpdir().
  Object.assign(process.env,{TEMP:PROJECT_TMP,TMP:PROJECT_TMP,TMPDIR:PROJECT_TMP});
}

export function launchOptions(config={}) {
  return {channel:'chrome',headless:true,timeout:20000,
    // Browser defaults include --no-sandbox; explicitly retain the Chrome sandbox.
    chromiumSandbox:true,
    ...(config.chromePath ? {executablePath:config.chromePath} : {})};
}

export async function checkChrome(config={}) {
  let browser;
  try {
    await prepareScratch();
    browser=await chromium.launch(launchOptions(config));
    const page=await bounded(browser.newPage(),20000,'создание вкладки Google Chrome');
    await page.setContent('<title>HTML Presentation Converter</title>');
    return {version:browser.version()};
  } catch (err) {
    throw new Error(`Для работы программы необходим Google Chrome. Установите его с https://www.google.com/chrome/ . Если Chrome уже установлен, проверьте политики запуска. Диагностика: ${err.message}`);
  } finally {await browser?.close();}
}

const bounded = async (promise, ms, label) => {
  let timer;
  try {return await Promise.race([promise,new Promise((_,reject)=>{timer=setTimeout(()=>reject(new Error(`Таймаут: ${label}`)),ms);})]);}
  finally {clearTimeout(timer);}
};

async function settle(page, target, config, content=target) {
  await target.scrollIntoViewIfNeeded({timeout:config.timeoutMs});
  await page.waitForTimeout(config.delayMs);
  await bounded(page.evaluate(async () => {
    await document.fonts.ready;
    for (const animation of document.getAnimations()) {
      const timing=animation.effect?.getComputedTiming();
      if (timing && Number.isFinite(timing.endTime)) {
        try {animation.finish();} catch {animation.pause();}
      } else animation.pause();
    }
    document.querySelectorAll('video,audio').forEach(media=>media.pause());
    // Lazy images on the current slide start loading after scrollIntoView.
  }), config.timeoutMs, 'шрифты и анимации');
  await bounded(content.evaluate(async el => {
    const images=[...(el.matches('img')?[el]:[]),...el.querySelectorAll('img')];
    await Promise.all(images.map(async im=>{
      if (!im.complete) await new Promise((resolve,reject)=>{
        im.addEventListener('load',resolve,{once:true});
        im.addEventListener('error',()=>reject(new Error(`Не загружено изображение: ${im.getAttribute('src')}`)),{once:true});
      });
      if (!im.naturalWidth) throw new Error(`Не загружено изображение: ${im.getAttribute('src')}`);
      await im.decode();
    }));
  }),config.timeoutMs,'изображения слайда');
  let previous='', stable=0;
  const end=Date.now()+config.timeoutMs;
  while (Date.now()<end) {
    const box=await target.boundingBox();
    if (!box || box.width<20 || box.height<20) throw new Error('Область слайда отсутствует или слишком мала.');
    const state=JSON.stringify(Object.values(box).map(n=>Math.round(n*10)));
    stable=state===previous ? stable+1 : 0;
    if (stable>=3) return;
    previous=state;
    await page.waitForTimeout(80);
  }
  throw new Error('Слайд не завершил переход. Увеличьте задержку или настройте навигацию вручную.');
}

export async function capture(input, emit=()=>{}, signal) {
  const config={width:1600,height:900,count:0,selector:'',captureSelector:'',nextKey:'ArrowRight',
    delayMs:500,timeoutMs:20000,allowExternal:false,...input};
  if (!Number.isInteger(config.count) || config.count<0 || config.count>500) throw new Error('Допустимо от 1 до 500 слайдов (0 — авто).');
  if (!Number.isInteger(config.width) || config.width<320 || config.width>3840 || !Number.isInteger(config.height) || config.height<240 || config.height>2160) throw new Error('Неверное разрешение.');
  if (!Number.isFinite(config.delayMs) || config.delayMs<0 || config.delayMs>10000 || !Number.isFinite(config.timeoutMs) || config.timeoutMs<1000 || config.timeoutMs>60000) throw new Error('Неверная задержка или таймаут.');
  let server,browser,context;
  const abort=()=>{void browser?.close().catch(()=>{});};
  signal?.addEventListener('abort',abort,{once:true});
  const cancelled=()=>{if(signal?.aborted) throw new Error('Конвертация отменена.');};
  try {
    cancelled();
    await prepareScratch();
    await mkdir(config.work,{recursive:true});
    server=await startServer(config.source);
    try {browser=await chromium.launch(launchOptions(config));}
    catch (err) {throw new Error(`Для работы программы необходим Google Chrome. Диагностика запуска: ${err.message}`);}
    cancelled();
    context=await browser.newContext({viewport:{width:config.width,height:config.height},
      acceptDownloads:false,serviceWorkers:'block',permissions:[],locale:'ru-RU'});
    const blocked=new Set(), missing=new Set(), pending=new Set();
    await context.route('**/*',async route=>{
      const request=route.request(), url=new URL(request.url());
      if (url.origin===server.origin || ['data:','blob:'].includes(url.protocol)) return route.continue();
      if (config.allowExternal && ['https:','http:'].includes(url.protocol)) return route.continue();
      blocked.add(url.origin);
      return route.abort('blockedbyclient');
    });
    // HTTP routing alone does not block WebSocket connections.
    await context.routeWebSocket('**/*',ws=>ws.close());
    context.on('page',popup=>{if(context.pages().length>1) void popup.close();});
    const page=await bounded(context.newPage(),config.timeoutMs,'создание вкладки Google Chrome');
    page.setDefaultTimeout(config.timeoutMs);
    let diagnostics=0;
    const diagnostic=message=>{if(diagnostics++<30) emit({type:'diagnostic',message:message.slice(0,1000)});};
    page.on('console',msg=>{if(msg.type()==='error') diagnostic(msg.text());});
    const critical=r=>['stylesheet','script','image','font'].includes(r.resourceType()) ||
      (['fetch','xhr'].includes(r.resourceType()) && new URL(r.url()).origin===server.origin);
    page.on('request',r=>{if(critical(r)) pending.add(r);});
    page.on('requestfinished',r=>pending.delete(r));
    page.on('requestfailed',r=>{pending.delete(r);if(critical(r)) missing.add(r.url());});
    page.on('response',res=>{if(res.status()>=400 && (critical(res.request()) || res.request().resourceType()==='document')) missing.add(res.url());});
    page.on('pageerror',err=>diagnostic(err.message));
    emit({type:'status',message:'Открытие HTML в Google Chrome'});
    await page.goto(server.url,{waitUntil:'load',timeout:config.timeoutMs});
    await page.waitForTimeout(config.delayMs);
    const resourceCheck=()=>{
      if (blocked.size) throw new Error(`Заблокированы внешние ресурсы: ${[...blocked].slice(0,5).join(', ')}. Разрешите внешние ресурсы в настройках, если доверяете презентации.`);
      if (missing.size) throw new Error(`Не удалось загрузить ресурсы: ${[...missing].slice(0,4).map(x=>decodeURI(x).replace(server.base,'')).join(', ')}. Проверьте файлы рядом с HTML.`);
    };
    resourceCheck();
    const deck=await detect(page,config);
    if (deck.count<1 || deck.count>500) throw new Error('Поддерживается от 1 до 500 слайдов.');
    if (config.count && config.count!==deck.count) throw new Error(`Найдено ${deck.count} слайдов вместо ${config.count}.`);
    if (deck.mode==='reveal' && deck.aspect && !config.captureSelector) {
      const h=Math.round(config.width/deck.aspect);
      if (h>=240 && h<=2160) await page.setViewportSize({width:config.width,height:h});
      await page.evaluate(()=>window.Reveal.layout());
    }
    emit({type:'detected',mode:deck.mode,total:deck.count});
    if (deck.mode==='navigation' && await activeIndex(page)!==0) {
      await page.keyboard.press('Home');
      await page.waitForTimeout(config.delayMs);
      if (await activeIndex(page)!==0) throw new Error('Не удалось открыть первый слайд. Сохраните презентацию с начальным слайдом или настройте навигацию вручную.');
    }
    const slides=[], hashes=new Set();
    for (let i=0;i<deck.count;i++) {
      cancelled();
      await bounded((async()=>{
        if (deck.mode==='reveal') await selectReveal(page,i);
        else if (i>0 && deck.mode!=='static') {
          await page.keyboard.press(config.nextKey);
          await page.waitForTimeout(config.delayMs);
        }
        if (deck.mode==='navigation') {
          // Wait for actual DOM identity, never infer success merely from a sent key.
          const deadline=Date.now()+config.timeoutMs;
          while (await activeIndex(page)!==i && Date.now()<deadline) await page.waitForTimeout(80);
          if (await activeIndex(page)!==i) throw new Error(`Нет перехода к слайду ${i+1} или навигация повторяется. Настройте CSS-селектор и клавишу вручную.`);
        }
        const target=await slideHandle(page,i,deck.mode,config.captureSelector);
        const content=deck.mode==='reveal' ? (await page.evaluateHandle(()=>window.Reveal.getCurrentSlide())).asElement() : target;
        try {await settle(page,target,config,content);}
        finally {if(content!==target) await content.dispose();}
        // Await critical CSS/background/font loads without hanging on analytics/network idle.
        const deadline=Date.now()+config.timeoutMs;
        while(pending.size && Date.now()<deadline) await page.waitForTimeout(80);
        if (pending.size) throw new Error('Таймаут загрузки ресурсов слайда.');
        resourceCheck();
        const file=path.resolve(config.work,`slide-${String(i+1).padStart(4,'0')}.png`);
        const buffer=await target.screenshot({path:file,type:'png',animations:'disabled',timeout:config.timeoutMs});
        const hash=createHash('sha256').update(buffer).digest('hex');
        if (deck.mode==='manual' && hashes.has(hash)) throw new Error(`Слайд ${i+1} повторяется: нет перехода или обнаружен цикл. Укажите селектор структурных слайдов, если они выглядят одинаково.`);
        hashes.add(hash);
        const box=await target.boundingBox();
        const text=await target.innerText().catch(()=> '');
        slides.push({index:i,file,width:Math.round(box.width),height:Math.round(box.height),hash,text:text.slice(0,500)});
        emit({type:'progress',current:i+1,total:deck.count,message:`Сохранён слайд ${i+1} из ${deck.count}`});
        if (target.dispose) await target.dispose();
      })(),config.timeoutMs*3+config.delayMs*2+2000,`слайд ${i+1}`);
    }
    cancelled();
    return {mode:deck.mode,slides,width:slides[0].width,height:slides[0].height,chrome:browser.version()};
  } finally {
    signal?.removeEventListener('abort',abort);
    await context?.close().catch(()=>{});
    await browser?.close().catch(()=>{});
    await server?.close();
  }
}
