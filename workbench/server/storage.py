"""One current research project, reversible replacement and account ownership."""
from __future__ import annotations
from collections import Counter
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
import json
import mimetypes
import os
import re
import shutil
import sqlite3
import threading
import uuid

STANDARD_DIRS = ('src','data','results','docs')
LABELS = {'src':'源程序','configs':'配置','scripts':'运行脚本','tests':'测试','data':'数据',
          'results':'结果','figures':'图表','notebooks':'笔记本','docs':'说明'}
HIDDEN = {'.git','.gitkeep','__pycache__','.DS_Store','.workbench','.trash','.venv','node_modules'}


def now():
    return datetime.now(timezone.utc).isoformat()


def atomic_json(path: Path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    pending = path.with_name('.'+path.name+'.pending')
    pending.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf8')
    os.replace(pending, path)


def child(root: Path, relative: str, *, allow_root=False):
    raw = str(relative).replace('\\','/')
    parts = PurePosixPath(raw)
    if '\x00' in raw or parts.is_absolute() or any(p in ('..',) for p in parts.parts):
        raise ValueError('文件路径无效')
    root = root.resolve()
    target = root.joinpath(*parts.parts)
    if any(p.is_symlink() for p in [target,*target.parents] if p != root and root in p.parents):
        raise ValueError('不通过符号链接读取项目外的文件')
    target = target.resolve()
    if not target.is_relative_to(root) or (target == root and not allow_root):
        raise ValueError('文件路径超出当前项目')
    return target


def file_type(path: Path):
    return path.suffix.removeprefix('.').upper() or ('GIT' if path.name.startswith('.git') else 'TEXT')


class Conflict(ValueError): pass


class Store:
    def __init__(self, root):
        self.root=Path(root).resolve(); self.root.mkdir(parents=True,exist_ok=True)
        self.locks: dict[str,threading.RLock] = {}
        with self.db() as db:
            db.executescript('''CREATE TABLE IF NOT EXISTS projects(
              id TEXT PRIMARY KEY, owner TEXT NOT NULL, name TEXT NOT NULL,
              native_id TEXT NOT NULL DEFAULT '', created TEXT NOT NULL, updated TEXT NOT NULL,
              config TEXT NOT NULL DEFAULT '{}');
              CREATE TABLE IF NOT EXISTS trash(id TEXT PRIMARY KEY,owner TEXT NOT NULL,
              project TEXT NOT NULL,path TEXT NOT NULL,original TEXT NOT NULL,reason TEXT NOT NULL,
              created TEXT NOT NULL,size INTEGER NOT NULL);
              CREATE TABLE IF NOT EXISTS jobs(id TEXT PRIMARY KEY,owner TEXT NOT NULL,
              project TEXT NOT NULL,kind TEXT NOT NULL,status TEXT NOT NULL,
              stage TEXT NOT NULL,created TEXT NOT NULL,updated TEXT NOT NULL,
              result TEXT NOT NULL DEFAULT '{}',error TEXT NOT NULL DEFAULT '');''')
            if 'tracking' not in {r['name'] for r in db.execute('PRAGMA table_info(jobs)')}:
                db.execute("ALTER TABLE jobs ADD COLUMN tracking TEXT NOT NULL DEFAULT '{}'")

    @contextmanager
    def db(self):
        db=sqlite3.connect(self.root/'workbench.sqlite3',timeout=20)
        db.row_factory=sqlite3.Row
        try: yield db; db.commit()
        finally: db.close()

    def lock(self, key):
        return self.locks.setdefault(key,threading.RLock())

    def path(self, owner, project):
        if not re.fullmatch(r'[a-f0-9]{32}',project): raise KeyError('项目不存在')
        with self.db() as db:row=db.execute('SELECT config FROM projects WHERE id=? AND owner=?',(project,owner)).fetchone()
        if row:
            location=json.loads(row['config']).get('project_root')
            if location:
                target=Path(location).resolve()
                if not any(target.is_relative_to(Path(x).resolve()) for x in os.environ.get('WORKBENCH_NATIVE_ROOTS','/workspace:/app/data').split(os.pathsep)):
                    raise ValueError('原生工作区不在已挂载目录中')
                return target
        owner_dir=uuid.uuid5(uuid.NAMESPACE_URL,owner).hex
        return self.root/'owners'/owner_dir/project

    def bind_native(self,owner,pid,native):
        with self.lock(pid):
            old=self.path(owner,pid);new=Path(native['path']).resolve()
            if not any(new.is_relative_to(Path(x).resolve()) for x in os.environ.get('WORKBENCH_NATIVE_ROOTS','/workspace:/app/data').split(os.pathsep)):
                raise ValueError('原生工作区没有挂载到工作台')
            if not new.is_dir():raise ValueError('原生工作区目录不可见')
            for item in old.iterdir():
                if (new/item.name).exists():raise ValueError('新建工作区中出现同名内容，保留原文等待处理')
            for item in old.iterdir():shutil.move(str(item),str(new/item.name))
            config=self.get(owner,pid)['config'];config['project_root']=str(new)
            self.update(owner,pid,native_id=native['workspace_id'],config=config)
            old.rmdir()
        return self.get(owner,pid)

    def get(self, owner, pid):
        with self.db() as db: row=db.execute('SELECT * FROM projects WHERE owner=? AND id=?',(owner,pid)).fetchone()
        if row is None: raise KeyError('项目不存在')
        return {**dict(row),'config':json.loads(row['config']),'root':str(self.path(owner,pid))}

    def list(self, owner, include_archived=False):
        with self.db() as db: rows=db.execute('SELECT id FROM projects WHERE owner=? ORDER BY updated DESC',(owner,)).fetchall()
        projects=[self.get(owner,r['id']) for r in rows]
        return [p for p in projects if include_archived or not p['config'].get('archived')]

    def create(self, owner, name):
        name=name.strip()
        if not name or len(name)>100: raise ValueError('项目名称为1至100字')
        pid=uuid.uuid4().hex; root=self.path(owner,pid)
        program=root/'project'
        for folder in STANDARD_DIRS:
            path=program/folder;path.mkdir(parents=True,exist_ok=True);(path/'.gitkeep').touch()
        for folder in ['manuscript/assets','manuscript/exports','slides/exports','releases/latest','.trash']:
            (root/folder).mkdir(parents=True,exist_ok=True)
        (program/'README.md').write_text(f'# {name}\n\n## 运行\n\n在此记录环境、输入与复现命令。\n\n## 目录\n\n- src：计算、绘图及任务相关程序\n- data：输入数据\n- results：计算输出与图表\n- docs：项目说明\n\n目录内部按实际任务组织，默认不预设子目录。\n',encoding='utf8')
        (program/'.gitignore').write_text('__pycache__/\n.venv/\n.env\n*.pyc\n.pytest_cache/\n.DS_Store\n',encoding='utf8')
        (program/'pyproject.toml').write_text('[project]\nname = "research-project"\nversion = "0.1.0"\nrequires-python = ">=3.10"\ndependencies = []\n',encoding='utf8')
        with self.db() as db:db.execute('INSERT INTO projects(id,owner,name,created,updated) VALUES(?,?,?,?,?)',(pid,owner,name,now(),now()))
        return self.get(owner,pid)

    def update(self, owner, pid, **fields):
        with self.lock(pid):
            project=self.get(owner,pid)
            for key in ('name','native_id','config'):
                if key in fields:project[key]=fields[key]
            with self.db() as db:db.execute('UPDATE projects SET name=?,native_id=?,config=?,updated=? WHERE id=? AND owner=?',(project['name'],project['native_id'],json.dumps(project['config'],ensure_ascii=False),now(),pid,owner))
        return self.get(owner,pid)

    def touch(self, owner,pid):
        self.get(owner,pid)
        with self.db() as db:db.execute('UPDATE projects SET updated=? WHERE id=?',(now(),pid))

    def inventory(self, owner,pid,relative='',mode='all'):
        root=self.path(owner,pid)/'project'; self.get(owner,pid)
        directory=child(root,relative,allow_root=True)
        if not directory.is_dir():raise KeyError('目录不存在')
        index=self.path(owner,pid)/'.workbench/file-index.json'
        file_index=json.loads(index.read_text()) if index.exists() else {}
        imported=self.path(owner,pid)/'.workbench/material-import.json'
        imported_at=json.loads(imported.read_text()).get('imported') if imported.exists() else None
        result=[]
        def matches(file):
            if mode=='all':return True
            suffix=file.suffix.lower()
            if mode=='images':return suffix in {'.png','.jpg','.jpeg','.webp','.gif','.svg','.eps'} or suffix=='.pdf' and (any(v in {'figures','plots','results','images'} for v in file.relative_to(root).parts[:-1]) or re.search(r'fig|plot|chart|图',file.name,re.I))
            if mode=='code':return suffix in {'.py','.pyw','.ipynb','.m','.r','.jl','.f','.f90','.f95','.for','.c','.cc','.cpp','.h','.hpp','.rs','.go','.java','.js','.jsx','.ts','.tsx','.sh','.bat','.ps1','.sbatch','.json','.yaml','.yml','.toml','.ini','.cfg','.csv','.mat','.npy','.npz','.h5','.hdf5','.dat','.log','.sql'} or file.name.lower().startswith(('readme','requirements','cmakelists','dockerfile'))
            raise ValueError('文件视图无效')
        for path in sorted(directory.iterdir(),key=lambda p:(not p.is_dir(),p.name.lower())):
            if path.name in HIDDEN or path.is_symlink():continue
            types=Counter();size=0;count=0
            files=[p for p in path.rglob('*') if p.is_file() and not p.is_symlink() and not any(x in HIDDEN for x in p.relative_to(path).parts)] if path.is_dir() else [path]
            files=[p for p in files if matches(p)]
            if mode!='all' and not files:continue
            for file in files:
                try:size+=file.stat().st_size;types[file_type(file)]+=1;count+=1
                except OSError:continue
            result.append({'name':path.name,'path':path.relative_to(root).as_posix(),'kind':'folder' if path.is_dir() else 'file','count':count,'size':size,'types':dict(types),'label':LABELS.get(path.name,''),'modified':path.stat().st_mtime,'uploaded':file_index.get('project/'+path.relative_to(root).as_posix(),{}).get('uploaded') or imported_at,'uploaded_source':'file index' if file_index.get('project/'+path.relative_to(root).as_posix()) else 'material import' if imported_at else 'unknown'})
        return {'path':relative,'items':result}

    def discard(self, owner,pid,path: Path,reason='替换旧版本'):
        root=self.path(owner,pid).resolve();self.get(owner,pid);path=path.resolve()
        if not path.is_relative_to(root) or path==root or not path.exists() or path.is_symlink():raise ValueError('只能移入当前项目的文件')
        original=path.relative_to(root).as_posix()
        if original=='project' or original.startswith('.trash/'):raise ValueError('不能移走项目根目录')
        if path.is_dir() and original in {'project/'+d for d in STANDARD_DIRS}|{'project/data','manuscript','slides','releases/latest'}:
            raise ValueError('标准目录保留；可以移走其中的文件')
        tid=uuid.uuid4().hex;dest=root/'.trash'/tid/path.name;dest.parent.mkdir(parents=True)
        size=sum(p.stat().st_size for p in path.rglob('*') if p.is_file() and not p.is_symlink()) if path.is_dir() else path.stat().st_size
        shutil.move(str(path),str(dest))
        if original.startswith('project/') and path.suffix.lower()=='.png':
            from .figures import snapshot_state
            snapshot_state(root,original[len('project/'):],dest.parent)
        with self.db() as db:db.execute('INSERT INTO trash VALUES(?,?,?,?,?,?,?,?)',(tid,owner,pid,str(dest),original,reason,now(),size))
        return tid

    def replace(self, owner,pid,path,data: bytes,reason='更新当前文件'):
        with self.lock(pid),self.lock(owner):
            from .workspace_files import require_space,record_file
            require_space(self,owner,len(data))
            prior=None
            if path.exists():prior=self.discard(owner,pid,path,reason)
            path.parent.mkdir(parents=True,exist_ok=True)
            pending=path.with_name('.'+path.name+'.upload');pending.write_bytes(data);os.replace(pending,path)
            record_file(self,owner,pid,path)
        self.touch(owner,pid)
        if prior:
            from .annotations import event
            event(self,owner,pid,'artifact.replaced',{'asset':path.relative_to(self.path(owner,pid)).as_posix(),'reason':reason,'trash_id':prior})

    def trash(self, owner,pid):
        self.get(owner,pid)
        from .workspace_files import describe_revision
        with self.db() as db:return [describe_revision(dict(r)) for r in db.execute('SELECT id,original,reason,created,size FROM trash WHERE owner=? AND project=? ORDER BY created DESC',(owner,pid))]

    def restore(self, owner,pid,tid):
        self.get(owner,pid)
        from .figures import render_lock
        with render_lock,self.lock(pid):
            with self.db() as db:row=db.execute('SELECT * FROM trash WHERE owner=? AND project=? AND id=?',(owner,pid,tid)).fetchone()
            if row is None:raise KeyError('回收记录不存在')
            dest=child(self.path(owner,pid),row['original'])
            previous_revision=self.manuscript(owner,pid)['revision'] if row['original']=='manuscript/main.json' else None
            if dest.exists():self.discard(owner,pid,dest,'恢复历史版本前保留当前稿件')
            dest.parent.mkdir(parents=True,exist_ok=True);shutil.move(row['path'],dest)
            if row['original'].startswith('project/') and dest.suffix.lower()=='.png':
                from .figures import restore_state
                restore_state(self,owner,pid,row['original'][len('project/'):],Path(row['path']).parent)
            if previous_revision is not None:
                document=json.loads(dest.read_text());document.update(revision=previous_revision+1,updated=now());atomic_json(dest,document)
            from .annotations import event
            event(self,owner,pid,'artifact.restored',{'asset':row['original'],'reason':row['reason']})
            with self.db() as db:db.execute('DELETE FROM trash WHERE id=?',(tid,))
            consumed=Path(row['path']).parent
            for name in ('figure-state.pkl','figure-state.json'):(consumed/name).unlink(missing_ok=True)
            if consumed.is_dir() and not any(consumed.iterdir()):consumed.rmdir()
            return {'restored':row['original']}

    def manuscript(self, owner,pid):
        self.get(owner,pid);path=self.path(owner,pid)/'manuscript/main.json'
        if path.exists():
            from .references import prepare
            return prepare(json.loads(path.read_text(encoding='utf8')),self.path(owner,pid))
        name=self.get(owner,pid)['name']
        return {'title':name,'template':'generic-zh' if re.search('[\u4e00-\u9fff]',name) else 'generic-en','revision':0,
                'content':{'type':'doc','content':[{'type':'paragraph'}]},'comments':[],'updated':None}

    def save_manuscript(self, owner,pid,value):
        with self.lock(pid),self.lock(owner):
            current=self.manuscript(owner,pid)
            if value.get('revision')!=current['revision']:raise Conflict('稿件已在其他窗口更新，请重新加载后继续')
            result={k:value.get(k,current.get(k)) for k in ('title','template','content','comments','translation','references')}
            from .references import prepare
            result=prepare(result,self.path(owner,pid))
            if result.get('translation') and (result['content']!=current['content'] or result['title']!=current['title']):
                result['translation']={**result['translation'],'stale':True}
            if not isinstance(result['content'],dict) or result['content'].get('type')!='doc':raise ValueError('稿件需要可编辑文档结构')
            if len(json.dumps(result))>12_000_000:raise ValueError('稿件过大，请将图片作为附件上传')
            from .workspace_files import require_space
            require_space(self,owner,len(json.dumps(result,ensure_ascii=False).encode()))
            result.update(revision=current['revision']+1,updated=now())
            target=self.path(owner,pid)/'manuscript/main.json'
            if target.exists() and any(result.get(k)!=current.get(k) for k in ('title','template','content')):
                from .workspace_files import paragraphs
                from difflib import SequenceMatcher
                changed=[op for op in SequenceMatcher(None,paragraphs(current),paragraphs(result),autojunk=False).get_opcodes() if op[0]!='equal']
                reason=(value.get('reason','更新论文正文')+' · '+str(len(changed))+' 处变化')[:180]
                archived=self.discard(owner,pid,target,reason)
                from .annotations import event
                event(self,owner,pid,'manuscript.revised',{'asset':'manuscript/main.json','from_revision':current['revision'],'to_revision':result['revision'],'reason':reason,'trash_id':archived})
            atomic_json(target,result)
            self.touch(owner,pid);return result

    def job(self, owner,pid,kind,context=None):
        from .task_workflows import create
        project=self.get(owner,pid);jid=uuid.uuid4().hex;stamp=now()
        tracking=create(kind,project,context)
        with self.db() as db:db.execute('INSERT INTO jobs(id,owner,project,kind,status,stage,created,updated,tracking) VALUES(?,?,?,?,?,?,?,?,?)',(jid,owner,pid,kind,'queued','等待开始',stamp,stamp,json.dumps(tracking,ensure_ascii=False)))
        return jid

    def set_job(self,jid,*,step=None,counts=None,**fields):
        from .task_workflows import advance
        allowed={'status','stage','result','error'}
        if set(fields)-allowed:raise ValueError('Unknown job field')
        fields['updated']=now()
        with self.lock('job:'+jid),self.db() as db:
            row=db.execute('SELECT tracking,status FROM jobs WHERE id=?',(jid,)).fetchone()
            if not row:raise KeyError('任务不存在')
            tracking=json.loads(row['tracking'])
            if tracking:fields['tracking']=json.dumps(advance(tracking,{'status':row['status'],**fields},fields['updated'],step=step,counts=counts),ensure_ascii=False)
            if 'result' in fields:fields['result']=json.dumps(fields['result'],ensure_ascii=False)
            db.execute('UPDATE jobs SET '+','.join(k+'=?' for k in fields)+' WHERE id=?',(*fields.values(),jid))

    def jobs(self,owner,pid):
        from .task_workflows import present
        project=self.get(owner,pid)
        with self.db() as db:rows=db.execute("SELECT * FROM jobs WHERE owner=? AND project=? ORDER BY CASE WHEN status IN ('queued','running','waiting_service') THEN 0 WHEN status IN ('waiting_input','paused') THEN 1 WHEN status IN ('failed','interrupted') THEN 2 ELSE 3 END,updated DESC LIMIT 200",(owner,pid)).fetchall()
        result=[]
        for raw in rows:
            row=dict(raw);row['result']=json.loads(row['result']);row['tracking']=json.loads(row['tracking']);row['task']=present(row,project);row.pop('tracking');result.append(row)
        return result
