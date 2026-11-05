(()=>{
const prefix=PREFIX,pid=PID;let activeDoc='',blocks=[],lastImage='';
let boundReader=null,lastStatus='',themeKey='';
function syncPalette(){
 try{
  const root=parent.document.documentElement,shared=getComputedStyle(root),local=document.documentElement;
  for(const key of ['--background','--foreground','--card','--card-foreground','--popover','--popover-foreground','--primary','--primary-foreground','--secondary','--secondary-foreground','--muted','--muted-foreground','--accent','--accent-foreground','--border','--input','--ring']){const value=shared.getPropertyValue(key);if(local.style.getPropertyValue(key)!==value)local.style.setProperty(key,value)}
  local.style.fontFamily=shared.fontFamily;
  const appTheme=root.dataset.tutorTheme||'snow',mode=['dark','glass'].includes(appTheme)?'dark':appTheme==='light'?'sepia':'light';
  const reader=window.__workbenchReader;
  if(reader&&themeKey!==appTheme){themeKey=appTheme;reader.setTheme({...reader.theme,appearance:mode,mode,pdfDarkImageMode:'preserve',pdfDarkContrast:'soft'});const colors={background:shared.getPropertyValue('--card').trim(),foreground:shared.getPropertyValue('--foreground').trim()};reader.viewer.pageColors=colors;reader.viewer.refresh(false,{pageColors:colors})}
 }catch{}
}
syncPalette();
try{new MutationObserver(syncPalette).observe(parent.document.documentElement,{attributes:true,attributeFilter:['class','data-tutor-theme']})}catch{}
function nativeButton(label){return Array.from(document.querySelectorAll('.neoread-toolbar button')).find(b=>b.getAttribute('aria-label')===label||b.textContent.trim()===label)}
function status(){
 const reader=window.__workbenchReader;
 if(reader&&boundReader!==reader){boundReader=reader;themeKey='';requestAnimationFrame(syncPalette);reader.bus?.on('pagesinit',()=>{themeKey='';syncPalette()});reader.bus?.on('scalechanging',()=>requestAnimationFrame(status));reader.bus?.on('pagechanging',()=>requestAnimationFrame(status))}
 const mode=Array.from(document.querySelectorAll('.neoread-toolbar [role="tab"]')).find(t=>t.getAttribute('aria-selected')==='true')?.textContent.trim();
 const value={mode,zoom:reader?.viewer.currentScale,page:reader?.viewer.currentPageNumber,navigation:nativeButton('目录与搜索')?.getAttribute('aria-expanded')==='true',assistant:nativeButton('Agent 与批注')?.getAttribute('aria-expanded')==='true'};
 const key=JSON.stringify(value);if(key!==lastStatus){lastStatus=key;parent.postMessage({type:'workbench:reader-state',project:pid,...value},location.origin)}
}
const documents=new Map();
const sourceFetch=window.fetch.bind(window);
window.addEventListener('message',event=>{
 if(event.origin===location.origin&&event.data?.type==='workbench:reader-command'&&event.data.project===pid){
  const {command,value}=event.data,reader=window.__workbenchReader;
  if(command==='navigation')nativeButton('目录与搜索')?.click();
  if(command==='assistant')nativeButton('Agent 与批注')?.click();
  if(command==='translate')nativeButton('翻译')?.click();
  if(command==='mode')Array.from(document.querySelectorAll('.neoread-toolbar [role="tab"]')).find(t=>t.textContent.trim()===value)?.click();
  if(command==='zoom'&&reader){if(value==='width'){reader.setTheme({...reader.theme,zoom:'width'});reader.events.zoom?.('width','manual')}else{const scale=value==='in'?reader.viewer.currentScale*1.15:value==='out'?reader.viewer.currentScale/1.15:Number(value);reader.zoomTo(scale);reader.events.zoom?.(scale,'manual')}}
  requestAnimationFrame(status);return;
 }
 if(event.origin!==location.origin||event.data?.type!=='workbench:locate'||event.data.project!==pid)return;
 const page=Number(event.data.locator?.page);if(!page)return;
 let attempt=0;const locate=()=>{const node=document.querySelector('.page[data-page-number="'+page+'"]');if(node){node.scrollIntoView({block:'center'});return}if(attempt++<25)setTimeout(locate,350)};locate();
});
window.fetch=async function(input,init){
 let url=typeof input==='string'?input:input instanceof URL?input.href:input?.url;
 if(typeof url!=='string')return sourceFetch(input,init);
 if(url.includes('/api/')){
  const at=url.indexOf('/api/');if(!url.includes('/research/reader/'))url=prefix+url.slice(at);
 }
 const result=await sourceFetch(typeof input==='string'||input instanceof URL?url:new Request(url,input),init);
 if(result.ok&&/\/api\/documents\/[^/]+\/blocks/.test(url)){
  const id=url.match(/\/documents\/([^/]+)\/blocks/)?.[1];
  result.clone().json().then(value=>{activeDoc=id||activeDoc;blocks=Array.isArray(value)?value:value.blocks||[];documents.set(activeDoc,blocks)}).catch(()=>{});
 }
 return result;
};
function emit(doc,block){if(!doc||!block)return;parent.postMessage({type:'workbench:figure-open',project:pid,document_id:doc,block_id:block},location.origin)}
document.addEventListener('pointermove',event=>{const block=event.target.closest?.('[data-block-id][data-block-kind="image"]');if(block)lastImage=block.dataset.blockId},true);
document.addEventListener('click',event=>{
 const action=event.target.closest?.('[data-block-action="preview"]');
 if(action){const host=action.closest('[data-block-id]');const id=host?.dataset.blockId||lastImage;if(id){event.preventDefault();event.stopImmediatePropagation();emit(activeDoc,id);return}}
 const image=event.target.closest?.('img');
 if(image){const match=image.src.match(/\/pub\/[^/]+\/([^/]+)\/assets\/(p\d+-b\d+)\.png/);if(match){event.preventDefault();event.stopImmediatePropagation();emit(match[1],match[2]);return}}
 if(event.target.closest?.('button,a,input,.neoread-selection-toolbar')||window.getSelection()?.toString().trim())return;
 const page=event.target.closest?.('.page[data-page-number]');if(!page)return;
 const rect=page.getBoundingClientRect(),x=(event.clientX-rect.left)/rect.width,y=(event.clientY-rect.top)/rect.height;
 const hit=blocks.find(b=>b.image&&b.page===Number(page.dataset.pageNumber)&&x>=b.bounds.x&&x<=b.bounds.x+b.bounds.width&&y>=b.bounds.y&&y<=b.bounds.y+b.bounds.height);
 if(hit){event.preventDefault();event.stopImmediatePropagation();emit(activeDoc,hit.id);return}
 // Plain clicks retain the page geometry. Native selection, double-click sentence
 // selection, annotations and links keep their own interactions.
 const text=blocks.find(b=>!b.image&&b.page===Number(page.dataset.pageNumber)&&x>=b.bounds.x&&x<=b.bounds.x+b.bounds.width&&y>=b.bounds.y&&y<=b.bounds.y+b.bounds.height);
 if(text&&!event.target.closest?.('.neoread-annotation,[data-annotation-id]')){event.stopImmediatePropagation();const focus=document.createElement('div');focus.className='wb-block-focus';Object.assign(focus.style,{left:text.bounds.x*100+'%',top:text.bounds.y*100+'%',width:text.bounds.width*100+'%',height:text.bounds.height*100+'%'});page.append(focus);setTimeout(()=>focus.remove(),1300)}
},true);
const closePreview=()=>{const dialog=document.querySelector('.image-preview-dialog');if(!dialog)return;const image=dialog.querySelector('img');const match=image?.src.match(/\/pub\/[^/]+\/([^/]+)\/assets\/(p\d+-b\d+)\.png/);if(match){emit(match[1],match[2]);const button=dialog.querySelector('[aria-label="Close"],[aria-label="关闭"],[data-slot="dialog-close"]');button?.click()}};
let scheduled=false;new MutationObserver(()=>{if(scheduled)return;scheduled=true;requestAnimationFrame(()=>{scheduled=false;closePreview();status()})}).observe(document.documentElement,{childList:true,subtree:true});
})();
