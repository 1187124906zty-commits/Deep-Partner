"""Author contact details for previews, independent from sign-in credentials."""
from copy import deepcopy
from datetime import datetime
from zoneinfo import ZoneInfo
import json,re
from fastapi import Depends
from .native import actor
from .storage import atomic_json,now

FIELDS=('name','affiliation','email','orcid','address','name_en','affiliation_en')


def read_profile(api_path,owner):
    path=api_path(owner).with_name('author-profile.json')
    return json.loads(path.read_text()) if path.exists() else {k:'' for k in FIELDS}


def validate(payload):
    value={k:str(payload.get(k,'')).strip()[:(1200 if k.startswith('affiliation') or k=='address' else 200)] for k in FIELDS}
    if value['email'] and not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+',value['email']):raise ValueError('请填写有效的作者邮箱')
    if value['orcid'] and not re.fullmatch(r'(?:https://orcid.org/)?\d{4}-\d{4}-\d{4}-\d{3}[\dX]',value['orcid']):raise ValueError('ORCID 格式为 0000-0000-0000-0000')
    value['orcid']=value['orcid'].removeprefix('https://orcid.org/')
    return value


def prepare_preview(document,profile,language=None):
    """Add supplied front matter and an honestly named date to an export copy."""
    from .references import text
    doc=deepcopy(document);nodes=doc.setdefault('content',{}).setdefault('content',[])
    zh=(language or ('zh-CN' if re.search(r'[\u4e00-\u9fff]',doc.get('title','')) else 'en'))=='zh-CN'
    today=datetime.now(ZoneInfo('Asia/Shanghai')).date().isoformat()
    heading=next((i for i,n in enumerate(nodes) if n.get('type')=='heading'),0)
    front=[text(n) for n in nodes[:heading] if n.get('type')=='paragraph' and text(n).strip()]
    def paragraph(value):return {'type':'paragraph','content':[{'type':'text','text':value}]}
    extra=[]
    name=profile.get('name' if zh else 'name_en') or profile.get('name','')
    affiliation=profile.get('affiliation' if zh else 'affiliation_en') or profile.get('affiliation','')
    if not front and name:extra.append(paragraph(name))
    if affiliation and not any(re.search(r'大学|学院|研究所|研究院|university|institute|laborator|school|college|department',v,re.I) or affiliation.casefold() in v.casefold() for v in front):extra.append(paragraph(affiliation))
    contact=[]
    if profile.get('email') and not any(profile['email'].casefold() in v.casefold() for v in front):contact.append(('联系邮箱：' if zh else 'Contact email: ')+profile['email'])
    if profile.get('orcid') and not any(profile['orcid'] in v for v in front):contact.append('ORCID: '+profile['orcid'])
    contact.append(('预览日期：' if zh else 'Preview date: ')+today)
    extra.append(paragraph('   '.join(contact)))
    nodes[heading:heading]=extra
    doc['preview_metadata']={'date':today,'date_kind':'preview','author_profile':profile,'source_front_matter':front,'missing_fields':[k for k in ('name','affiliation','email') if not profile.get(k)],'publication_volume':None,'publication_issue':None}
    return doc


def install(app,api_path,store=None):
    @app.get('/research/api/author-profile')
    async def profile(user=Depends(actor)):
        value=read_profile(api_path,user['id'])
        return {**value,'account_email':user.get('email',''),'purpose':'稿件预览的作者资料；不修改登录信息'}

    @app.put('/research/api/author-profile')
    async def save(payload:dict,user=Depends(actor)):
        value={**validate(payload),'updated':now()};atomic_json(api_path(user['id']).with_name('author-profile.json'),value)
        return {'saved':True,'profile':value}

    if store:
        @app.get('/research/api/projects/{pid}/preview-author')
        async def preview_author(pid:str,user=Depends(actor)):
            from .references import text
            doc=store.manuscript(user['id'],pid);nodes=doc.get('content',{}).get('content',[])
            heading=next((i for i,n in enumerate(nodes) if n.get('type')=='heading'),0)
            front=[text(n) for n in nodes[:heading] if n.get('type')=='paragraph' and text(n).strip()]
            profile=read_profile(api_path,user['id'])
            affiliation=next((v for v in front if re.search(r'大学|学院|研究所|university|institute|college',v,re.I)),'')
            return {'name':front[0] if front else profile.get('name',''),'affiliation':affiliation or profile.get('affiliation',''),'email':profile.get('email',''),'front_matter':front,'source':'当前稿件署名与已保存作者资料'}
