"""Object-level scientific figure drafts, exact exports and source-linked saving."""
from pathlib import Path
from io import BytesIO
import ast,hashlib,json,pickle,re,threading,uuid
import matplotlib
matplotlib.use('Agg')
from matplotlib import font_manager
from .figure_artists import artists,describe,apply_changes,layout_description
from .storage import child,atomic_json,now,Conflict

# These private fonts are installed by this workbench deployment, not shipped
# as web assets. Register them in each process without relying on old caches.
for font in Path('/usr/share/fonts/truetype/research-workbench').glob('*'):
    if font.suffix.lower() in ('.ttf','.ttc','.otf'):font_manager.fontManager.addfont(str(font))

render_lock=threading.RLock()


def registry_path(root):return Path(root)/'.workbench/figures/registry.json'


def read_registry(root):
    file=registry_path(root)
    return json.loads(file.read_text()) if file.exists() else {}


def snapshot_state(root,asset,folder):
    """A figure's trash entry retains its editable state as well as the PNG."""
    entry=read_registry(root).get(asset)
    if not entry:return
    archived=folder/Path(asset).name
    if entry.get('image_digest') and archived.is_file() and hashlib.sha256(archived.read_bytes()).hexdigest()!=entry['image_digest']:return
    source=Path(root)/'.workbench/figures'/entry['id'];current=source/'current.pkl'
    if not current.is_file():return
    (folder/'figure-state.pkl').write_bytes(current.read_bytes())
    style=source/'style.json'
    atomic_json(folder/'figure-state.json',{'asset':asset,'entry':entry,'style':json.loads(style.read_text()) if style.exists() else {}})


def restore_state(store,owner,pid,asset,folder):
    meta=folder/'figure-state.json';state=folder/'figure-state.pkl'
    if not meta.is_file() or not state.is_file():return
    root=store.path(owner,pid);value=json.loads(meta.read_text())
    if value['asset']!=asset:raise ValueError('历史图形索引不匹配')
    with render_lock:
        entries=read_registry(root);entry=value['entry'];entry['revision']=entries.get(asset,{}).get('revision',entry.get('revision',0))+1;entry['updated']=now()
        figure=pickle.loads(state.read_bytes());file=child(root/'project',asset);entry['image_digest']=hashlib.sha256(file.read_bytes()).hexdigest();entry['bound_modified']=file.stat().st_mtime_ns
        destination=root/'.workbench/figures'/entry['id'];destination.mkdir(parents=True,exist_ok=True);(destination/'current.pkl').write_bytes(state.read_bytes());(destination/'current.svg').write_text(svg(figure),encoding='utf8')
        style=value.get('style',{});style.update(revision=entry['revision'],updated=now());atomic_json(destination/'style.json',style)
        entries[asset]=entry;atomic_json(registry_path(root),entries);link_program(store,owner,pid,entry)
        for extension in ('pdf','svg'):
            output=BytesIO();figure.savefig(output,format=extension);store.replace(owner,pid,file.with_suffix('.'+extension),output.getvalue(),'恢复图形历史版本，同步导出文件')


def manuscript_links(root,asset):
    """Keep the author's embedded image until an explicit canvas save."""
    path=Path(root)/'.workbench/material-import.json'
    if not path.is_file():return set()
    return {link['image'] for link in json.loads(path.read_text()).get('linked_figures',[]) if link['asset']==asset}


def svg(figure):
    buffer=BytesIO()
    with matplotlib.rc_context({'svg.fonttype':'path','svg.hashsalt':'research-workbench'}):figure.savefig(buffer,format='svg',dpi=max(200,getattr(figure,'_workbench_export_dpi',300)),facecolor=figure.get_facecolor())
    return re.sub(r'<\?xml[^>]+\?>|<!DOCTYPE[^>]+>','',buffer.getvalue().decode('utf8'))


def register(root,asset,figure,plot_program='',compute_program=''):
    """Called by an authorized plotting program, never by deserializing API input."""
    root=Path(root);entries=read_registry(root);entry=entries.get(asset,{'id':uuid.uuid4().hex,'revision':0})
    folder=root/'.workbench/figures'/entry['id'];folder.mkdir(parents=True,exist_ok=True)
    with render_lock:
        describe(figure)
        blob=serialize_figure(figure)
        for name in ('source.pkl','current.pkl'):(folder/name).write_bytes(blob)
        (folder/'current.svg').write_text(svg(figure),encoding='utf8')
    image=child(root/'project',asset)
    entry.update(asset=asset,plot_program=plot_program,compute_program=compute_program,revision=entry['revision']+1,
      matplotlib=matplotlib.__version__,updated=now(),bound_modified=image.stat().st_mtime_ns if image.exists() else 0,
      image_digest=hashlib.sha256(image.read_bytes()).hexdigest() if image.exists() else '')
    entries[asset]=entry;atomic_json(registry_path(root),entries)
    return entry


def serialize_figure(figure):
    try:return pickle.dumps(figure,protocol=pickle.HIGHEST_PROTOCOL)
    except (AttributeError,pickle.PicklingError):
        import cloudpickle
        return cloudpickle.dumps(figure,protocol=pickle.HIGHEST_PROTOCOL)


def read_figure(root,asset):
    entry=read_registry(root).get(asset)
    if not entry:return None,None
    if not re.fullmatch(r'[a-f0-9]{32}',entry['id']):raise ValueError('图形对象索引无效')
    # Only our own runtime-created, project-isolated state can be loaded here.
    file=Path(root)/'.workbench/figures'/entry['id']/'current.pkl'
    if not file.is_file():return None,None
    return pickle.loads(file.read_bytes()),entry


def response(figure,entry):
    objects=describe(figure)
    return {'ready':True,'revision':entry['revision'],'updated':entry['updated'],'svg':svg(figure),'objects':objects,'layout':layout_description(figure),
      'figure':{'width':figure.get_figwidth(),'height':figure.get_figheight(),'dpi':getattr(figure,'_workbench_export_dpi',300),
        'facecolor':matplotlib.colors.to_hex(figure.get_facecolor()),'transparent':getattr(figure,'_workbench_transparent',False),
        'font_family':next((o['properties'].get('font_family') for o in objects if o['kind']=='text'),'DejaVu Sans'),
        'font_size':next((o['properties'].get('font_size') for o in objects if o['kind']=='ticks'),10),
        'font_weight':'normal','font_style':'normal','text_color':'#222222',
        **{key:next((o['properties']['font_size'] for o in objects if o.get('role') in roles and 'font_size' in o['properties']),10) for key,roles in {'title_size':['title'],'label_size':['xlabel','ylabel','zlabel','colorbar-label'],'tick_size':['x','y','z','colorbar-ticks'],'legend_size':['legend-text']}.items()},
        **getattr(figure,'_workbench_typography',{})},
      'colormaps':['viridis','cividis','plasma','inferno','magma','turbo','coolwarm','RdBu_r','RdYlBu_r','YlGnBu','Blues','Greys','terrain','Spectral_r'],
      'fonts':sorted({f.name for f in font_manager.fontManager.ttflist}),
      'source':{'plot_program':entry.get('plot_program',''),'compute_program':entry.get('compute_program','')},'engine':'Matplotlib '+matplotlib.__version__}


def inspect(store,owner,pid,asset):
    store.get(owner,pid);root=store.path(owner,pid);image=child(root/'project',asset)
    if not image.is_file():raise KeyError('图片不存在')
    with render_lock:
        figure,entry=read_figure(root,asset)
        if figure is None:return {'ready':False,'reason':'此图尚未关联可编辑绘图对象','kind':'raster'}
        actual=hashlib.sha256(image.read_bytes()).hexdigest()
        if entry.get('image_digest') and actual!=entry['image_digest']:return {'ready':False,'reason':'原图已由其他程序更新，重新运行关联绘图程序后可继续对象编辑','kind':'raster'}
        if not entry.get('image_digest'):
            entry['image_digest']=actual;entries=read_registry(root);entries[asset]=entry;atomic_json(registry_path(root),entries)
        return response(figure,entry)


def edit_session(store,owner,pid,asset):
    with render_lock:
        result=inspect(store,owner,pid,asset)
        if not result.get('ready'):return result
        root=store.path(owner,pid);figure,entry=read_figure(root,asset);sid=uuid.uuid4().hex
        folder=root/'.workbench/figure-edit-sessions';folder.mkdir(parents=True,exist_ok=True)
        import time
        for old in folder.glob('*.json'):
            if time.time()-old.stat().st_mtime>86400:
                old.with_suffix('.pkl').unlink(missing_ok=True);old.unlink(missing_ok=True)
        (folder/(sid+'.pkl')).write_bytes(serialize_figure(figure))
        style=root/'.workbench/figures'/entry['id']/'style.json'
        atomic_json(folder/(sid+'.json'),{'asset':asset,'style':json.loads(style.read_text()) if style.exists() else {}})
        return {**result,'edit_session':sid}


def session_figure(root,asset,sid):
    if not re.fullmatch(r'[a-f0-9]{32}',sid):raise ValueError('图形编辑会话无效')
    folder=root/'.workbench/figure-edit-sessions';meta=folder/(sid+'.json');data=folder/(sid+'.pkl')
    if not meta.is_file() or not data.is_file():raise ValueError('编辑会话已过期，请重新打开图形')
    value=json.loads(meta.read_text())
    if value['asset']!=asset:raise ValueError('图形编辑会话不匹配')
    return pickle.loads(data.read_bytes()),value.get('style',{})


def preview(store,owner,pid,asset,changes,revision,edit_session=''):
    store.get(owner,pid);root=store.path(owner,pid)
    with render_lock:
        figure,entry=read_figure(root,asset)
        if figure is None:raise ValueError('此图需要先由绘图程序提供可编辑对象')
        if entry['revision']!=revision:raise Conflict('此图已更新，请重新打开后继续')
        if entry.get('image_digest') and hashlib.sha256(child(root/'project',asset).read_bytes()).hexdigest()!=entry['image_digest']:raise Conflict('原图已更新，请重新加载当前图形')
        if edit_session:figure,_=session_figure(root,asset,edit_session)
        apply_changes(figure,changes)
        return {**response(figure,entry),'edit_session':edit_session}


def merge_styles(old,new,entries=None):
    previous_figure=dict(old.get('figure',{}));overall=new.get('figure',{})
    if 'font_size' in overall:
        for key in ('title_size','label_size','tick_size','legend_size'):previous_figure.pop(key,None)
    result={'figure':{**previous_figure,**overall},'objects':{key:dict(value) for key,value in old.get('objects',{}).items()}}
    # A new shared style replaces earlier local overrides of that same style.
    # Later local edits in this operation are merged below and remain explicit.
    for key,patch in result['objects'].items():
        entry=(entries or {}).get(key,{});kind=entry.get('kind');role=entry.get('role')
        typography=kind in ('text','ticks','legend') or bool(re.search(r'(?:-(?:title|xlabel|ylabel|zlabel|[xyz]ticks|legend|text\d+|label|ticks))$|^figure-text',key))
        for name in ('font_family','font_size','font_weight','font_style','text_color'):
            if name in overall and typography:
                patch.pop('color' if name=='text_color' else name,None)
        role_size='title_size' if role=='title' else 'label_size' if role in ('xlabel','ylabel','zlabel','colorbar-label') else 'tick_size' if kind=='ticks' else 'legend_size' if kind=='legend' or role=='legend-text' else ''
        if role_size and role_size in overall:patch.pop('font_size',None)
    for key,patch in new.get('objects',{}).items():
        previous=result['objects'].get(key,{});merged={**previous,**patch}
        if 'matplotlib' in patch:merged['matplotlib']={**previous.get('matplotlib',{}),**patch['matplotlib']}
        if 'move' in patch:merged['move']={axis:previous.get('move',{}).get(axis,0)+patch['move'].get(axis,0) for axis in ('dx','dy')}
        result['objects'][key]=merged
    if old.get('layout') or new.get('layout'):
        before=old.get('layout',{});after=new.get('layout',{})
        cells={**before.get('cells',{})}
        for key,cell in after.get('cells',{}).items():cells[key]={**cells.get(key,{}),**cell}
        result['layout']={**before,**after,'cells':cells}
    return result


def link_program(store,owner,pid,entry):
    root=store.path(owner,pid);program=entry.get('plot_program','')
    if not program or not program.endswith('.py'):return
    path=child(root/'project',program)
    if not path.is_file():return
    helper=root/'.workbench/figure_runtime.py'
    helper.write_bytes(Path(__file__).with_name('figure_artists.py').read_bytes())
    source=path.read_text(encoding='utf8')
    edits={}
    for asset,item in read_registry(root).items():
        if item.get('plot_program')!=program:continue
        style=root/'.workbench/figures'/item['id']/'style.json'
        if style.exists():edits[asset]=json.loads(style.read_text()).get('changes',{})
    tree=ast.parse(source);position=0
    for node in tree.body:
        if isinstance(node,ast.Expr) and isinstance(node.value,ast.Constant) and isinstance(node.value.value,str) or isinstance(node,ast.ImportFrom) and node.module=='__future__':position=node.end_lineno
        else:break
    depth=len(Path(program).parts)
    from pprint import pformat
    block=f'''\n# research-workbench: figure styles — edited parameters only\nimport importlib.util as _wb_importlib\n_wb_edits={pformat(edits,width=95,sort_dicts=False)}\n_wb_root=__import__('pathlib').Path(__file__).resolve().parents[{depth}]\n_wb_helper=_wb_root/'.workbench/figure_runtime.py'\nif _wb_helper.is_file():\n    _wb_spec=_wb_importlib.spec_from_file_location('workbench_figure_runtime',_wb_helper)\n    _wb_module=_wb_importlib.module_from_spec(_wb_spec)\n    _wb_spec.loader.exec_module(_wb_module)\n    _wb_module.install(_wb_root,overrides=_wb_edits)\n# end research-workbench figure styles\n'''
    if '# research-workbench: figure styles' in source:
        updated=re.sub(r'\n?# research-workbench: figure styles[^\n]*\n.*?# end research-workbench figure styles\n?',lambda _:block,source,flags=re.S)
    else:
        lines=source.splitlines(keepends=True);updated=''.join(lines[:position])+block+''.join(lines[position:])
    compile(updated,str(path),'exec');store.replace(owner,pid,path,updated.encode(),'图布保存样式，绘图程序重跑时自动复用')


def save(store,owner,pid,asset,changes,revision,reason='调整图形样式',edit_session=''):
    store.get(owner,pid);root=store.path(owner,pid);file=child(root/'project',asset)
    if not file.is_file():raise KeyError('原图不存在')
    if not reason.strip():reason='调整图形样式'
    with render_lock,store.lock(pid),store.lock(owner):
        figure,entry=read_figure(root,asset)
        if figure is None:raise ValueError('此图没有可编辑对象')
        if entry['revision']!=revision:raise Conflict('此图已被其他操作更新，未覆盖新图')
        if entry.get('image_digest') and hashlib.sha256(file.read_bytes()).hexdigest()!=entry['image_digest']:raise Conflict('原图已被绘图程序更新，未覆盖新图')
        base_style=None
        if edit_session:figure,base_style=session_figure(root,asset,edit_session)
        original=file.read_bytes();apply_changes(figure,changes)
        folder=root/'.workbench/figures'/entry['id'];style_path=folder/'style.json'
        prior=base_style if base_style is not None else json.loads(style_path.read_text()) if style_path.exists() else {}
        style={'revision':entry['revision']+1,'changes':merge_styles(prior.get('changes',{}),changes,artists(figure)),'reason':reason[:200],'updated':now()}
        exports={};rendered={}
        for extension in ('png','pdf','svg'):
            buffer=BytesIO()
            with matplotlib.rc_context({'svg.fonttype':'none'}):figure.savefig(buffer,format=extension,dpi=getattr(figure,'_workbench_export_dpi',300),transparent=getattr(figure,'_workbench_transparent',False))
            rendered[extension]=buffer.getvalue()
        from .workspace_files import require_space
        old_state=folder/'current.pkl';state_bytes=old_state.stat().st_size if old_state.is_file() else 0
        linked_count=len(manuscript_links(root,asset));program=child(root/'project',entry['plot_program']) if entry.get('plot_program') else None
        require_space(store,owner,sum(len(v) for v in rendered.values())+state_bytes+linked_count*len(rendered['png'])+(program.stat().st_size+10000 if program and program.is_file() else 10000))
        for extension,data in rendered.items():
            target=file.with_suffix('.'+extension);store.replace(owner,pid,target,data,reason[:200]);exports[extension]=target.relative_to(root).as_posix()
        # Manuscript figures keep their stable URLs. All source-linked copies update.
        references=[]
        linked_images=manuscript_links(root,asset)
        for image in (root/'manuscript/assets').glob('*'):
            if image.is_file() and (image.name in linked_images or image.stat().st_size==len(original) and image.read_bytes()==original):
                store.replace(owner,pid,image,file.read_bytes(),reason[:200]);references.append(image.relative_to(root).as_posix())
        (folder/'current.pkl').write_bytes(serialize_figure(figure));(folder/'current.svg').write_text(svg(figure),encoding='utf8')
        atomic_json(style_path,style);entry.update(revision=style['revision'],updated=style['updated'],bound_modified=file.stat().st_mtime_ns,image_digest=hashlib.sha256(file.read_bytes()).hexdigest())
        entries=read_registry(root);entries[asset]=entry;atomic_json(registry_path(root),entries);link_program(store,owner,pid,entry)
        if references:
            # Changing an image invalidates rendered paper/export caches even when text is unchanged.
            document=store.manuscript(owner,pid);store.save_manuscript(owner,pid,document)
        from .annotations import event
        event(store,owner,pid,'figure.updated',{'asset':asset,'reason':reason,'revision':entry['revision'],'exports':exports,'references':references,'changes':changes})
        return {'saved':True,'revision':entry['revision'],'updated':entry['updated'],'exports':exports,'updated_references':references,'reason':reason}
