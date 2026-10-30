// Browser-side analysis stays in JavaScript; no source documents are modified.
export async function detect(page, config) {
  if (await page.evaluate(() => !!window.Reveal?.getSlides)) {
    await page.waitForFunction(() => window.Reveal.isReady(), null, {timeout:config.timeoutMs});
    return page.evaluate(() => {
      const R = window.Reveal;
      R.configure({autoSlide:0, transition:'none', backgroundTransition:'none',
        controls:false, progress:false, slideNumber:false});
      R.toggleOverview(false);
      R.togglePause(false);
      const slides = R.getSlides().filter(el => el.dataset.visibility !== 'hidden');
      window.__hpcSlides = slides;
      const cfg = R.getConfig();
      return {mode:'reveal', count:slides.length,
        aspect:typeof cfg.width === 'number' && typeof cfg.height === 'number' ? cfg.width / cfg.height : null};
    });
  }
  return page.evaluate(({selector,count,captureSelector}) => {
    const visible = el => {
      if (!el || !el.getBoundingClientRect().width || !el.getBoundingClientRect().height) return false;
      for (let p=el; p; p=p.parentElement) {
        const css=getComputedStyle(p);
        if (css.display==='none' || css.visibility==='hidden' || Number(css.opacity)===0 || p.hidden) return false;
      }
      return true;
    };
    let elements=[];
    if (selector) {
      try {elements=[...document.querySelectorAll(selector)];}
      catch {throw new Error('Некорректный CSS-селектор слайдов.');}
      if (!elements.length) throw new Error('CSS-селектор не нашёл слайды. Проверьте ручные настройки.');
    } else {
      for (const candidate of ['[data-slide]', '.slide', '.presentation-slide', '.slide-page', '.slides > section', 'main > section']) {
        const found=[...document.querySelectorAll(candidate)];
        if (found.length) {elements=found;break;}
      }
    }
    if (elements.some(el=>elements.some(other=>other!==el && el.contains(other)))) {
      throw new Error('Найдены вложенные слайды. Укажите CSS-селектор отдельных слайдов в ручных настройках.');
    }
    if (!elements.length) {
      if (!count) throw new Error('Не удалось определить слайды. Откройте ручные настройки: количество, клавиша, CSS-селектор.');
      const target=captureSelector ? document.querySelector(captureSelector) : document.body;
      if (!target) throw new Error('Не найдена область захвата.');
      window.__hpcSlides=[];
      return {mode:'manual',count,aspect:null};
    }
    if (count && count!==elements.length) throw new Error(`Указано ${count} слайдов, CSS-селектор нашёл ${elements.length}.`);
    window.__hpcSlides=elements;
    const shown=elements.filter(visible);
    // Static decks show all slides without overlapping. Hidden/stacked decks need real navigation.
    const overlaps=shown.some((el,i)=>shown.slice(i+1).some(other=>{
      const a=el.getBoundingClientRect(), b=other.getBoundingClientRect();
      return Math.min(a.right,b.right)-Math.max(a.left,b.left)>10 && Math.min(a.bottom,b.bottom)-Math.max(a.top,b.top)>10;
    }));
    const mode=shown.length===elements.length && !overlaps ? 'static' : 'navigation';
    const first=shown[0]?.getBoundingClientRect();
    return {mode,count:elements.length,aspect:first ? first.width/first.height : null};
  }, config);
}

export async function activeIndex(page) {
  return page.evaluate(() => {
    const slides=window.__hpcSlides;
    const visible=slides.map((el,i)=>{
      const rect=el.getBoundingClientRect();
      if (rect.width<1 || rect.height<1) return null;
      for (let p=el;p;p=p.parentElement) {
        const s=getComputedStyle(p);
        if (p.hidden || s.display==='none' || s.visibility==='hidden' || Number(s.opacity)<0.01) return null;
      }
      const marked=el.matches('.active,.present,.current,[aria-current="true"],[data-active="true"]');
      const x=Math.max(0,Math.min(innerWidth-1,rect.x+rect.width/2));
      const y=Math.max(0,Math.min(innerHeight-1,rect.y+rect.height/2));
      const top=document.elementFromPoint(x,y);
      return {i,marked,painted:el===top || el.contains(top)};
    }).filter(Boolean);
    const marked=visible.filter(x=>x.marked);
    if (marked.length===1) return marked[0].i;
    const painted=visible.filter(x=>x.painted);
    if (painted.length===1) return painted[0].i;
    return visible.length===1 ? visible[0].i : -1;
  });
}

export async function selectReveal(page, index) {
  await page.evaluate(i => {
    const R=window.Reveal, slide=window.__hpcSlides[i], pos=R.getIndices(slide);
    R.slide(pos.h,pos.v,Number.MAX_SAFE_INTEGER);
    R.loadSlide(slide);
    R.navigateFragment(Number.MAX_SAFE_INTEGER);
  }, index);
  const actual=await page.evaluate(() => window.__hpcSlides.indexOf(window.Reveal.getCurrentSlide()));
  if (actual!==index) throw new Error(`Reveal.js не перешёл к слайду ${index+1}.`);
}

export async function slideHandle(page,index,mode,captureSelector) {
  if (captureSelector) {
    const locator=page.locator(captureSelector);
    if (await locator.count()!==1) throw new Error('Селектор области захвата должен находить ровно один элемент.');
    return locator;
  }
  if (mode==='reveal') return page.locator('.reveal');
  if (mode==='manual') return page.locator('body');
  const handle=await page.evaluateHandle(i=>window.__hpcSlides[i],index);
  return handle.asElement();
}
