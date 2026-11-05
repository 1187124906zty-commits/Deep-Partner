"""Import an explicit file snapshot, without executing imported code or pickles."""
from pathlib import PurePosixPath
import json,re
from .storage import child,atomic_json,now

def import_snapshot(store,owner,pid,archive,meta,progress=None):
    root=store.path(owner,pid);project=store.get(owner,pid);staged={};omitted=[]
    for member in archive.infolist():
        if member.is_dir() or member.filename in ('workbench-import.json','导出来源.json'):continue
        parts=PurePosixPath(member.filename)
        if parts.is_absolute() or '..' in parts.parts or '\\' in member.filename:raise ValueError('导入路径无效')
        if member.filename.startswith('.workbench/'):
            omitted.append(member.filename);continue
        if parts.parts[0] not in ('project','manuscript','slides','literature'):raise ValueError('导入文件不属于项目材料')
        if any(p in ('.git','.venv','node_modules','__pycache__','.trash','.env') for p in parts.parts):raise ValueError('导入包包含运行环境或私密配置')
        staged[member.filename]=archive.read(member)
    document=None
    if 'manuscript/main.json' in staged:
        document=json.loads(staged.pop('manuscript/main.json'))
        if not isinstance(document.get('content'),dict) or document['content'].get('type')!='doc':raise ValueError('快照稿件不是可编辑文档')
        # Rewrite only owned resource URLs, never source prose or arbitrary URLs.
        old=meta.get('source_project_id','')
        def relink(value):
            if isinstance(value,dict):
                for key,item in value.items():
                    if key in ('src','href','url') and isinstance(item,str) and re.fullmatch('[a-f0-9]{32}',old):value[key]=item.replace('/research/api/projects/'+old+'/', '/research/api/projects/'+pid+'/')
                    else:relink(item)
            elif isinstance(value,list):
                for item in value:relink(item)
        relink(document)
    if progress:progress('files','正在保存项目文件',{'done':0,'total':len(staged),'unit':'个文件'})
    for i,(path,data) in enumerate(staged.items(),1):
        store.replace(owner,pid,child(root,path),data,'按用户导入请求接收外部项目材料')
        if progress and (i%10==0 or i==len(staged)):progress('files','正在保存项目文件',{'done':i,'total':len(staged),'unit':'个文件'})
    if progress:progress('document','正在整理项目稿件')
    revision=None
    if document:
        current=store.manuscript(owner,pid)
        for key in ('content','title','template','comments','translation','references'):
            if key in document:current[key]=document[key]
        current['reason']='从用户选择的外部项目快照导入'
        revision=store.save_manuscript(owner,pid,current)['revision']
    if progress:progress('catalog','正在更新项目材料记录')
    receipt={'imported':now(),'format':'workbench-project.v2','source':meta.get('source','user selected local folder'),
        'files':len(staged),'manuscript_revision':revision,'omitted_runtime_files':omitted,
        'scope':'selected source files only; imported code and serialized figure runtimes were not executed'}
    atomic_json(root/'.workbench/material-import.json',receipt)
    config=project['config'];config['material_import']=receipt;store.update(owner,pid,config=config)
    return receipt
