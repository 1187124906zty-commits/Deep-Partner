"""Install source-bound examples into the current user's own native workspace."""
from pathlib import Path
import json,shutil
from .storage import atomic_json,child,now
from .native import call
from .slides import source_elements


def available(root):
    items=[]
    for path in sorted((root/'examples').glob('*/manifest.json')):
        value=json.loads(path.read_text(encoding='utf8'))
        item={k:value[k] for k in ('id','name','language','description','repository','article')}
        item['description']=item['description'].replace('结果图和汇报','结果图与参考汇报结构').replace('结果图和组会汇报','结果图与参考汇报结构')
        items.append(item)
    return items


def install(store,owner,pid,root,example):
    source=child(root/'examples',example);manifest=json.loads((source/'manifest.json').read_text(encoding='utf8'))
    destination=store.path(owner,pid)
    for file in (source/'project').rglob('*'):
        if not file.is_file():continue
        relative=file.relative_to(source/'project')
        store.replace(owner,pid,destination/'project'/relative,file.read_bytes(),'安装公开项目示例')
    figure_objects=source/'.workbench/figures'
    if figure_objects.is_dir():shutil.copytree(figure_objects,destination/'.workbench/figures',dirs_exist_ok=True)
    assets=destination/'manuscript/assets';assets.mkdir(parents=True,exist_ok=True)
    image=source/'project'/manifest['image'];shutil.copyfile(image,assets/image.name)
    document=json.loads((source/'manuscript.json').read_text(encoding='utf8'))
    def rewrite(node):
        if node.get('type')=='image':node['attrs'].update(src=f'/research/api/projects/{pid}/manuscript/assets/{image.name}',source_path=manifest['image'])
        for child in node.get('content',[]):rewrite(child)
    rewrite(document['content']);document.update(revision=0,comments=[])
    translated=document.pop('translation',None)
    document=store.save_manuscript(owner,pid,document)
    if translated:
        rewrite(translated['content']);translated['source_revision']=document['revision']
        document['translation']=translated;store.save_manuscript(owner,pid,document)
    # Keep the public example's authored plan as reading material. The PPT area
    # is populated only after the same explicit choices as any other project.
    store.replace(owner,pid,destination/'project/docs/示例汇报结构.json',(source/'slides.json').read_bytes(),'安装公开示例的参考结构')
    atomic_json(destination/'review/asset-index.json',{manifest['image']:{'plot_program':'src/plot_reference.py','compute_program':manifest['compute_program'],'updated':now()}})
    config=store.get(owner,pid)['config'];config.update(example=example,example_source=manifest['repository'])
    store.update(owner,pid,config=config)
    return manifest


async def attach_literature(request,store,owner,pid,root,manifest):
    project=store.get(owner,pid);scope='?dt_workspace='+project['native_id']
    existing=await call(request,'GET','/api/knowledge-bases?resource_library=true&dt_workspace='+project['native_id'])
    result=next((x for x in existing if x.get('name')==manifest['knowledge_base']),None)
    files=[]
    for paper in manifest['literature']:
        file=child(root/'examples',paper['file'])
        files.append(('files',(file.name,file.read_bytes(),'application/pdf')))
        files.append(('rel_paths',(None,file.name)))
    if result is None:
        result=await call(request,'POST','/api/knowledge-bases'+scope,data={'name':manifest['knowledge_base'],'rag_provider':'llamaindex','storage_workspace_id':project['native_id']},files=files)
    kb_id=result['id'];config=project['config'];config['knowledge_bases']=[kb_id];config['literature_import']={'papers':len(manifest['literature']),'task_id':result.get('task_id'),'downloader':'ScanSci native MCP','processed_at':now()}
    # This KB belongs to the newly created workspace and is already available
    # under its inherited native scope. Changing the allowlist during indexing
    # would request an exclusive maintenance lease and conflict with that task.
    config.pop('knowledge_error',None)
    return store.update(owner,pid,config=config)
