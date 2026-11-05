"""Read-only visual and latency checks against three existing research projects."""
from pathlib import Path
import argparse,json,os,sys,time
ROOT=Path(__file__).resolve().parents[1]
DIST=Path('D:/Development/research-workbench/unified-ui/dist')
sys.path.insert(0,str(ROOT/'.local/browser-qa'))
from playwright.sync_api import sync_playwright
from workspace_interactions_fixture import login,ORIGIN
from verify_workspace_interactions import static_candidate,geometry

CONTRAST=r"""()=>{
const parse=value=>{const values=value.match(/[\d.]+/g)?.map(Number);if(!values||values.length<3)return null;if(value.startsWith('color(srgb ')){for(let i=0;i<3;i++)values[i]*=255}return values},compose=(front,back)=>{const a=front[3]??1;return front.slice(0,3).map((v,i)=>v*a+back[i]*(1-a))},lum=color=>{const v=color.slice(0,3).map(x=>{x/=255;return x<=.04045?x/12.92:((x+.055)/1.055)**2.4});return .2126*v[0]+.7152*v[1]+.0722*v[2]},ratio=(a,b)=>{const l=[lum(a),lum(b)].sort((a,b)=>b-a);return(l[0]+.05)/(l[1]+.05)},background=el=>{const chain=[];for(let p=el;p;p=p.parentElement)chain.unshift(p);let out=[255,255,255];for(const p of chain){const c=parse(getComputedStyle(p).backgroundColor);if(c)out=compose(c,out)}return out};
const walker=document.createTreeWalker(document.querySelector('.dp-native-shell'),NodeFilter.SHOW_TEXT),bad=[];let node,count=0,min=100;
while(node=walker.nextNode()){const text=node.textContent.trim(),el=node.parentElement;if(!text||!el||!el.checkVisibility({checkVisibilityCSS:true,checkOpacity:true})||el.closest('button:disabled,[aria-disabled=true],svg,script,style'))continue;const rect=el.getBoundingClientRect(),style=getComputedStyle(el);if(!rect.width||!rect.height||rect.bottom<=0||rect.top>=innerHeight||rect.right<=0||rect.left>=innerWidth||style.visibility==='hidden')continue;const c=parse(style.color);if(!c)continue;let opacity=1;for(let p=el;p;p=p.parentElement)opacity*=Number(getComputedStyle(p).opacity);c[3]=(c[3]??1)*opacity;const bg=background(el),r=ratio(compose(c,bg),bg),size=parseFloat(style.fontSize),minimum=(size>=24||size>=18.66&&Number(style.fontWeight)>=700)?3:4.5;count++;min=Math.min(min,r);if(r<minimum-.01)bad.push({text:text.slice(0,65),ratio:r,minimum,color:style.color,background:bg,class:el.className})}
const css=getComputedStyle(document.documentElement);return {count,minimum_visible_ratio:min,low_contrast:bad,palette:Object.fromEntries(['--background','--foreground','--primary','--muted-foreground','--border'].map(k=>[k,css.getPropertyValue(k)]))}}
"""


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--published',action='store_true');args=parser.parse_args()
    mode='published' if args.published else 'candidate';report={'mode':mode,'checks':{},'errors':[],'themes':{},'timings':{},'model_calls':0}
    with sync_playwright() as p:
        browser=p.chromium.launch(executable_path='C:/Program Files/Google/Chrome/Application/chrome.exe',headless=True)
        ctx=browser.new_context(viewport={'width':1540,'height':1000},**({'proxy':{'server':os.environ['WORKBENCH_HTTP_PROXY']}} if os.environ.get('WORKBENCH_HTTP_PROXY') else {}))
        class Client:
            def post(self,path,json=None):
                r=ctx.request.post(ORIGIN+path,data=json,headers={'Origin':ORIGIN})
                class Result:
                    def raise_for_status(self):assert r.ok
                return Result()
        login(Client());projects=ctx.request.get(ORIGIN+'/research/api/projects').json()['projects'];project=next(p for p in projects if p['name']=='水分扩散')
        if not args.published:ctx.route(ORIGIN+'/research/**',static_candidate)
        page=ctx.new_page();page.on('pageerror',lambda e:report['errors'].append(str(e)))
        url=ORIGIN+'/research/?project='+project['id']+'&dt_workspace='+project['native_id']+'&area=literature'
        start=time.perf_counter();page.goto(url,wait_until='domcontentloaded');page.locator('.bibliography-table tbody tr').first.wait_for(timeout=60000);report['timings']['library_ready_seconds']=round(time.perf_counter()-start,3)
        for theme in ['snow','light','dark','glass']:
            page.evaluate("""theme=>{localStorage.setItem('deeptutor-theme',theme);const root=document.documentElement;root.classList.remove('dark','theme-snow','theme-glass');if(theme==='dark'||theme==='glass')root.classList.add('dark');if(theme==='glass')root.classList.add('theme-glass');if(theme==='snow')root.classList.add('theme-snow');root.dataset.tutorTheme=theme;window.dispatchEvent(new StorageEvent('storage',{key:'deeptutor-theme',newValue:theme}));}""",theme)
            page.wait_for_timeout(350);report['themes'][theme]=page.evaluate(CONTRAST)
            page.screenshot(path=str(ROOT/'reports/screenshots'/('restored-ui-'+mode+'-'+theme+'.png')))
        report['checks']['all_visible_text_meets_contrast']=all(not value['low_contrast'] for value in report['themes'].values())
        report['layout']=[]
        for area in ['literature','paper','figures','code','slides','questions']:
            page.goto(url.split('&area=')[0]+'&area='+area,wait_until='domcontentloaded');page.locator('.dp-artifacts').wait_for(timeout=45000);page.wait_for_timeout(500)
            for width,height in [(1540,1000),(1100,850),(900,800),(390,844)]:
                page.set_viewport_size({'width':width,'height':height});page.wait_for_timeout(100);value=geometry(page);value['area']=area;report['layout'].append(value)
        report['checks']['no_measured_layout_overlap_or_page_overflow']=all(not row['horizontal_page_overflow'] and not row['toolbar_overlaps'] and all(b['inside'] for b in row['attachment_actions']) for row in report['layout'])
        report['checks']['original_three_projects_preserved']=len(projects)==3
        report['checks']['no_script_errors']=not report['errors'];report['build']=json.loads((DIST/'build-info.json').read_text());report['passed']=all(report['checks'].values())
        (ROOT/'reports'/('restored-ui-'+mode+'.json')).write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8');print(json.dumps({'passed':report['passed'],'checks':report['checks'],'themes':{k:{'low_contrast':v['low_contrast'],'palette':v['palette']} for k,v in report['themes'].items()}},ensure_ascii=False));browser.close()


if __name__=='__main__':main()
