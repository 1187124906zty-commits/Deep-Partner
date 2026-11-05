"""Account storage, readable revision diffs and file provenance."""
from pathlib import Path
from difflib import SequenceMatcher
import json, os, uuid
from .storage import atomic_json, now, child

QUOTA = 2 * 1024**3
LABELS = {'literature':'文献','code':'程序与数据','paper':'论文','slides':'PPT','history':'历史与垃圾箱','other':'工作台索引'}


def account_root(store, owner):
    from .account_policy import policy
    root=store.root/'owners'/uuid.uuid5(uuid.NAMESPACE_URL,owner).hex
    root.mkdir(parents=True,exist_ok=True)
    manifest=root/'workspace.json'
    projects=store.list(owner,include_archived=True)
    current=policy(store,owner)
    value={'schema_version':1,'owner':owner,'quota':current['quota_bytes'],'policy_revision':current['revision'],
        'native_resources':'account-scoped Tutor knowledge bases, memory and sessions remain in their native layout',
        'projects':[{'id':p['id'],'name':p['name'],'path':p['root']} for p in projects]}
    if not manifest.exists() or json.loads(manifest.read_text())!=value:atomic_json(manifest,value)
    return root,projects


def usage(store, owner):
    from .account_policy import policy
    current=policy(store,owner);quota=current['quota_bytes']
    root,projects=account_root(store,owner);totals={k:0 for k in LABELS};seen=set();rows=[];cache_used=0
    for project in projects:
        local={k:0 for k in LABELS};base=Path(project['root'])
        for file in base.rglob('*'):
            if file.is_symlink() or not file.is_file():continue
            rel=file.relative_to(base).parts
            if any(p in ('node_modules','.venv','__pycache__','.git') for p in rel):continue
            try:
                stat=file.stat();key=(stat.st_dev,stat.st_ino)
                if key in seen:continue
                seen.add(key)
                if rel[:3]==('.workbench','neoread','cache'):
                    cache_used+=stat.st_size;continue
                category='history' if rel[0]=='.trash' else 'paper' if rel[0]=='manuscript' else 'slides' if rel[0]=='slides' else 'literature' if (rel[0]=='literature' or 'knowledge_bases' in rel) else 'code' if rel[0] in ('project','outputs') or rel[:2]==('.workbench','figures') else 'other'
                local[category]+=stat.st_size;totals[category]+=stat.st_size
            except OSError:continue
        rows.append({'id':project['id'],'name':project['name'],'bytes':sum(local.values()),'categories':local})
    total=sum(totals.values())
    return {'quota':quota,'used':total,'available':max(0,quota-total),'over_quota':total>quota,'cache_used':cache_used,
        'cache_limit':current['cache_limit_bytes'],'cache_over_limit':cache_used>current['cache_limit_bytes'],
        'policy_revision':current['revision'],'archive_quota':current['archive_quota_bytes'],
        'cache_policy':'阅读渲染缓存独立预算；当前返回用量和超额状态，后台回收及原生KB/Code全局配额尚未切换',
        'categories':[{'id':k,'label':LABELS[k],'bytes':v} for k,v in totals.items()],'projects':rows,'account_path':str(root),'updated':now()}


def require_space(store,owner,additional):
    from .account_policy import check_write
    check_write(store,owner,additional)


def record_file(store,owner,pid,path):
    root=store.path(owner,pid);index=root/'.workbench/file-index.json'
    value=json.loads(index.read_text()) if index.exists() else {}
    key=path.relative_to(root).as_posix();prior=value.get(key,{})
    value[key]={'uploaded':prior.get('uploaded') or now(),'updated':now()};atomic_json(index,value)


def revision_category(original):
    return 'paper' if original.startswith('manuscript/') else 'slides' if original.startswith('slides/') else 'literature' if original.startswith(('literature/','knowledge_bases/')) else 'code'


def paragraphs(document):
    from .references import text
    return [document.get('title','')]+[text(n) if n.get('type')!='image' else '[图片] '+(n.get('attrs',{}).get('src','').split('/')[-1]) for n in document.get('content',{}).get('content',[])]


def revision_diff(store,owner,pid,tid):
    store.get(owner,pid)
    with store.db() as db:row=db.execute('SELECT * FROM trash WHERE owner=? AND project=? AND id=?',(owner,pid,tid)).fetchone()
    if not row:raise KeyError('历史版本不存在')
    old=Path(row['path']);current=child(store.path(owner,pid),row['original']);is_paper=row['original']=='manuscript/main.json'
    image=old.suffix.lower() in ('.png','.jpg','.jpeg','.webp','.svg')
    from urllib.parse import quote
    if image:return {'kind':'image','before':'/research/api/projects/'+pid+'/trash/'+tid+'/preview','after':'/research/api/projects/'+pid+'/file?path='+quote(row['original'][len('project/'):],safe='') if row['original'].startswith('project/') else '', 'changes':[]}
    if not old.is_file() or old.stat().st_size>4*1024**2:return {'kind':'file','changes':[]}
    try:
        if is_paper:
            a=paragraphs(json.loads(old.read_text()));b=paragraphs(json.loads(current.read_text())) if current.exists() else []
        else:
            a=old.read_text().splitlines();b=current.read_text().splitlines() if current.is_file() else []
    except (UnicodeError,ValueError):return {'kind':'file','changes':[]}
    changes=[]
    for tag,i,j,k,l in SequenceMatcher(None,a,b,autojunk=False).get_opcodes():
        if tag=='equal':continue
        changes.append({'kind':tag,'location':('段落 ' if is_paper else '行 ')+str(i+1),'before':'\n'.join(a[i:j])[:16000],'after':'\n'.join(b[k:l])[:16000]})
    return {'kind':'paper' if is_paper else 'text','changes':changes[:80],'before_count':len(a),'after_count':len(b),'comparison':'旧版本 → 当前版本'}


def describe_revision(row):
    original=row['original'];category=revision_category(original)
    title='论文正文' if original=='manuscript/main.json' else '汇报稿件' if original=='slides/main.json' else Path(original).name
    result={**row,'category':category,'category_label':LABELS[category],'title':title,'location':original.removeprefix('project/')}
    return result
