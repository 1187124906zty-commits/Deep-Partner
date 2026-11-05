"""Journal identity lookup and an official-class typesetting preview."""
from pathlib import Path
from urllib.parse import urlparse,quote
import asyncio,html,json,re,shutil,subprocess,time
import httpx
from fastapi import Depends,Request
from .native import actor
from .storage import atomic_json,now
from .journal_catalog import match_template,local_journals

ROOT=Path(__file__).resolve().parents[1]
ELSEVIER_SOURCE='https://www.elsevier.com/researcher/author/policies-and-guidelines/latex-instructions'


def journal_item(value):
    publisher=value.get('host_organization_name') or ' / '.join(value.get('host_organization_lineage_names') or [])
    return match_template({'id':value['id'].split('/')[-1],'name':value.get('display_name',''),'publisher':publisher,'issn':value.get('issn') or [],'homepage':value.get('homepage_url') or '','source':'https://openalex.org/'+value['id'].split('/')[-1],'impact_factor':None,'quartile':None,'metrics_checked':now()})


def crossref_journal(value):
    issn=next(iter(value.get('ISSN',[])),'');publisher=value.get('publisher','');name=value.get('title','')
    homepage='https://www.sciencedirect.com/journal/'+re.sub(r'[^a-z0-9]+','-',name.lower()).strip('-') if 'elsevier' in publisher.lower() else value.get('URL','')
    return match_template({'id':'issn-'+issn,'name':name,'publisher':publisher,'issn':value.get('ISSN',[]),'homepage':homepage,'source':'https://api.crossref.org/journals/'+issn,'impact_factor':None,'quartile':None,'metrics_checked':now()})


def chinese_template():return local_journals()[0]


async def lookup(identifier):
    if identifier in ('generic-zh','generic-en'):
        from .manuscripts import template_info
        spec=template_info(identifier)
        return {'id':identifier,'name':spec['name'],'publisher':'工作台通用学术版式','issn':[],'homepage':'','source':'/research/api/standards','language':spec['language'],'generic':True,'template':{'family':'generic','word_template':identifier,'name':spec['name'],'source':spec['source'],'supported':True,'columns':[1,2],'match':'generic'},'impact_factor':None,'quartile':None,'metrics_checked':now()}
    local=next((j for j in local_journals() if j['id']==identifier),None)
    if local:return local
    if re.fullmatch(r'issn-\d{4}-[\dXx]{4}',identifier):
        async with httpx.AsyncClient(timeout=25,trust_env=False) as client:
            response=await client.get('https://api.crossref.org/journals/'+identifier[5:]);response.raise_for_status()
        return crossref_journal(response.json()['message'])
    if not re.fullmatch(r'S\d+',identifier):raise ValueError('请选择检索到的期刊')
    async with httpx.AsyncClient(timeout=25,trust_env=False) as client:
        response=await client.get('https://api.openalex.org/sources/'+identifier);response.raise_for_status()
    return journal_item(response.json())




def escape(value):
    replacements={'\\':r'\textbackslash{}','&':r'\&','%':r'\%','$':r'\$','#':r'\#','_':r'\_','{':r'\{','}':r'\}','~':r'\textasciitilde{}','^':r'\textasciicircum{}'}
    greek={'α':'alpha','β':'beta','γ':'gamma','δ':'delta','ε':'epsilon','η':'eta','θ':'theta','κ':'kappa','λ':'lambda','μ':'mu','µ':'mu','ν':'nu','ξ':'xi','π':'pi','ρ':'rho','σ':'sigma','τ':'tau','φ':'phi','ϕ':'varphi','χ':'chi','ψ':'psi','ω':'omega','Γ':'Gamma','Δ':'Delta','Θ':'Theta','Λ':'Lambda','Ξ':'Xi','Π':'Pi','Σ':'Sigma','Φ':'Phi','Ψ':'Psi','Ω':'Omega','∇':'nabla','∂':'partial','∞':'infty','×':'times','≤':'leq','≥':'geq','±':'pm','−':'-'}
    superscript=str.maketrans('⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻','0123456789+-');subscript=str.maketrans('₀₁₂₃₄₅₆₇₈₉₊₋','0123456789+-')
    out=[]
    for c in str(value):
        if ord(c)<32 and c not in '\n\r\t' or 127<=ord(c)<160:continue
        if c in greek:out.append(r'\ensuremath{'+('\\'+greek[c] if greek[c]!='-' else '-')+'}')
        elif c in '⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻':out.append(r'\textsuperscript{'+c.translate(superscript)+'}')
        elif c in '₀₁₂₃₄₅₆₇₈₉₊₋':out.append(r'\textsubscript{'+c.translate(subscript)+'}')
        else:out.append(replacements.get(c,c))
    return ''.join(out)


def inline(nodes):
    output=[]
    for n in nodes:
        kind=n.get('type');attrs=n.get('attrs',{})
        if kind in ('inlineMath','blockMath'):
            from .math_layout import typographic_math
            value='$'+typographic_math(''.join(c for c in attrs.get('latex','') if c in '\n\r\t' or not (ord(c)<32 or 127<=ord(c)<160))).replace(r'\mathbf',r'\symbfit')+'$'
        elif kind=='citation':value='['+str(attrs.get('number','?'))+']'
        elif kind=='hardBreak':value=r'\newline{}'
        elif kind=='text':
            raw=n.get('text','');parts=[];last=0
            for match in re.finditer(r'https?://[^\s]+|(?<![\w/])10\.\d{4,9}/[^\s]+',raw):
                token=match[0].rstrip('.,;');parts.append(escape(raw[last:match.start()]));parts.append(r'\url{'+token.replace('{','%7B').replace('}','%7D')+'}');last=match.start()+len(token)
            parts.append(escape(raw[last:]));value=''.join(parts)
            for mark in n.get('marks',[]):
                command={'bold':'textbf','italic':'textit','superscript':'textsuperscript','subscript':'textsubscript'}.get(mark['type'])
                if command:value='\\'+command+'{'+value+'}'
        else:value=inline(n.get('content',[]))
        output.append(value)
    return ''.join(output)


def document_tex(root,document,journal,columns):
    if journal['template']['family']=='elsevier':
        from .cas_typesetting import document_tex as cas_document_tex
        return cas_document_tex(root,document,journal,columns)
    from .native_typesetting import document_tex as native_document_tex
    return native_document_tex(root,document,journal,columns)


def compile_preview(store,owner,pid,document,journal,columns):
    root=store.path(owner,pid);folder=root/'.workbench/journal-preview';folder.mkdir(parents=True,exist_ok=True)
    if journal['template']['family'] in ('word-native','generic'):
        from .manuscripts import export_manuscript
        data,_,_=export_manuscript(root,{**document,'template':journal['template'].get('word_template','chinese'),'columns':columns},'pdf')
        import fitz
        with fitz.open(stream=data,filetype='pdf') as pdf:pages=len(pdf)
        target=root/'manuscript/exports/期刊排版预览.pdf';store.replace(owner,pid,target,data,'生成'+journal['name']+'预览')
        atomic_json(folder/'manifest.json',{'journal':journal,'columns':columns,'language':journal.get('language','en'),'manuscript_revision':document['revision'],'pages':pages,'generated':now(),'template_class':journal['template'].get('word_template','chinese'),'preview_metadata':document.get('preview_metadata'),'research':document.get('preview_research')})
        return {'url':'/research/api/projects/'+pid+'/download?area=manuscript&name='+quote(target.name),'pages':pages,'journal':journal,'columns':columns,'template_class':journal['template'].get('word_template','chinese')}
    # Different classes can ship same-named packages and incompatible aux macros.
    # Only the task-owned compilation support files are replaced here.
    for support in folder.iterdir():
        if support.is_file() and support.suffix.lower() in ('.cls','.sty','.bst','.aux','.out','.toc','.bbl','.blg','.xdv','.log'):support.unlink()
    if (folder/'Fonts').is_dir():shutil.rmtree(folder/'Fonts')
    template=ROOT/'templates/manuscripts/latex'/('cas' if journal['template']['family']=='elsevier' else journal['template']['family'])
    class_name=('cas-dc.cls' if columns==2 else 'cas-sc.cls') if journal['template']['family']=='elsevier' else {'springer':'sn-jnl.cls','ieee':'IEEEtran.cls','wiley':'WileyNJDv5.cls'}[journal['template']['family']]
    if not (template/class_name).is_file():raise ValueError('期刊模板尚未安装')
    for file in template.iterdir():
        if file.suffix.lower() in ('.cls','.sty','.bst'):shutil.copyfile(file,folder/file.name)
    if (template/'Fonts').is_dir():shutil.copytree(template/'Fonts',folder/'Fonts',dirs_exist_ok=True)
    source,report=document_tex(root,document,journal,columns);tex=folder/'preview.tex';tex.write_text(source,encoding='utf8')
    engine=Path('/opt/workbench-tools/tectonic/tectonic')
    if not engine.is_file():raise ValueError('LaTeX 排版引擎尚未配置')
    result=subprocess.run([str(engine),'--untrusted','--keep-logs','--keep-intermediates','--outdir',str(folder),str(tex)],cwd=folder,capture_output=True,text=True,timeout=300)
    (folder/'compile.txt').write_text(result.stdout+'\n'+result.stderr,encoding='utf8')
    pdf=folder/'preview.pdf'
    if result.returncode or not pdf.is_file():raise ValueError('期刊排版未完成：'+(result.stderr or result.stdout)[-1200:])
    if 'Missing character:' in result.stdout+result.stderr:raise ValueError('期刊预览中有字符未找到对应字体，未发布这次预览；排版日志已保留。')
    import fitz
    with fitz.open(pdf) as rendered:
        if not len(rendered):raise ValueError('期刊预览没有可阅读页面')
        pages=len(rendered)
    target=root/'manuscript/exports/期刊排版预览.pdf';store.replace(owner,pid,target,pdf.read_bytes(),'按 '+journal['name']+' 官方类排版预览')
    atomic_json(folder/'manifest.json',{'journal':journal,'columns':columns,'manuscript_revision':document['revision'],'generated':now(),'pages':pages,'layout':report,'template_class':class_name,'source_template':str(template/'provenance.json')})
    return {'url':'/research/api/projects/'+pid+'/download?area=manuscript&name='+quote(target.name),'pages':pages,'journal':journal,'columns':columns,'template_class':class_name}



def english_document(store,owner,pid,document,native_headers,settings,stage=None):
    from .manuscripts import plain_document
    if not re.search(r'[\u4e00-\u9fff]',document['title']+plain_document(document['content'])[:800]):return document
    translated=document.get('translation')
    if not translated or translated.get('language')!='en' or translated.get('stale') or translated.get('prompt_version',0)<3:
        from .academic_translation import translate_document
        from .translation import DEFAULT_PROMPT
        from .models import complete
        from .native import BASE
        project=store.get(owner,pid);root=store.path(owner,pid)
        def invoke(prompt,body):return complete(settings,native_headers,project['native_id'],prompt,body,BASE,True,'translation')
        translated=translate_document(document,'en',invoke,settings.get('translation_prompt') or DEFAULT_PROMPT,workers=2,checkpoint=root/'.workbench/translations/english-preview.json',progress=lambda done,total:stage('正在准备英文稿 · '+str(done)+' / '+str(total)) if stage else None)
        import uuid
        translated.update(updated=now(),generation_id=uuid.uuid4().hex)
        with store.lock(pid):
            current=store.manuscript(owner,pid)
            if current['content']!=document['content'] or current['title']!=document['title']:raise ValueError('原稿在翻译时已改变，请重新生成英文预览')
            current['translation']=translated;store.save_manuscript(owner,pid,current)
    return {**document,**translated,'references':document.get('references',[]),'language':'en'}


def install(app,store,pool,api_path=None):
    @app.get('/research/api/journals/search')
    async def search(q:str='',user=Depends(actor)):
        if not q.strip():return {'items':[],'local_templates':[],'generic_templates':[await lookup('generic-zh'),await lookup('generic-en')],'checked':now()}
        if len(q.strip())<2:raise ValueError('请输入期刊全名或关键词')
        async with httpx.AsyncClient(timeout=30,trust_env=False) as client:
            result=await client.get('https://api.crossref.org/journals',params={'query':q[:200],'rows':8})
            if result.is_success:
                values=[crossref_journal(v) for v in result.json()['message'].get('items',[]) if v.get('ISSN')]
            else:
                result=await client.get('https://api.openalex.org/sources',params={'search':q[:200],'per-page':8});result.raise_for_status()
                values=[journal_item(v) for v in result.json().get('results',[]) if v.get('type')=='journal']
        if re.search(r'西北|工业大学|工程科学|力学进展|中文|260909|polytechnical',q,re.I):
            for local in reversed(local_journals()):
                if q in local['name'] or q in ('中文','260909') or 'polytechnical' in q.lower():values.insert(0,local)
        return {'items':values,'checked':now(),'local_templates':local_journals()}

    @app.get('/research/api/journals/{identifier}')
    async def detail(identifier:str,year:int|None=None,user=Depends(actor)):
        from .journal_metrics import metrics as source_metrics
        journal=await lookup(identifier)
        if journal.get('generic'):return journal
        if year is not None and not 1997<=year<=time.localtime().tm_year:raise ValueError('指标年份无效')
        settings=json.loads(api_path(user['id']).read_text()) if api_path and api_path(user['id']).exists() else {}
        return await source_metrics(journal,settings,year)

    @app.post('/research/api/projects/{pid}/journal-preview')
    async def preview(request:Request,pid:str,payload:dict,user=Depends(actor)):
        owner=user['id'];project=store.get(owner,pid);journal=await lookup(str(payload.get('journal') or 'generic-zh'));columns=int(payload.get('columns',1))
        if columns not in (1,2):raise ValueError('期刊预览支持单栏或双栏')
        if not journal['template']['supported']:raise ValueError('尚未取得该刊可用的官方排版类，请先选择已有官方模板的期刊')
        if columns not in journal['template'].get('columns',[2,1]):columns=journal['template']['columns'][0]
        document=store.manuscript(owner,pid);config=project['config'];config['target_journal']=journal;store.update(owner,pid,config=config)
        from .native import headers
        native_headers=headers(request);settings=json.loads(api_path(owner).read_text()) if api_path and api_path(owner).exists() else {}
        jid=store.job(owner,pid,'journal-preview',{'subject':document['title']+' · '+journal['name']})
        def run():
            store.set_job(jid,status='running',step='author',stage='正在核对作者单位与版式来源')
            try:
                from .author_profile import read_profile,prepare_preview
                from .network_sources import institution_search,web_search
                profile=read_profile(api_path,owner) if api_path else {}
                prepared=document if journal.get('language')=='zh-CN' else english_document(store,owner,pid,document,native_headers,settings,stage=lambda message:store.set_job(jid,stage=message))
                prepared=prepare_preview(prepared,profile,journal.get('language'))
                affiliation=profile.get('affiliation') or profile.get('affiliation_en')
                if not affiliation:
                    affiliation=next((v for v in prepared['preview_metadata']['source_front_matter'] if re.search(r'大学|学院|研究所|university|institute',v,re.I)),'')
                research={'institutions':asyncio.run(institution_search(affiliation)),'checked':now()}
                if affiliation:research['author_sources']=asyncio.run(web_search(affiliation+' official university institute contact',settings,limit=3))
                store.set_job(jid,step='template',stage='正在核对期刊版式与模板来源')
                if not journal.get('generic'):
                    from .template_discovery import discover
                    research['templates']=asyncio.run(discover(journal,settings))
                prepared['preview_research']=research
                store.set_job(jid,step='compile',stage='正在生成作者资料、日期与稿件版式')
                result=compile_preview(store,owner,pid,prepared,journal,columns)
                store.set_job(jid,step='save',stage='期刊排版预览已保存')
                result.update(preview_metadata=prepared.get('preview_metadata'),research=research)
                store.set_job(jid,status='completed',stage='稿件预览已生成',result=result)
            except Exception as e:store.set_job(jid,status='failed',stage='排版未完成',error=str(e)[:1600])
        pool.submit(run);return {'job_id':jid}
