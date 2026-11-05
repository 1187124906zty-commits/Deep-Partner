"""Stable citation identities shared by the manuscript and project library."""
from copy import deepcopy
import json,re
from urllib.parse import quote


def text(node):
    if node.get('type')=='citation':return '['+str(node.get('attrs',{}).get('number','?'))+']'
    return node.get('text','')+''.join(text(n) for n in node.get('content',[]))


def entry_text(entry):
    if entry.get('raw') and not entry.get('verified'):return entry['raw']
    authors=', '.join(entry.get('authors',[]))
    detail='. '.join(str(v).rstrip('.') for v in (authors,entry.get('title'),entry.get('venue'),entry.get('year')) if v)
    return detail+('. DOI: '+entry['doi'] if entry.get('doi') else ('. arXiv:'+entry['arxiv'] if entry.get('arxiv') else ''))+'.'


def apa_metadata(raw):
    match=re.match(r'^(.*?)\(((?:19|20)\d{2})[a-z]?\)\.\s+(.+)$',raw,re.S)
    if not match:return None
    authors,year,tail=match.groups();parts=re.split(r'\.\s+',tail,maxsplit=1)
    names=re.split(r',\s*(?:&\s*)?(?=[A-ZÀ-Ž][\w’\'-]+,)|\s+&\s+',authors.strip().rstrip(','))
    return {'authors':[n.strip().rstrip(',') for n in names if n.strip()],'year':int(year),'title':parts[0].strip(),
      'venue':re.split(r',\s*\d|\.\s+https?://',parts[1],maxsplit=1)[0].strip() if len(parts)>1 else ''}


def prepare(document,root=None):
    doc=deepcopy(document);blocks=doc.get('content',{}).get('content',[])
    refs=doc.get('references');heading=next((i for i,n in enumerate(blocks) if n.get('type')=='heading' and re.fullmatch(r'(?:\d+[ .、]*)?(?:参考文献|References|Bibliography)',text(n).strip(),re.I)),None)
    if refs is None:
        refs=[]
        if heading is not None:
            for n in blocks[heading+1:]:
                match=re.match(r'^\[(\d+)\]\s*(.+)',text(n),re.S)
                if not match:continue
                number=int(match[1]);raw=match[2].strip();arxiv=re.search(r'(?:arXiv:|arxiv.org/abs/)(\d{4}\.\d{4,5})',raw,re.I)
                doi=re.search(r'10\.\d{4,9}/[^\s]+',raw)
                entry={'id':'ref-'+str(number),'number':number,'raw':raw,'title':raw,'authors':[],'doi':doi[0].rstrip('.,') if doi else '', 'arxiv':arxiv[1] if arxiv else '', 'verified':False}
                parts=re.split(r'\.\s+(?=[A-Z][a-z])',raw,maxsplit=1)
                if len(parts)==2:
                    entry['authors']=[parts[0].rstrip('.')]
                    entry['title']=re.split(r'\.\s+(?:arXiv|DOI|ICLR|Nature|Science|Journal|J\.)|,?\s*arXiv:',parts[1],maxsplit=1,flags=re.I)[0].rstrip('.,')
                year=re.search(r'\b((?:19|20)\d{2})\b',re.sub(r'(?:arXiv:|arxiv.org/abs/)\d{4}\.\d{4,5}','',raw,flags=re.I))
                if year:entry['year']=int(year[1])
                parsed=apa_metadata(raw)
                if parsed:entry.update(parsed)
                if entry['arxiv']:entry['url']='https://arxiv.org/abs/'+entry['arxiv']
                elif entry['doi']:entry['url']='https://doi.org/'+entry['doi']
                # Exact source identity from the project's installed paper manifest.
                if root:
                    candidates=[root/'provenance.json',root/'.workbench/example.json']
                    for p in candidates:
                        if p.is_file():
                            try:
                                data=json.loads(p.read_text());papers=data.get('literature',[])
                                for paper in papers:
                                    if entry['arxiv'] and entry['arxiv'] in paper.get('file',''):entry['title']=paper['title']
                            except (ValueError,KeyError):pass
                refs.append(entry)
    if not isinstance(refs,list) or len(refs)>1000:raise ValueError('参考文献列表无效')
    ids=[r.get('id') for r in refs]
    if any(not isinstance(i,str) or not re.fullmatch(r'[\w-]{1,100}',i) for i in ids) or len(set(ids))!=len(ids):raise ValueError('参考文献需要独立且稳定的标识')
    by_num={str(r.get('number',i+1)):r for i,r in enumerate(refs)};by_id={r['id']:r for r in refs}
    for i,r in enumerate(refs):
        r['number']=i+1
        if r.get('raw') and not r.get('verified'):
            parsed=apa_metadata(r['raw'])
            if parsed:r.update(parsed)
            without_id=re.sub(r'(?:arXiv:|arxiv.org/abs/)\d{4}\.\d{4,5}','',r['raw'],flags=re.I)
            if r.get('year') and not re.search(r'\b'+str(r['year'])+r'\b',without_id):r.pop('year',None)
    def walk(node,bibliography=False):
        if node.get('type')=='citation':
            entry=by_id.get(node.get('attrs',{}).get('refId'))
            if entry:node['attrs']={**node.get('attrs',{}),'number':entry['number']}
            else:raise ValueError('正文引用未登记到参考文献库')
        if 'content' not in node:return
        out=[]
        for child in node['content']:
            if child.get('type')=='text' and not bibliography:
                value=child.get('text','');last=0
                for m in re.finditer(r'\[(\d+)\]',value):
                    if m[1] not in by_num:continue
                    if m.start()>last:out.append({**child,'text':value[last:m.start()]})
                    ref=by_num[m[1]];out.append({'type':'citation','attrs':{'refId':ref['id'],'number':ref['number']}});last=m.end()
                if last<len(value):out.append({**child,'text':value[last:]})
            else:walk(child,bibliography);out.append(child)
        node['content']=out
    for i,n in enumerate(blocks):walk(n,heading is not None and i>heading)
    if refs:
        bib=[{'type':'paragraph','attrs':{'referenceId':r['id']},'content':[{'type':'text','text':'['+str(r['number'])+'] '+entry_text(r)}]} for r in refs]
        if heading is None:blocks += [{'type':'heading','attrs':{'level':1},'content':[{'type':'text','text':'参考文献'}]}]+bib
        else:
            end=next((i for i in range(heading+1,len(blocks)) if blocks[i].get('type')=='heading'),len(blocks))
            blocks[heading+1:end]=bib
    from .equation_layout import mark_tables
    mark_tables(doc['content'])
    doc['references']=refs
    if doc.get('translation'):
        translated=prepare({**doc['translation'],'references':deepcopy(refs)})
        doc['translation']={k:v for k,v in translated.items() if k!='references'}
    return doc


def crossref_item(item):
    authors=[' '.join(v for v in (a.get('given'),a.get('family')) if v) for a in item.get('author',[])][:40]
    date=item.get('published',item.get('issued',{})).get('date-parts',[[None]])
    return {'title':next(iter(item.get('title',[])),''),'authors':authors,'year':date[0][0],'published_date':'-'.join(str(v).zfill(2) if i else str(v) for i,v in enumerate(date[0]) if v is not None), 'venue':next(iter(item.get('container-title',[])),''),'publication_type':item.get('type',''),'doi':item.get('DOI',''),'url':item.get('URL',''),'abstract':re.sub('<[^>]+>','',item.get('abstract',''))[:6000],'issn':item.get('ISSN',[]),'publisher':item.get('publisher',''),'cited_by':item.get('is-referenced-by-count'),'verified':True,'source':'Crossref metadata'}


async def search(query,newest=False,settings=None,journal_only=False,limit=8,venue=None,min_year=None,source=None,offset=0):
    import httpx
    from .literature_providers import resolve,eligible,wos_search,scholar_search,title_key
    settings=settings or {};provider=resolve(settings,source)
    query=query.strip()[:600]
    if len(query)<3:raise ValueError('请输入 DOI、标题或关键词')
    doi=re.sub(r'^https?://(?:dx\.)?doi.org/','',query)
    if provider in ('scholar_mcp','academic_web'):
        if re.fullmatch(r'10\.\d{4,9}/\S+',doi):return await search(doi,settings=settings,source='crossref',journal_only=journal_only,limit=limit,min_year=min_year,offset=offset)
        from .search_mcp import discover,reconcile,PaperRows
        if provider=='scholar_mcp':rows=await discover(query+(' '+venue if venue else ''),limit,min_year,offset)
        else:
            from .network_sources import web_search
            result=await web_search(query+' research paper',settings,limit=min(10,limit))
            if result.get('status')=='unavailable':
                from .search_errors import SearchProviderError
                error=result.get('error') or {}
                raise SearchProviderError(error.get('code','provider_unavailable'),result.get('message','学术网页检索暂不可用'),
                    provider=result.get('source','academic_web'),retryable=error.get('retryable',True),next_action=error.get('next_action','切换来源'))
            rows=PaperRows([{'title':v['title'],'authors':[],'year':None,'venue':'','doi':'','url':v['url'],'abstract':'','search_snippet':v.get('snippet',''),'source':result['source'],'verified':False,'evidence':'search-result'} for v in result.get('items',[])])
        rows=await reconcile(rows,journal_only)
        selected=[v for v in rows if eligible(v,min_year=min_year) and (not venue or v.get('venue','').casefold().strip()==venue.casefold().strip())]
        if newest:selected.sort(key=lambda v:v.get('published_date') or str(v.get('year') or 0),reverse=True)
        return PaperRows(selected,rows.next_cursor,getattr(rows,'diagnostics',{}))
    if provider in ('wos','scholar'):
        try:
            async with httpx.AsyncClient(timeout=30,trust_env=False) as client:
                values=await (wos_search(client,query,settings,limit,venue,min_year,newest,journal_only,offset) if provider=='wos' else scholar_search(client,query,settings,limit,venue,min_year,newest,offset))
        except httpx.HTTPStatusError as error:
            raise ValueError(('Web of Science' if provider=='wos' else 'Google Scholar · SerpApi')+' 返回 HTTP '+str(error.response.status_code)+'，请检查 API Key、权限或配额') from None
        except httpx.HTTPError:
            raise ValueError('文献检索连接未完成，请稍后重试') from None
        if provider=='scholar' and journal_only:
            # Scholar search snippets are not publisher abstracts or verified
            # journal identities. Resolve candidates before journal ranking.
            import asyncio
            semaphore=asyncio.Semaphore(3)
            async def verify(item):
                async with semaphore:
                    try:
                        rows=await search(item.get('doi') or item['title'],settings=settings,source='crossref',limit=1)
                        matched=next((r for r in rows if title_key(r['title'])==title_key(item['title'])),None)
                        if matched and matched.get('publication_type')=='journal-article':return {**matched,'source':item['source']+' · Crossref 题录核验','search_snippet':item['search_snippet']}
                    except httpx.HTTPError:pass
            values=[v for v in await asyncio.gather(*(verify(item) for item in values[:8])) if v]
        return [v for v in values if eligible(v,min_year=min_year) and (not venue or v.get('venue','').casefold().strip()==venue.casefold().strip())]
    if provider=='semantic':
        async with httpx.AsyncClient(timeout=30,trust_env=False) as client:
            r=await client.get('https://api.semanticscholar.org/graph/v1/paper/search',params={'query':query+(' '+venue if venue else ''),'limit':limit,'offset':offset,'fields':'title,authors,year,venue,externalIds,url,abstract,openAccessPdf,publicationTypes',**({'publicationTypes':'JournalArticle'} if journal_only else {}),**({'year':str(min_year)+'-'} if min_year else {})},headers={'x-api-key':settings['literature_token']})
            r.raise_for_status()
            values=[{'title':p['title'],'authors':[a['name'] for a in p.get('authors',[])],'year':p.get('year'),'venue':p.get('venue',''),'doi':p.get('externalIds',{}).get('DOI',''),'url':p.get('url',''),'abstract':p.get('abstract') or '', 'open_access_pdf':(p.get('openAccessPdf') or {}).get('url',''),'verified':True,'source':'Semantic Scholar API'} for p in r.json().get('data',[])]
            values=[v for v in values if eligible(v,min_year=min_year) and (not venue or v.get('venue','').casefold().strip()==venue.casefold().strip())]
            return sorted(values,key=lambda p:p.get('year') or 0,reverse=newest) if newest else values
    async with httpx.AsyncClient(timeout=30,trust_env=False,headers={'User-Agent':'ResearchWorkbench/1.0 (citation metadata lookup)'}) as client:
        if re.fullmatch(r'10\.\d{4,9}/\S+',doi):
            if offset:return []
            r=await client.get('https://api.crossref.org/works/'+quote(doi,safe=''))
            if r.status_code==404:return []
            r.raise_for_status();item=crossref_item(r.json()['message']);return [item] if eligible(item,min_year=min_year) else []
        params={'query.bibliographic':query,'rows':min(30,max(1,limit)),'offset':offset}
        filters=['type:journal-article'] if journal_only else []
        if min_year:
            from datetime import date
            filters.extend(['from-pub-date:'+str(min_year)+'-01-01','until-pub-date:'+date.today().isoformat()])
        if filters:params['filter']=','.join(filters)
        if venue:params['query.container-title']=venue[:200]
        # Crossref's global date sort can bring back papers matching only one
        # broad term. Keep the relevance-ranked candidate page, then order that
        # page by year when requested.
        r=await client.get('https://api.crossref.org/works',params=params);r.raise_for_status()
    values=[crossref_item(i) for i in r.json()['message']['items'] if i.get('title')]
    values=[v for v in values if eligible(v,min_year=min_year) and (not venue or v.get('venue','').casefold().strip()==venue.casefold().strip())]
    return sorted(values,key=lambda v:v.get('published_date') or str(v.get('year') or 0),reverse=True) if newest else values


def replace(store,owner,pid,ref_id,entry,revision,paragraph=None,expected_text=None):
    with store.lock(pid):
        doc=store.manuscript(owner,pid)
        if doc['revision']!=revision:raise ValueError('稿件已更新，请重新选择引用')
        ref=next((r for r in doc.get('references',[]) if r['id']==ref_id),None)
        if ref is None:raise ValueError('参考文献不存在')
        if not entry.get('title') or not entry.get('doi'):raise ValueError('请从检索到的 DOI 文献中选择')
        old=deepcopy(ref);ref.clear();ref.update({**entry,'id':old['id'],'number':old['number']})
        if paragraph:
            matches=[n for n in doc['content']['content'] if n.get('type')=='paragraph' and text(n)==expected_text]
            if len(matches)!=1:raise ValueError('引用所在段落已改变，请重新生成建议')
            if any(n.get('type') not in ('text','citation') for n in matches[0].get('content',[])):raise ValueError('此段包含公式或其他结构，请保留原段落并单独替换文献')
            # A model may revise wording, but may not invent or delete citation identities.
            expected=re.findall(r'\[(\d+)\]',expected_text or '')
            if re.findall(r'\[(\d+)\]',paragraph)!=expected:raise ValueError('建议段落改变了引用编号，请重新生成')
            matches[0]['content']=[{'type':'text','text':paragraph}]
        doc['reason']='替换引用：'+old.get('title','')[:80]+' → '+entry['title'][:80]
        return store.save_manuscript(owner,pid,prepare(doc))
