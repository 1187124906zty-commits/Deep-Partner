"""Actual browser acceptance for the requested workspace interactions."""
from pathlib import Path
from urllib.parse import unquote,urlparse
import argparse,json,mimetypes,sys,time
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'.local/browser-qa'))
from playwright.sync_api import sync_playwright
from workspace_interactions_fixture import login,CACHE,STATE,ORIGIN
DIST=Path('D:/Development/research-workbench/unified-ui/dist')
SHOTS=ROOT/'reports/screenshots';SHOTS.mkdir(exist_ok=True)

def static_candidate(route):
    relative=unquote(urlparse(route.request.url).path).removeprefix('/research/').strip('/')
    if not relative:target=DIST/'index.html'
    elif relative.startswith(('assets/','fonts/')) or relative=='build-info.json':
        target=(DIST/relative).resolve();assert target.is_relative_to(DIST.resolve())
    else:route.continue_();return
    if target.is_file():route.fulfill(status=200,body=target.read_bytes(),content_type=mimetypes.guess_type(target.name)[0] or 'application/octet-stream')
    else:route.fulfill(status=404,body='missing candidate asset')

def choose(page,label,value):
    page.get_by_role('button',name=label,exact=True).click()
    page.get_by_role('option',name=value,exact=True).click()

def selected_menu(page,selector):
    node=page.locator(selector).first;node.scroll_into_view_if_needed()
    node.evaluate("""el=>{const text=Array.from(el.childNodes).find(n=>n.nodeType===3)||el.firstChild;const range=document.createRange();range.selectNodeContents(el);const selection=getSelection();selection.removeAllRanges();selection.addRange(range);document.dispatchEvent(new Event('selectionchange'));}""")
    page.wait_for_timeout(250);box=node.bounding_box();page.mouse.click(box['x']+20,box['y']+12,button='right')
    page.get_by_role('menu',name='选文操作').wait_for()

def shot(page,report,name):
    path=SHOTS/('workspace-interactions-'+name+'.png');page.screenshot(path=str(path));report.setdefault('screenshots',[]).append(str(path));return path


def geometry(page):
    return page.evaluate("""()=>{
 const visible=el=>{const r=el.getBoundingClientRect(),s=getComputedStyle(el);return r.width>0&&r.height>0&&s.visibility!=='hidden'&&r.bottom>0&&r.top<innerHeight},rect=el=>{const r=el.getBoundingClientRect();return {x:r.x,y:r.y,width:r.width,height:r.height,right:r.right,bottom:r.bottom}},overlaps=[];
 for(const bar of document.querySelectorAll('.reading-toolbar,.quiet-paper-toolbar,.adapted-reader-toolbar,.bibliography-count,.image-tools,.dp-workspace-header,.task-center-heading,.manuscript-export-actions')){
  const children=Array.from(bar.children).filter(el=>visible(el)&&!el.classList.contains('toolbar-spacer'));
  for(let i=0;i<children.length;i++)for(let j=i+1;j<children.length;j++){const a=rect(children[i]),b=rect(children[j]);if(Math.min(a.right,b.right)-Math.max(a.x,b.x)>1&&Math.min(a.bottom,b.bottom)-Math.max(a.y,b.y)>1)overlaps.push({bar:bar.className,first:children[i].textContent.slice(0,45),second:children[j].textContent.slice(0,45),a,b});}
 }
 const attachmentActions=Array.from(document.querySelectorAll('.bibliography-table tbody tr')).flatMap(row=>{const cell=row.lastElementChild,button=cell.querySelector('.bibliography-read,.bibliography-download');if(!button)return [];const c=rect(cell),b=rect(button);return [{title:row.children[1].textContent.slice(0,65),cell:c,button:b,inside:b.x>=c.x-1&&b.right<=c.right+1&&b.y>=c.y-1&&b.bottom<=c.bottom+1}]});
 const popups=Array.from(document.querySelectorAll('.selection-context-menu,.dp-select-popover,.task-center,.modal')).filter(visible).map(el=>{const r=rect(el);return {class:el.className,rect:r,inside:r.x>=-1&&r.y>=-1&&r.right<=innerWidth+1&&r.bottom<=innerHeight+1}});
 return {viewport:{width:innerWidth,height:innerHeight},horizontal_page_overflow:document.documentElement.scrollWidth>innerWidth,toolbar_overlaps:overlaps,attachment_actions:attachmentActions,popups};}""")

def run_library(ctx,page,prefix,report):
    page.locator('.bibliography-table tbody tr').first.wait_for(timeout=45000)
    assert page.get_by_role('button',name='稿件导出',exact=True).count()==0
    assert page.get_by_role('button',name='搜索并下载',exact=True).count()==0
    report['checks']['library_has_import_and_direct_download_without_manuscript_preview']=True
    if page.locator('.bibliography-checkbox input:enabled').count()==2:
        page.get_by_label('全选待下载文献',exact=True).check()
        count=page.locator('.bibliography-checkbox input:checked').count();assert count==2,count
        with page.expect_response(lambda r:r.request.method=='POST' and '/literature/download-batch' in r.url,timeout=45000) as submitted:
            page.get_by_role('button',name='下载所选全文',exact=False).click()
        response=submitted.value;value=response.json();assert response.ok,value
        report['download_request']=value;report['checks']['two_selected_references_create_real_download_tasks']=True
    else:
        jobs=ctx.request.get(ORIGIN+prefix+'/jobs').json()['jobs'];downloads=[j for j in jobs if j['kind']=='literature-download']
        assert len(downloads)==2
        report['download_jobs']=[{k:j.get(k) for k in ('id','status','task','result')} for j in downloads]
        report['checks']['two_selected_references_create_real_download_tasks']=all(j.get('tracking') or j.get('task') for j in downloads)
    data=(CACHE/'reader-interaction-fixture.pdf').read_bytes()
    transfer=page.evaluate_handle("""bytes=>{const transfer=new DataTransfer();transfer.items.add(new File([new Uint8Array(bytes)],'reader-interaction-fixture.pdf',{type:'application/pdf'}));return transfer}""",list(data))
    page.locator('.library-dropzone').dispatch_event('dragenter',{'dataTransfer':transfer})
    page.get_by_text('松开以导入文献',exact=True).wait_for()
    with page.expect_response(lambda r:r.request.method=='POST' and r.url.endswith('/attachments'),timeout=180000) as uploaded:
        page.locator('.library-dropzone').dispatch_event('drop',{'dataTransfer':transfer})
    response=uploaded.value;result=response.json();assert response.ok,result
    report['upload']={'saved':result.get('saved'),'indexing':result.get('knowledge') or result.get('task')}
    page.get_by_role('button',name='刷新文献',exact=True).click()
    page.locator('.bibliography-table tbody tr').filter(has_text='Reader interaction verification').first.wait_for(timeout=60000)
    report['checks']['drag_and_drop_imports_the_actual_pdf']=True
    project=next(p for p in ctx.request.get(ORIGIN+'/research/api/projects').json()['projects'] if p['id']==prefix.split('/')[-1])
    sources=ctx.request.get(ORIGIN+prefix+'/knowledge/sources').json()['items'];kid=project['config']['attachment_knowledge_base'];original=next(row for row in sources if row['id']==kid)
    page.locator('.knowledge-sources>summary').click()
    page.get_by_role('button',name='重命名 '+original['name'],exact=True).click()
    page.get_by_label('知识库名称',exact=True).fill('阅读交互验收资料')
    with page.expect_response(lambda r:r.request.method=='PATCH' and '/knowledge/sources/' in r.url) as renamed:page.get_by_role('button',name='保存知识库名称',exact=True).click()
    assert renamed.value.ok
    updated=ctx.request.get(ORIGIN+prefix+'/knowledge/sources').json()['items'];assert next(row for row in updated if row['id']==kid)['name']=='阅读交互验收资料'
    page.locator('.knowledge-source-list article label>span').filter(has_text='阅读交互验收资料').wait_for(timeout=20000)
    report['knowledge_rename']={'id':kid,'before':original['name'],'after':'阅读交互验收资料'};report['checks']['knowledge_rename_preserves_the_same_resource_id']=True
    report['checks']['bibliography_authors_are_separate_rows']=page.locator('.author-names>span').count()>=4
    shot(page,report,'library')

def run_manuscript(ctx,page,prefix,report):
    page.get_by_label('论文正文',exact=True).wait_for(timeout=45000);page.get_by_label('译文正文',exact=True).wait_for()
    assert page.get_by_role('button',name='问 Agent',exact=True).count()==0
    selected_menu(page,'.source-pane .manuscript-editor p:nth-of-type(5)')
    assert page.get_by_role('menuitem',name='插入图片',exact=True).count()==0
    page.get_by_role('menuitem',name='黄色高亮',exact=True).click()
    page.locator('.source-pane mark[data-annotation-id]').wait_for(timeout=15000)
    selected_menu(page,'.translation-pane .manuscript-editor p:nth-of-type(5)')
    page.get_by_role('menuitem',name='蓝色高亮',exact=True).click();page.locator('.translation-pane mark[data-annotation-id]').wait_for(timeout=15000)
    selected_menu(page,'.source-pane .manuscript-editor p:nth-of-type(6)')
    page.get_by_role('menuitem',name='写批注',exact=True).click();page.get_by_label('批注问题',exact=True).fill('这条批注验证选文与稿件位置的保存。')
    page.get_by_role('button',name='记录问题',exact=True).click();page.get_by_role('dialog',name='批注',exact=True).wait_for(state='hidden')
    page.locator('.quiet-save').click();page.wait_for_function("document.querySelector('.quiet-save')?.textContent==='已保存'",timeout=30000)
    doc=ctx.request.get(ORIGIN+prefix+'/manuscript').json()
    report['checks']['source_and_translation_highlights_are_saved']=('annotationHighlight' in json.dumps(doc['content']) and 'annotationHighlight' in json.dumps(doc['translation']['content']))
    notes=ctx.request.get(ORIGIN+prefix+'/annotations?area=paper&asset=manuscript%2Fmain.json').json()
    report['checks']['selected_text_note_is_persisted']='这条批注验证选文与稿件位置的保存。' in json.dumps(notes,ensure_ascii=False)
    alignment=page.evaluate("""async()=>{const source=document.querySelector('.paper-scroll'),target=document.querySelector('.translation-scroll'),a=source.querySelector('.manuscript-editor').children[10];source.scrollTop+=a.getBoundingClientRect().top-source.getBoundingClientRect().top-24;source.dispatchEvent(new Event('scroll'));await new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)));const b=target.querySelector('.manuscript-editor').children[10];return {sourceTop:a.getBoundingClientRect().top-source.getBoundingClientRect().top,targetTop:b.getBoundingClientRect().top-target.getBoundingClientRect().top,sourceScroll:source.scrollTop,targetScroll:target.scrollTop}}""")
    report['bilingual_alignment']=alignment
    if abs(alignment['sourceTop']-alignment['targetTop'])>3:
        report['scroll_geometry']=page.locator('.paper-scroll').evaluate("el=>{const rows=[];while(el){const s=getComputedStyle(el);rows.push({tag:el.tagName,class:el.className,h:el.clientHeight,scroll:el.scrollHeight,height:s.height,min:s.minHeight,display:s.display,overflow:s.overflow,flex:s.flex});el=el.parentElement}return rows}")
        print(json.dumps(report['scroll_geometry']),flush=True)
    assert abs(alignment['sourceTop']-alignment['targetTop'])<=3,alignment
    report['checks']['bilingual_scroll_aligns_corresponding_paragraphs']=True;shot(page,report,'manuscript')
    selected_menu(page,'.source-pane .manuscript-editor p:nth-of-type(7)');page.get_by_role('menuitem',name='问 Dito',exact=True).click()
    page.wait_for_function("document.querySelector('.dp-native-shell')?.classList.contains('dp-surface-split')")
    page.locator('.dp-dito-location').wait_for(timeout=30000);report['checks']['selection_asks_the_existing_dito']=True
    # Reload into the manuscript alone before checking its export planner.
    page.goto(page.url.replace('area=paper','area=paper'),wait_until='domcontentloaded');page.get_by_role('button',name='稿件导出',exact=True).click()
    page.locator('.manuscript-export-planner').wait_for()
    page.locator('.export-template-list article').nth(1).wait_for(timeout=30000);assert page.locator('.export-template-list article').count()==2
    report['checks']['only_two_primary_word_templates_are_offered']=True
    for index,total in [(0,4),(1,10)]:
        page.get_by_role('button',name='预览模板全文',exact=True).nth(index).click()
        page.wait_for_function("n=>document.querySelector('input[aria-label=\"预览页码\"]')?.max===String(n) && Array.from(document.querySelectorAll('.template-pdf-container canvas')).some(c=>c.width>100)",arg=total,timeout=60000)
        page.get_by_label('预览页码',exact=True).fill(str(total));page.get_by_label('预览页码',exact=True).press('Tab')
        page.wait_for_function("n=>document.querySelector('input[aria-label=\"预览页码\"]')?.value===String(n)",arg=total)
    report['checks']['original_template_preview_contains_all_four_and_ten_pages']=True
    page.locator('.export-template-choice').first.click()
    with page.expect_response(lambda r:r.request.method=='POST' and '/manuscript/export' in r.url,timeout=30000) as submitted:page.get_by_role('button',name='预览稿件',exact=True).click()
    result=submitted.value.json();assert submitted.value.ok,result;report['manuscript_preview_job']=result['job_id']
    page.get_by_role('region',name='稿件预览',exact=True).wait_for(timeout=180000) if page.get_by_role('region',name='稿件预览',exact=True).count() else page.wait_for_function("document.querySelector('.template-pdf-preview>header>strong')?.textContent==='稿件预览'",timeout=180000)
    page.wait_for_function("Array.from(document.querySelectorAll('.template-pdf-container canvas')).some(c=>c.width>100)",timeout=45000)
    report['checks']['current_manuscript_preview_is_generated_and_paints']=True;shot(page,report,'export')

def run_canvas(ctx,page,prefix,report):
    # A real lexical retrieval receipt supplies a causal edge in the canvas.
    response=ctx.request.post(ORIGIN+prefix+'/knowledge/search',data={'query':'diffusion','mode':'fulltext-keyword','limit':3});assert response.ok,response.text()
    report['retrieval']=response.json()
    page.reload(wait_until='domcontentloaded');page.locator('.project-canvas-page').wait_for(timeout=45000)
    page.wait_for_function("document.querySelector('.project-canvas-graph canvas') && document.querySelector('.canvas-outline button')",timeout=45000)
    page.get_by_role('navigation',name='画布节点').get_by_role('button',name='最近检索',exact=False).click()
    page.locator('.canvas-record-list button').filter(has_text='diffusion').first.click()
    assert 'diffusion' in page.get_by_label('节点详情',exact=True).inner_text()
    report['checks']['canvas_shows_an_actual_project_retrieval']=True
    page.get_by_role('button',name='账户共享记忆',exact=True).click()
    page.get_by_role('navigation',name='画布节点').get_by_role('button',name='分项记忆',exact=False).click()
    assert '账户共享' in page.get_by_label('节点详情',exact=True).inner_text()
    report['checks']['canvas_labels_the_actual_account_memory_scope']=True;shot(page,report,'canvas')


def run_reader(ctx,page,prefix,report):
    file=CACHE/'reader-synchronized-fixture.pdf';assert file.is_file()
    existing=ctx.request.get(ORIGIN+prefix+'/literature/items').json()['files']
    if not any('Reader synchronized reading verification'==row.get('metadata',{}).get('title') for row in existing):
        response=ctx.request.post(ORIGIN+prefix+'/attachments',multipart={'files':{'name':file.name,'mimeType':'application/pdf','buffer':file.read_bytes()}},timeout=180000);assert response.ok,response.text()
    page.reload(wait_until='domcontentloaded')
    row=page.locator('.bibliography-table tbody tr').filter(has_text='Reader synchronized reading verification')
    with page.expect_response(lambda r:r.request.method=='POST' and r.url.endswith('/reader'),timeout=60000) as opened:row.get_by_role('button',name='阅读全文',exact=True).click()
    reader=opened.value.json();assert opened.value.ok,reader
    page.wait_for_function("document.querySelector('.reader-page-control input')?.max==='2' && Array.from(document.querySelectorAll('.local-pdf-container canvas')).some(c=>c.width>100)",timeout=60000)
    route='/research/reader/'+prefix.split('/')[-1]+'/api/documents/'+reader['document_id']
    deadline=time.monotonic()+150;blocks=[]
    while time.monotonic()<deadline:
        response=ctx.request.get(ORIGIN+route+'/blocks');blocks=response.json() if response.ok else []
        if blocks:break
        page.wait_for_timeout(1000)
    assert blocks,'PDF blocks are not ready'
    response=ctx.request.put(ORIGIN+route+'/translation-options',data={'targetLanguage':'zh-CN'});assert response.ok,response.text()
    current=ctx.request.get(ORIGIN+route+'/translations').json()
    if not current or any(row.get('status')!='complete' for row in current):
        with page.expect_response(lambda r:r.request.method=='POST' and r.url.endswith('/translations'),timeout=45000) as translating:page.get_by_role('button',name='翻译全文',exact=True).click()
        assert translating.value.ok,translating.value.text();report['real_pdf_translation_requested']=True
        deadline=time.monotonic()+180
        while time.monotonic()<deadline:
            current=ctx.request.get(ORIGIN+route+'/translations').json()
            if current and all(row.get('status')=='complete' for row in current):break
            page.wait_for_timeout(1200)
    assert current and all(row.get('status')=='complete' for row in current),current
    choose(page,'阅读模式','双语对照')
    page.wait_for_function("document.querySelector('.local-translation')?.textContent.includes('扩散')",timeout=30000)
    assert page.locator('.local-source').is_visible() and page.locator('.local-translation').is_visible()
    report['reader']={'document_id':reader['document_id'],'pages':2,'source_blocks':len(blocks),'completed_translation_blocks':len(current),'target_language':'zh-CN','real_service_output':True}
    report['checks']['neoread_real_translation_is_available_bilingually']=True
    selected_menu(page,'.local-pdf-container .textLayer span')
    page.get_by_role('menuitem',name='黄色高亮',exact=True).click();page.locator('.workbench-pdf-highlights span').first.wait_for(timeout=15000)
    selected_menu(page,'.local-translation .translation-blocks article>span')
    page.get_by_role('menuitem',name='粉色高亮',exact=True).click()
    selected_menu(page,'.local-translation .translation-blocks article>span')
    page.get_by_role('menuitem',name='写批注',exact=True).click();page.get_by_label('批注内容',exact=True).fill('译文批注应保留对应的文本块和页码。')
    with page.expect_response(lambda r:r.request.method=='POST' and r.url.endswith('/annotations'),timeout=30000) as saved:page.get_by_role('button',name='保存批注',exact=True).click()
    assert saved.value.ok,saved.value.text()
    notes=ctx.request.get(ORIGIN+prefix+'/annotations?area=literature').json()
    report['checks']['reader_original_and_translation_annotations_are_persisted']='译文批注应保留对应的文本块和页码。' in json.dumps(notes,ensure_ascii=False) and 'translation' in json.dumps(notes)
    shot(page,report,'reader-bilingual');report['reader_geometry']=geometry(page)
    page.get_by_role('button',name='收起审阅侧栏',exact=True).click()
    alignment=page.evaluate("""async()=>{const target=document.querySelector('.local-translation'),item=Array.from(target.querySelectorAll('[data-block]')).find(el=>el.querySelector('small')?.textContent==='第 2 页');target.scrollTop+=item.getBoundingClientRect().top-target.getBoundingClientRect().top-48;target.dispatchEvent(new Event('scroll'));await new Promise(r=>setTimeout(r,350));return {sourcePage:Number(document.querySelector('.reader-page-control input').value),targetBlock:item.dataset.block,sourceScroll:document.querySelector('.local-pdf-container').scrollTop,targetScroll:target.scrollTop}}""")
    report['reader_alignment']=alignment;report['checks']['reader_translation_scroll_moves_to_matching_source_page']=alignment['sourcePage']==2 and alignment['sourceScroll']>0
    choose(page,'阅读模式','中文译文');assert not page.locator('.local-source').is_visible();assert page.locator('.local-translation').is_visible()
    choose(page,'阅读模式','原文');assert page.locator('.local-source').is_visible();assert page.locator('.local-translation').count()==0
    report['checks']['reader_supports_either_monolingual_view']=True
    report['checks']['literature_reader_has_no_manuscript_export_planner']=page.get_by_role('button',name='稿件导出',exact=True).count()==0


def run_layout(ctx,page,prefix,report):
    results=[];initial=page.url
    for area in ['literature','paper','code','figures','slides','questions']:
        url=initial.split('&area=')[0]+'&area='+area;page.goto(url,wait_until='domcontentloaded')
        page.locator('.dp-artifacts').wait_for();page.wait_for_timeout(1800)
        for width,height in [(1540,1000),(1100,850),(900,800),(390,844)]:
            page.set_viewport_size({'width':width,'height':height});page.wait_for_timeout(250)
            measured=geometry(page);measured['area']=area;results.append(measured)
            if measured['toolbar_overlaps'] or measured['horizontal_page_overflow'] or any(not item['inside'] for item in measured['attachment_actions']):shot(page,report,'layout-'+area+'-'+str(width))
    report['layout']=results
    report['checks']['six_workspace_pages_have_no_toolbar_overlap']=all(not row['toolbar_overlaps'] for row in results)
    report['checks']['attachment_actions_stay_inside_their_table_cells']=all(all(item['inside'] for item in row['attachment_actions']) for row in results)
    report['checks']['six_workspace_pages_have_no_horizontal_page_overflow']=all(not row['horizontal_page_overflow'] for row in results)


def run_themes(ctx,page,prefix,report):
    page.locator('.bibliography-table').wait_for(timeout=45000)
    page.locator('.knowledge-sources').evaluate('el=>el.open=true')
    values={}
    for theme in ['snow','light','dark','glass']:
        page.evaluate("""theme=>{localStorage.setItem('deeptutor-theme',theme);const root=document.documentElement;root.classList.remove('dark','theme-snow','theme-glass');if(theme==='dark'||theme==='glass')root.classList.add('dark');if(theme==='glass')root.classList.add('theme-glass');if(theme==='snow')root.classList.add('theme-snow');root.dataset.tutorTheme=theme;window.dispatchEvent(new StorageEvent('storage',{key:'deeptutor-theme',newValue:theme}));}""",theme)
        page.wait_for_timeout(500)
        value=page.evaluate("""()=>{
 const css=getComputedStyle(document.documentElement),rgb=value=>{const node=document.createElement('span');node.style.color=value;document.body.append(node);const out=getComputedStyle(node).color.match(/[\\d.]+/g).map(Number);node.remove();return out},lum=color=>{const v=color.slice(0,3).map(x=>{x/=255;return x<=.04045?x/12.92:((x+.055)/1.055)**2.4});return .2126*v[0]+.7152*v[1]+.0722*v[2]},ratio=(a,b)=>{const l=[lum(a),lum(b)].sort((a,b)=>b-a);return (l[0]+.05)/(l[1]+.05)},pairs=[['--foreground','--card',4.5],['--muted-foreground','--card',4.5],['--primary','--primary-foreground',4.5],['--input','--card',3],['--ring','--card',3],['--canvas-line','--card',3],['--foreground','--secondary',4.5],['--muted-foreground','--secondary',4.5]];
 const tokens=pairs.map(([a,b,min])=>({foreground:a,background:b,minimum:min,ratio:ratio(rgb(css.getPropertyValue(a)),rgb(css.getPropertyValue(b)))}));
 const parse=value=>{const parts=value.match(/[\\d.]+/g)?.map(Number);if(!parts||parts.length<3)return null;if(value.startsWith('color(srgb ')){for(let i=0;i<3;i++)parts[i]*=255}return parts},compose=(front,back)=>{const a=front[3]??1;return front.slice(0,3).map((v,i)=>v*a+back[i]*(1-a))},background=el=>{const chain=[];for(let p=el;p;p=p.parentElement)chain.unshift(p);let out=[255,255,255];for(const p of chain){const c=parse(getComputedStyle(p).backgroundColor);if(c)out=compose(c,out)}return out};
 const walker=document.createTreeWalker(document.querySelector('.dp-native-shell'),NodeFilter.SHOW_TEXT),bad=[];let node,count=0;
 while(node=walker.nextNode()) {const text=node.textContent.trim(),el=node.parentElement;if(!text||!el||!el.checkVisibility({checkVisibilityCSS:true,checkOpacity:true})||el.closest('button:disabled,[aria-disabled=true],svg,script,style'))continue;const rect=el.getBoundingClientRect(),style=getComputedStyle(el);if(!rect.width||!rect.height||rect.bottom<=0||rect.top>=innerHeight||rect.right<=0||rect.left>=innerWidth||style.visibility==='hidden')continue;const c=parse(style.color);if(!c)continue;let opacity=1;for(let p=el;p;p=p.parentElement)opacity*=Number(getComputedStyle(p).opacity);c[3]=(c[3]??1)*opacity;const bg=background(el),r=ratio(compose(c,bg),bg),size=parseFloat(style.fontSize),minimum=(size>=24||size>=18.66&&Number(style.fontWeight)>=700)?3:4.5;count++;if(r<minimum-.01)bad.push({text:text.slice(0,90),ratio:r,minimum,color:style.color,foreground:style.getPropertyValue('--foreground'),background:bg,opacity,class:el.className});}
 return {tokens,visible_text_nodes:count,low_contrast_text:bad.slice(0,40),viewport_overflow:document.documentElement.scrollWidth>innerWidth};}""")
        values[theme]=value;shot(page,report,'theme-'+theme)
    report['themes']=values
    report['checks']['semantic_text_control_and_focus_contrast_in_four_themes']=all(all(pair['ratio']>=pair['minimum'] for pair in value['tokens']) for value in values.values())
    report['checks']['visible_library_text_contrast_in_four_themes']=all(not value['low_contrast_text'] for value in values.values())
    report['checks']['four_themes_have_no_horizontal_page_overflow']=all(not value['viewport_overflow'] for value in values.values())
    assert report['checks']['semantic_text_control_and_focus_contrast_in_four_themes'],values

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--phase',choices=['smoke','library','manuscript','canvas','themes','reader','layout'],default='smoke');parser.add_argument('--published',action='store_true');args=parser.parse_args()
    state=json.loads(STATE.read_text(encoding='utf8'));project=state['project'];prefix='/research/api/projects/'+project['id'];build=json.loads((DIST/'build-info.json').read_text())
    target=ROOT/'reports'/('workspace-interactions-published-ui.json' if args.published else 'workspace-interactions-candidate.json')
    report=json.loads(target.read_text(encoding='utf8')) if target.exists() else {}
    if report.get('frontend_job_id')!=build['slurm_job_id']:report={'checks':{},'phases':{},'page_errors':[],'screenshots':[]}
    report.update(frontend_job_id=build['slurm_job_id'],project_id=project['id'],mode='published' if args.published else 'local_artifact_real_backend')
    with sync_playwright() as p:
        browser=p.chromium.launch(executable_path='C:/Program Files/Google/Chrome/Application/chrome.exe',headless=True)
        ctx=browser.new_context(viewport={'width':1540,'height':1000},accept_downloads=True)
        # APIRequestContext uses the same authenticated browser cookie jar.
        class LoginClient:
            def post(self,path,json=None):
                response=ctx.request.post(ORIGIN+path,data=json,headers={'Origin':ORIGIN})
                class Result:
                    def raise_for_status(self):assert response.ok,response.status
                return Result()
        login(LoginClient())
        if not args.published:ctx.route(ORIGIN+'/research/**',static_candidate)
        page=ctx.new_page();page.on('pageerror',lambda e:report['page_errors'].append(str(e)))
        area='paper' if args.phase=='manuscript' else 'questions' if args.phase=='canvas' else 'literature'
        url=ORIGIN+'/research/?project='+project['id']+'&dt_workspace='+project['native_id']+'&area='+area
        try:
            page.goto(url,wait_until='domcontentloaded',timeout=60000)
            if args.phase=='library':run_library(ctx,page,prefix,report)
            elif args.phase=='manuscript':run_manuscript(ctx,page,prefix,report)
            elif args.phase=='canvas':run_canvas(ctx,page,prefix,report)
            elif args.phase=='themes':run_themes(ctx,page,prefix,report)
            elif args.phase=='reader':run_reader(ctx,page,prefix,report)
            elif args.phase=='layout':run_layout(ctx,page,prefix,report)
            else:
                page.locator('.bibliography-table').wait_for(timeout=60000);page.wait_for_timeout(1500);report['body']=page.locator('body').inner_text()[:18000];shot(page,report,args.phase)
            report['phases'][args.phase]=True
            report.pop('failure',None)
        except Exception as e:
            report['phases'][args.phase]=False;report['failure']=type(e).__name__+': '+str(e);report['failure_body']=page.locator('body').inner_text()[:20000];shot(page,report,args.phase+'-failure');raise
        finally:
            report['passed']=all(report['phases'].get(phase) for phase in ['library','manuscript','canvas','themes','reader','layout']) and not report['page_errors'] and all(report['checks'].values())
            target.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8');print(json.dumps({'phase':args.phase,'passed':report['phases'].get(args.phase),'checks':report['checks'],'errors':report['page_errors'],'failure':report.get('failure')},ensure_ascii=False),flush=True);browser.close()

if __name__=='__main__':main()
