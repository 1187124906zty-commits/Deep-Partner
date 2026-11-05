"""Resolve bibliographic identities and author names from source records."""
from difflib import SequenceMatcher
from urllib.parse import quote
import json,re,time
import httpx
from .literature_providers import doi_key,title_key


def key(entry):
    return doi_key(entry.get('doi')) or ('arxiv:'+str(entry.get('arxiv'))) if entry.get('doi') or entry.get('arxiv') else title_key(entry.get('title'))


def pdf_author_names(names,excerpt):
    """Expand initials only when the name itself occurs in the PDF author block."""
    front=re.split(r'\babstract\b|摘\s*要',excerpt,1,flags=re.I)[0][:5000]
    result=[]
    for name in names:
        if ',' in name:family,given=name.split(',',1)
        else:
            pieces=name.split();family=pieces[-1] if pieces else '';given=' '.join(pieces[:-1])
        family=family.strip();given=given.strip()
        if not family or not given:result.append(name);continue
        matches=re.findall(r'\b('+re.escape(given[:1].upper())+r'[a-zÀ-ž][a-zÀ-ž\-]*(?:[ \t]+(?:[A-Z]\.|[A-Z][a-zÀ-ž\-]+)){0,3})[ \t\n]+(?i:'+re.escape(family)+r')\b',front)
        candidates=[' '.join(v.split()).strip() for v in matches if v.strip()[:1].casefold()==given[:1].casefold()]
        # Require a real written given name rather than treating initials as full names.
        candidate=next((v for v in candidates if any(len(w.rstrip('.'))>1 for w in v.split())),None)
        result.append((candidate or given)+' '+family)
    return result


async def resolve(entry,excerpt='',client=None):
    own=client is None
    client=client or httpx.AsyncClient(timeout=12,trust_env=False,headers={'User-Agent':'ResearchWorkbench bibliographic metadata/1.0'})
    try:
        doi=doi_key(entry.get('doi'));title=entry.get('title','');record=None
        if doi:
            response=await client.get('https://api.crossref.org/works/'+quote(doi,safe=''))
            if response.is_success:
                item=response.json().get('message',{})
                if doi_key(item.get('DOI'))==doi:record=item
        elif not entry.get('arxiv') and len(title)>14:
            response=await client.get('https://api.crossref.org/works',params={'query.title':title,'rows':3})
            if response.is_success:
                for item in response.json().get('message',{}).get('items',[]):
                    found=(item.get('title') or [''])[0]
                    if SequenceMatcher(None,title_key(title),title_key(found)).ratio()>.94:record=item;break
        if record:
            record_title=(record.get('title') or [''])[0]
            if excerpt and title_key(record_title) not in title_key(excerpt) and SequenceMatcher(None,title_key(title),title_key(record_title)).ratio()<.8:
                return {**entry,'metadata_status':'unconfirmed'}
            authors=[' '.join(str(a.get(k) or '').strip() for k in ('given','family')).strip() or a.get('name','') for a in record.get('author',[])]
            authors=[a for a in authors if a]
            if excerpt:authors=pdf_author_names(authors,excerpt)
            published=next((record[k]['date-parts'][0][0] for k in ('published','published-print','published-online','issued') if record.get(k,{}).get('date-parts')),entry.get('year'))
            return {**entry,'title':record_title or title,'authors':authors or entry.get('authors',[]),'doi':record.get('DOI') or doi,'year':published,'venue':(record.get('container-title') or [entry.get('venue','')])[0],'url':record.get('URL') or 'https://doi.org/'+doi,'verified':True,'metadata_status':'verified','metadata_source':'Crossref DOI record','metadata_url':'https://api.crossref.org/works/'+quote(doi_key(record.get('DOI')),safe='')}
        if entry.get('arxiv'):
            from xml.etree import ElementTree as ET
            identifier=str(entry['arxiv']).removeprefix('arXiv:')
            response=await client.get('https://export.arxiv.org/api/query',params={'id_list':identifier})
            if response.is_success:
                ns={'a':'http://www.w3.org/2005/Atom'};row=ET.fromstring(response.text).find('a:entry',ns)
                if row is not None and identifier in row.findtext('a:id',default='',namespaces=ns):
                    names=[a.findtext('a:name',default='',namespaces=ns) for a in row.findall('a:author',ns)]
                    return {**entry,'title':' '.join(row.findtext('a:title',default=title,namespaces=ns).split()),'authors':names,'verified':True,'metadata_status':'verified','metadata_source':'arXiv','metadata_url':'https://arxiv.org/abs/'+identifier}
        return {**entry,'metadata_status':'unconfirmed'}
    except (httpx.HTTPError,ValueError,KeyError):return {**entry,'metadata_status':'pending'}
    finally:
        if own:await client.aclose()


def read_cache(root):
    path=root/'.workbench/bibliography-metadata.json'
    return json.loads(path.read_text()) if path.exists() else {}


def more_complete_authors(original,incoming):
    """Keep written given names when a source record supplies only initials."""
    if not incoming:return original
    if len(original)!=len(incoming):return incoming
    def family(name):return (name.split(',')[0] if ',' in name else name.split()[-1] if name.split() else '').strip().casefold()
    def fullness(name):return sum(len(part.strip('.'))>1 for part in re.split(r'[\s,]+',name))
    return [old if family(old)==family(new) and fullness(old)>fullness(new) else new for old,new in zip(original,incoming)]


def overlay(entry,cache):
    value=cache.get(key(entry),{}).get('record',{})
    # Keep stable reference IDs and uploaded attachment provenance.
    merged={**entry,**{k:v for k,v in value.items() if k not in {'id','number','attachment','transfer','uploaded'}}}
    merged['authors']=more_complete_authors(entry.get('authors',[]),merged.get('authors',[]))
    return merged
