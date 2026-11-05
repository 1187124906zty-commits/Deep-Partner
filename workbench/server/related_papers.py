"""Daily source-backed suggestions, ranked by the user's configured model."""
import asyncio,json,re,time
from datetime import date
from .literature_providers import available,resolve,eligible,doi_key,title_key,PROVIDERS
from .native import actor,headers,BASE
from .storage import atomic_json,now
from fastapi import Depends,Request


def install(app,store,api_path,pool):
    seen={};active=set()
    def refresh(owner,pid,rid,native_headers,years=5,source='auto'):
        key=(owner,pid,rid,years,source)
        if key in active:return
        active.add(key);root=store.path(owner,pid);path=root/'.workbench/related-papers'/(rid+'-'+str(years)+'-'+source+'.json')
        prior=json.loads(path.read_text()) if path.exists() else {}
        settings=json.loads(api_path(owner).read_text()) if api_path(owner).exists() else {}
        min_year=date.today().year-years+1 if years else None
        atomic_json(path,{**prior,'status':'running','error':'','started_at':time.time(),'min_year':min_year,'source':PROVIDERS[resolve(settings,source)][0]})
        def run():
            try:
                from .references import search,text
                from .models import complete
                project=store.get(owner,pid);document=store.manuscript(owner,pid);ref=next(r for r in document['references'] if r['id']==rid)
                context=[text(n) for n in document['content']['content'] if any(c.get('attrs',{}).get('refId')==rid for c in n.get('content',[]))]
                query_prompt='为原引用寻找5篇相关高质量研究，生成3个互补英文检索式。综合原文方法、研究对象与引用段落：一个查同类方法的代表工作，一个查后续改进，一个查相近研究对象的应用。每式3至8个有效英文关键词，不包含作者、年份和原论文完整标题。另外选择2种与该研究领域相符、公认有影响力的学术期刊，用于定向补检，避免普通检索遗漏代表性方法文献；期刊名使用完整英文名称。只输出JSON：{"queries":["...","...","..."],"venues":["...","..."]}。'
                query_prompt+=' 本轮年份范围为'+(str(min_year)+'至'+str(date.today().year) if min_year else '全部年份')+'。检索关键词不要复述原文完整标题。'
                raw=complete(settings,native_headers,project['native_id'],query_prompt,json.dumps({'reference':ref,'context':context[:3]},ensure_ascii=False),BASE,True,'literature')
                plan=json.loads(re.sub(r'^```(?:json)?\s*|\s*```$','',raw.strip()));queries=plan.get('queries',[])[:3];venues=[v for v in plan.get('venues',[])[:2] if isinstance(v,str) and 5<len(v)<200]
                candidates=[];keys=set()
                # Exact DOI checks of nearby bibliography entries provide a
                # source-bound route to representative journal work when broad
                # keyword ranking returns only distant applications.
                journal_names=[v.casefold().strip() for v in venues]
                seeds=[r for r in document.get('references',[]) if r['id']!=rid and r.get('doi') and r.get('venue','').casefold().strip() in journal_names and re.search(r'physics.informed|neural|loss',r.get('title',''),re.I)][:6]
                searches=[(r['doi'],None) for r in seeds]+[(q,None) for q in [ref['title'],*queries]]+([(queries[i%len(queries)],v) for i,v in enumerate(venues)] if queries else [])
                for query,venue in searches:
                    if not isinstance(query,str) or len(query)<3:continue
                    import httpx
                    try:rows=asyncio.run(search(query,settings=settings,journal_only=True,limit=12 if venue else 18,venue=venue,min_year=min_year,source=source))
                    except (httpx.HTTPError,ValueError):
                        # One rate-limited query must not discard other verified
                        # candidates or a successfully completed previous list.
                        continue
                    for row in rows:
                        if not row.get('venue') or re.search(r'conference|proceedings|workshop|technical report|thesis|preprint',row['venue'],re.I):continue
                        identity=doi_key(row.get('doi')) or title_key(row['title'])
                        if identity in keys or not eligible(row,ref,min_year):continue
                        keys.add(identity);candidates.append(row)
                if not candidates:raise ValueError('当前来源和年份范围内未取得可核验的相关期刊文献，可切换来源或放宽年份。')
                prompt='从已联网检索到的真实候选文献中，选择5篇与原引用相关的高质量期刊研究。用户要求顶刊优先：应优先本领域公认有影响力的同行评议期刊（如 Journal of Computational Physics、Computer Methods in Applied Mechanics and Engineering、Nature 系列等），同时综合方法、研究对象、引用段落用途，不只按年份。禁止用普通会议论文集、技术报告、学位论文、预印本凑数。不能编造影响因子、分区、全文结论，不以声誉替代相关性。只有题录/摘要，应在理由中保持这一证据范围。建议列表用于展示相关研究，不等于全部替换原引用；兼顾方法与研究对象，可选相邻机制或数值方法。只有真实相关且质量足够的候选不足5篇时才少选并解释，不得降低门槛填满。只输出JSON：{"items":[{"index":候选整数索引,"reason":"具体方法/对象相关性及选择理由"}],"note":"限制或整体判断"}。'
                prompt+=' 每条reason用1至2句、约60至120个汉字说明具体联系，不重复期刊名和年份。note只写读者需要的证据限制，不提index、candidates、JSON或工具内部处理。'
                raw=complete(settings,native_headers,project['native_id'],prompt,json.dumps({'reference':ref,'paragraphs':context[:3],'candidates':candidates},ensure_ascii=False),BASE,True,'literature')
                ranked=json.loads(re.sub(r'^```(?:json)?\s*|\s*```$','',raw.strip()));items=[];used=set()
                for choice in ranked.get('items',[]):
                    index=choice.get('index')
                    if not isinstance(index,int) or index in used or not 0<=index<len(candidates):continue
                    used.add(index);items.append({**candidates[index],'reason':str(choice.get('reason',''))[:800]})
                    if len(items)==5:break
                items.sort(key=lambda r:r.get('published_date') or str(r.get('year') or 0),reverse=True)
                note=re.sub(r'[^。！？\n]*(?:\bindex\b|\bcandidates\b|JSON)[^。！？\n]*[。！？\n]?','',str(ranked.get('note','')),flags=re.I).strip()
                atomic_json(path,{'status':'ready','items':items,'note':note,'updated':now(),'checked_at':time.time(),'basis':'联网期刊题录与可用摘要；Agent 综合比较方法、对象与学术期刊，未推断未经核验的分区。','source':PROVIDERS[resolve(settings,source)][0],'min_year':min_year,'reference_title':ref['title'],'search_queries':queries,'targeted_journals':venues,'generation_version':7})
            except Exception as e:atomic_json(path,{**prior,'status':'failed','error':str(e)[:400],'attempted':now()})
            finally:active.discard(key)
        pool.submit(run)

    @app.get('/research/api/projects/{pid}/references/{rid}/related')
    async def related(request:Request,pid:str,rid:str,years:int=5,source:str='auto',user=Depends(actor)):
        owner=user['id'];doc=store.manuscript(owner,pid)
        ref=next((r for r in doc.get('references',[]) if r['id']==rid),None)
        if not ref:raise ValueError('引用文献不存在')
        if years not in (0,5,10):raise ValueError('年份范围请选择近5年、近10年或全部')
        settings=json.loads(api_path(owner).read_text()) if api_path(owner).exists() else {};source=resolve(settings,source)
        path=store.path(owner,pid)/'.workbench/related-papers'/(rid+'-'+str(years)+'-'+source+'.json');value=json.loads(path.read_text()) if path.exists() else {}
        key=(owner,pid,rid,years,source);seen[key]=headers(request)
        if value.get('status')=='running' and key not in active:value={**value,'status':'interrupted'}
        if value.get('generation_version')!=7 or value.get('reference_title')!=ref['title'] or time.time()-value.get('checked_at',0)>86400:
            if value.get('status')!='failed' or time.time()-path.stat().st_mtime>900:refresh(owner,pid,rid,headers(request),years,source)
        value=json.loads(path.read_text()) if path.exists() else {'status':'running','items':[]}
        min_year=date.today().year-years+1 if years else None
        note=re.sub(r'[^。！？\n]*(?:\bindex\b|\bcandidates\b|JSON)[^。！？\n]*[。！？\n]?','',str(value.get('note','')),flags=re.I).strip()
        return {**value,'note':note,'items':[r for r in value.get('items',[]) if eligible(r,ref,min_year)],'source':PROVIDERS[source][0],'provider':source,'providers':available(settings),'min_year':min_year}

    async def daily_updates():
        while True:
            await asyncio.sleep(900)
            for (owner,pid,rid,years,source),native_headers in list(seen.items()):
                path=store.path(owner,pid)/'.workbench/related-papers'/(rid+'-'+str(years)+'-'+source+'.json')
                if path.exists() and time.time()-json.loads(path.read_text()).get('checked_at',0)>86400:refresh(owner,pid,rid,native_headers,years,source)
    return daily_updates
