"""Durable idea-memo → owning Deep Partner project synchronization."""
from pathlib import Path
import argparse,json,os,sqlite3,subprocess,tempfile

HOME=Path(os.environ.get('CODEX_HOME',Path.home()/'.codex'))
STATE=HOME/'deep-partner'
DP=Path(os.environ.get('DEEP_PARTNER_CLI',Path.home()/'AppData/Local/Programs/Deep partner/dp.exe'))

def db():
    STATE.mkdir(parents=True,exist_ok=True);connection=sqlite3.connect(STATE/'memo-sync.sqlite3',timeout=15)
    connection.row_factory=sqlite3.Row
    connection.execute('CREATE TABLE IF NOT EXISTS bindings(memo TEXT PRIMARY KEY,project TEXT NOT NULL,status TEXT NOT NULL DEFAULT \'pending\',error TEXT NOT NULL DEFAULT \'\')')
    columns={r[1] for r in connection.execute('PRAGMA table_info(bindings)')}
    if 'last_sequence' not in columns:connection.execute('ALTER TABLE bindings ADD COLUMN last_sequence INTEGER NOT NULL DEFAULT 0')
    return connection

def invoke(*args):
    result=subprocess.run([str(DP),*map(str,args)],capture_output=True,text=True,encoding='utf8',timeout=120)
    if result.returncode:raise ValueError((result.stderr or result.stdout)[-1800:])
    return json.loads(result.stdout)

def sync(memo_id,project=None,root=None):
    root=Path(root) if root else HOME/'idea-memo'
    with db() as connection:
        if project:
            # Resolve an actual owned project before persisting the binding.
            projects=invoke('project','list','--json')['projects']
            matches=[p for p in projects if p['id']==project or p['name']==project]
            if len(matches)!=1:raise ValueError('请指定唯一的真实项目 ID')
            project=matches[0]['id']
            old=connection.execute('SELECT project FROM bindings WHERE memo=?',(memo_id,)).fetchone()
            if old and old['project']!=project:raise ValueError('备忘录已绑定其他项目；请明确迁移材料后再更改')
            connection.execute('INSERT INTO bindings(memo,project) VALUES(?,?) ON CONFLICT(memo) DO UPDATE SET status=\'pending\'',(memo_id,project))
        row=connection.execute('SELECT * FROM bindings WHERE memo=?',(memo_id,)).fetchone()
        if not row:return {'status':'local_only','reason':'memo has no explicit project binding'}
        project=row['project'];last_sequence=row['last_sequence'];connection.execute("UPDATE bindings SET status='pending' WHERE memo=?",(memo_id,))
    try:
        with sqlite3.connect(root/'memos.sqlite3') as source:
            source.row_factory=sqlite3.Row
            memo=source.execute('SELECT id,title,thread,updated FROM memos WHERE id=?',(memo_id,)).fetchone()
            if not memo:raise ValueError('备忘录不存在')
            events=[dict(r) for r in source.execute('SELECT sequence,kind,event_key,data,time FROM events WHERE memo=? AND sequence>? ORDER BY sequence',(memo_id,last_sequence))]
        for event in events:event['data']=json.loads(event['data'])
        body_path=root/'notes'/f'{memo_id}.md'
        body=body_path.read_text(encoding='utf8') if body_path.is_file() else '备忘录正文尚未整理；回查材料已保存。'
        record={'id':'memo-'+memo_id,'title':memo['title'],'content':body[:140000],
                'nodes':[{'id':'memo:'+memo_id,'kind':'memo','label':memo['title'][:300],'detail':body[:30000],'status':'recorded',
                          'evidence_level':'author_and_public_research_notes','evidence_refs':[{'path':'docs/idea-memo/'+memo_id+'.md'}]}]}
        with tempfile.TemporaryDirectory(prefix='partner-memo-') as directory:
            directory=Path(directory);note=directory/(memo_id+'.md');note.write_text(body,encoding='utf8')
            latest=max([event['sequence'] for event in events],default=last_sequence)
            materials=directory/(memo_id+'-materials-'+str(latest)+'.json');materials.write_text(json.dumps({'memo':dict(memo),'events':events},ensure_ascii=False,indent=2),encoding='utf8')
            uploaded=invoke('project','upload','--project',project,str(note),str(materials),'--category','documents','--path','docs/idea-memo','--json')
            payload=directory/'record.json';payload.write_text(json.dumps(record,ensure_ascii=False),encoding='utf8')
            receipt=invoke('workflow','record','--project',project,'--file',payload)
        with db() as connection:connection.execute("UPDATE bindings SET status='synced',error='',last_sequence=? WHERE memo=?",(latest,memo_id))
        return {'status':'synced','memo_id':memo_id,'project_id':project,'record':receipt,'files':uploaded}
    except Exception as error:
        with db() as connection:connection.execute("UPDATE bindings SET status='pending',error=? WHERE memo=?",(str(error)[-1800:],memo_id))
        return {'status':'pending','memo_id':memo_id,'project_id':project,'error':str(error)[-1800:],'local_copy_retained':True}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--memo',required=True);p.add_argument('--project');p.add_argument('--root');a=p.parse_args()
    print(json.dumps(sync(a.memo,a.project,a.root),ensure_ascii=False))
