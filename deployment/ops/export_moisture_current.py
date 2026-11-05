"""Export the owner's original website project without importing another account."""
from pathlib import Path
import json,subprocess,sys,tarfile
ROOT=Path(__file__).resolve().parents[1]
TARGET=Path('D:/博士工作/博士项目/水分扩散/2026-11-2')
sys.path.insert(0,'D:/Development/research-workbench/scripts')
from deploy import remote
def main():
    code='''from pathlib import Path
import sqlite3,json,tarfile,io,os
pid='05a893386c09449d88366cf6dfdc825f'
db=sqlite3.connect('/srv/deeptutor/data/research-workbench/workbench.sqlite3');db.row_factory=sqlite3.Row
r=dict(db.execute('SELECT * FROM projects WHERE id=?',(pid,)).fetchone());config=json.loads(r['config'])
root=Path('/srv/deeptutor/workspaces')/Path(config['project_root']).relative_to('/workspace')
files=[];excluded=[]
for p in root.rglob('*'):
 if not p.is_file() or p.is_symlink():continue
 rel=p.relative_to(root);parts=rel.parts
 keep=parts[0] in ('project','manuscript','slides','literature') or str(rel) in ('AGENTS.md','.workbench/remote-data.json') or str(rel).startswith('.workbench/figures/')
 if not keep or any(x in parts for x in ('.trash','.git','.venv','node_modules','__pycache__')):continue
 files.append((p,rel.as_posix()))
output=Path('/srv/research-workbench/moisture-current-export.tar')
manifest={'format':'workbench-project.v2','name':r['name'],'source_project_id':pid,'source_workspace_id':r['native_id'],'source_account_id':r['owner'],'snapshot':'manuscript/main.json','source':'author-requested website export 2026-11-02','imported_into_current_account':False,'files':[{'path':name,'bytes':p.stat().st_size} for p,name in files],'excluded':'runtime caches, old trash, reader caches and account credentials; figure runtime data retained as inert source for manual review'}
with tarfile.open(output,'w') as archive:
 for p,name in files:archive.add(p,arcname=name,recursive=False)
 for name,value in [('workbench-import.json',manifest),('导出来源.json',{'project_id':pid,'name':r['name'],'native_id':r['native_id'],'created':r['created'],'updated':r['updated'],'account_id':r['owner'],'files':len(files),'bytes':sum(p.stat().st_size for p,_ in files)})]:
  data=json.dumps(value,ensure_ascii=False,indent=2).encode();info=tarfile.TarInfo(name);info.size=len(data);archive.addfile(info,io.BytesIO(data))
os.chmod(output,0o644)
print(json.dumps({'archive':str(output),'files':len(files),'source_bytes':sum(p.stat().st_size for p,_ in files),'archive_bytes':output.stat().st_size,'source_project_id':pid}))
'''
    receipt=json.loads(remote(code,timeout=120,root=True));TARGET.mkdir(parents=True,exist_ok=True)
    archive=TARGET/'网站当前项目.tar'
    subprocess.run(['scp','-q','papers-research:'+receipt['archive'],str(archive)],check=True,timeout=600)
    assert archive.stat().st_size==receipt['archive_bytes']
    folder=TARGET/'网站项目'
    folder.mkdir(exist_ok=True)
    with tarfile.open(archive) as source:
        assert all((folder/m.name).resolve().is_relative_to(folder.resolve()) for m in source.getmembers())
        source.extractall(folder,filter='data')
    meta=json.loads((folder/'workbench-import.json').read_text(encoding='utf8'))
    assert all((folder/f['path']).is_file() and (folder/f['path']).stat().st_size==f['bytes'] for f in meta['files'])
    receipt.update({'local_folder':str(folder),'local_archive':str(archive),'verified_files':len(meta['files']),'imported':False})
    (TARGET/'整理回执.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2),encoding='utf8')
    (ROOT/'reports/moisture-current-export.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2),encoding='utf8')
    (TARGET/'说明.md').write_text('# 水分扩散网站资料\n\n网站项目/保存原网站另一账户下的当前程序、数据、稿件、导出文件、文献及图形编辑源资料。已核对文件清单与大小。未导入当前账户，也未改动原网站项目。\n\n测试导入时选择“网站项目”文件夹；workbench-import.json说明材料映射。图形运行时对象保留为源资料，普通导入不会自动执行或反序列化它们。阅读缓存、垃圾箱和账户凭据不在本次整理中。\n',encoding='utf8')
    print(json.dumps(receipt,ensure_ascii=False))
if __name__=='__main__':main()
