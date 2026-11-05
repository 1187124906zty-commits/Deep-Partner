(() => {
  'use strict';
  if (window.__DT_DESKTOP_METRICS) return;
  const stats = window.__DT_DESKTOP_METRICS = { samples: [], interactions: 0, longTasks: 0, longTaskMs: 0, eventDurationMs: [], startedAt: performance.now() };
  const styleText = `
    :root { --dt-desktop-feedback: rgba(115, 96, 199, .09); }
    button, a, [role="button"], input, textarea, select { touch-action: manipulation; }
    button, a, [role="button"] { -webkit-tap-highlight-color: transparent; }
    button:not(:disabled), [role="button"]:not([aria-disabled="true"]) { cursor: pointer; }
    [data-dtd-pressed] { outline: 2px solid rgba(145,121,189,.35) !important; outline-offset: -2px; background-image: linear-gradient(var(--dt-desktop-feedback),var(--dt-desktop-feedback)) !important; }
    button:active:not(:disabled), [role="button"]:active { filter: brightness(.96); }
    @media(prefers-reduced-motion: reduce) { [data-dtd-pressed] { transition: none !important; } }
    #dt-navigation-feedback { position:fixed; top:0; left:0; right:0; height:2px; z-index:2147483646; background:#3c857b; transform:scaleX(0); transform-origin:left; transition:transform 120ms ease; pointer-events:none; }
    #dt-navigation-feedback[data-loading] {transform:scaleX(.7);}
  `;
  const mount = () => {
    if (document.getElementById('dt-desktop-style')) return;
    const style = document.createElement('style'); style.id='dt-desktop-style'; style.textContent=styleText; document.head.append(style);
    const bar=document.createElement('div');bar.id='dt-navigation-feedback';document.body.append(bar);
  };
  if (document.readyState==='loading') document.addEventListener('DOMContentLoaded',mount,{once:true}); else mount();
  let pressed=null, timer=null;
  const clear = () => { if (pressed) pressed.removeAttribute('data-dtd-pressed'); pressed=null; };
  document.addEventListener('pointerdown',event => {
    const target=event.target.closest('button,a,[role="button"]');
    if (!target || target.disabled || target.getAttribute('aria-disabled')==='true') return;
    clear(); pressed=target; target.setAttribute('data-dtd-pressed','');
    const start=performance.now();stats.interactions++;
    requestAnimationFrame(() => {stats.samples.push(performance.now()-start);if(stats.samples.length>200)stats.samples.shift();});
    if (timer) clearTimeout(timer);timer=setTimeout(clear,500);
  },{capture:true,passive:true});
  document.addEventListener('pointerup',() => setTimeout(clear,90),{capture:true,passive:true});
  document.addEventListener('pointercancel',clear,{capture:true,passive:true});
  document.addEventListener('click',event => {
    const a=event.target.closest('a[href]');
    if (!a || event.ctrlKey || event.metaKey || event.shiftKey || a.target==='_blank') return;
    const url=new URL(a.href,location.href);
    if(url.origin!==location.origin || url.pathname===location.pathname) return;
    const bar=document.getElementById('dt-navigation-feedback');if(!bar)return;
    bar.setAttribute('data-loading','');clearTimeout(bar._timeout);bar._timeout=setTimeout(()=>bar.removeAttribute('data-loading'),1600);
  },{capture:true,passive:true});
  try {new PerformanceObserver(list=>{for(const e of list.getEntries()){stats.longTasks++;stats.longTaskMs+=e.duration;}}).observe({type:'longtask',buffered:true});} catch {}
  try {new PerformanceObserver(list=>{for(const e of list.getEntries()){if(e.interactionId){stats.eventDurationMs.push(e.duration);if(stats.eventDurationMs.length>200)stats.eventDurationMs.shift();}}}).observe({type:'event',durationThreshold:16,buffered:true});} catch {}
})();
