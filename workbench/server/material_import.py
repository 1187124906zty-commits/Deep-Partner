"""Import selected private research materials into an owner-scoped project."""
from pathlib import Path,PurePosixPath
from io import BytesIO
import hashlib,json,re,zipfile
from .storage import child,atomic_json,now


def import_bundle(store,owner,pid,data,progress=None):
    from .manuscripts import import_manuscript,text
    root=store.path(owner,pid);project=store.get(owner,pid)
    if progress:progress('inspect','正在检查材料清单与文件范围')
    with zipfile.ZipFile(BytesIO(data)) as archive:
        members=archive.infolist()
        if len(members)>2500 or sum(m.file_size for m in members)>650*1024**2:raise ValueError('导入包超出项目材料范围')
        if 'workbench-import.json' not in archive.namelist():raise ValueError('导入包缺少材料清单')
        meta=json.loads(archive.read('workbench-import.json'))
        if meta.get('format')=='workbench-project.v2':
            from .snapshot_import import import_snapshot
            return import_snapshot(store,owner,pid,archive,meta,progress=progress)
        manuscript=meta.get('manuscript','manuscript/source.docx')
        if manuscript not in archive.namelist() or not manuscript.endswith('.docx'):raise ValueError('清单需要指定可编辑 Word 原稿')
        if any(m.filename.startswith('.workbench/figures/') for m in members):
            receipt=store.root/'trusted-figure-imports'/(hashlib.sha256(data).hexdigest()+'.json')
            trusted=json.loads(receipt.read_text()) if receipt.is_file() else {}
            if trusted.get('owner')!=owner or trusted.get('project')!=pid:raise ValueError('图形对象须经已授权的计算通道生成并登记；普通材料包请只放源程序、数据和图像')
        staged={}
        for member in members:
            if member.is_dir() or member.filename=='workbench-import.json':continue
            path=PurePosixPath(member.filename)
            if path.is_absolute() or '..' in path.parts or '\\' in member.filename:raise ValueError('导入路径无效')
            relative=path.as_posix()
            if not relative.startswith(('project/','manuscript/source.','.workbench/figures/','.workbench/remote-data.json')):raise ValueError('导入文件不属于研究材料目录')
            if relative.startswith('project/') and any(v in path.parts for v in ('.venv','node_modules','site-packages','.env')):raise ValueError('运行环境不作为项目材料导入')
            staged[relative]=archive.read(member)
    if progress:progress('files','正在保存程序与数据',{'done':0,'total':len(staged),'unit':'个文件'})
    for i,(name,value) in enumerate(staged.items(),1):
        store.replace(owner,pid,child(root,name),value,'导入用户选择的研究材料')
        if progress and (i%10==0 or i==len(staged)):progress('files','正在保存程序与数据',{'done':i,'total':len(staged),'unit':'个文件'})
    if progress:progress('document','正在整理可编辑稿件与图表来源')
    tree=import_manuscript(root,pid,staged[manuscript],Path(manuscript).name);title=meta.get('title') or project['name']
    if tree.get('content') and text(tree['content'][0]).strip()==title.strip():tree['content'].pop(0)
    current=store.manuscript(owner,pid);current.update(title=title,content=tree,comments=[],references=None,translation=None,reason='导入最新作者稿，保留原始 Word/PDF')
    from .figures import read_registry
    from PIL import Image,ImageChops,ImageStat
    candidates=[]
    for asset in read_registry(root):
        p=child(root/'project',asset)
        if p.is_file():
            with Image.open(p) as im:candidates.append((asset,im.width/im.height,im.convert('RGB').resize((96,96))))
    linked=[]
    def connect(node):
        if node.get('type')=='image':
            attrs=node.get('attrs',{});match=re.search('/manuscript/assets/([^/?]+)',attrs.get('src',''))
            if match:
                p=child(root/'manuscript/assets',match[1])
                with Image.open(p) as im:
                    ratio=im.width/im.height;sample=im.convert('RGB').resize((96,96));scores=[]
                    for asset,r,other in candidates:
                        if abs(ratio/r-1)<.035:scores.append((sum(ImageStat.Stat(ImageChops.difference(sample,other)).mean)/3/255,asset))
                scores.sort()
                if scores and scores[0][0]<.045 and (len(scores)<2 or scores[1][0]-scores[0][0]>.008):
                    asset=scores[0][1];attrs['source_path']=asset;linked.append({'asset':asset,'image':p.name,'visual_error':scores[0][0]})
        for n in node.get('content',[]):connect(n)
    connect(current['content']);saved=store.save_manuscript(owner,pid,current)
    if progress:progress('catalog','正在更新项目材料记录')
    metadata={'imported':now(),'source':meta.get('source','user selected bundle'),'manuscript':manuscript,'files':len(staged),'linked_figures':linked,'manuscript_revision':saved['revision'],'scope':'private owner project; no presentation generated'}
    atomic_json(root/'.workbench/material-import.json',metadata);config=project['config'];config['material_import']=metadata;store.update(owner,pid,config=config)
    def image_count(node):return int(node.get('type')=='image')+sum(image_count(n) for n in node.get('content',[]))
    return {**metadata,'references':len(saved.get('references',[])),'images':image_count(saved['content'])}
