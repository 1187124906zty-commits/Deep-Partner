import io
import json
import sqlite3
import zipfile

import pytest

from server.storage import Store,now
from server.material_import import import_bundle


def fixture(tmp_path):
    store=Store(tmp_path/'state');project=store.create('owner','水分扩散')
    return store,project['id']

def test_independent_runs_keep_objects_steps_and_restart_state(tmp_path):
    store,pid=fixture(tmp_path)
    first=store.job('owner',pid,'manuscript-translate',{'subject':'第一份稿件','target':'en'})
    second=store.job('owner',pid,'manuscript-translate',{'subject':'第二份稿件','target':'zh-CN'})
    store.set_job(first,status='running')
    store.set_job(first,step='translate',counts={'done':12,'total':30,'unit':'段'},stage='正在翻译段落')
    restarted=Store(store.root)
    rows={j['id']:j for j in restarted.jobs('owner',pid)}
    assert len(rows)==2 and first!=second
    assert rows[first]['task']['title']=='翻译 · 第一份稿件 · 英文'
    assert rows[second]['task']['title']=='翻译 · 第二份稿件 · 中文'
    assert rows[first]['task']['counts']=={'done':12,'total':30,'unit':'段','step':'translate'}
    assert rows[first]['task']['current_step']=='translate'
    assert rows[second]['task']['current_step'] is None
    assert all(s['state']=='pending' for s in rows[second]['task']['steps'])

def test_failure_stops_at_real_step_and_does_not_complete_future_work(tmp_path):
    store,pid=fixture(tmp_path);jid=store.job('owner',pid,'slides-export')
    store.set_job(jid,status='running',step='build');store.set_job(jid,step='render',stage='正在渲染')
    store.set_job(jid,status='failed',stage='预览生成失败',error='渲染进程返回错误')
    task=store.jobs('owner',pid)[0]['task']
    assert task['current_step']=='render' and task['completed_steps']==1
    assert [s['state'] for s in task['steps']]==['done','failed','pending','pending','pending']
    assert task['events'][-1]['state']=='failed'
    with pytest.raises(ValueError):store.set_job(jid,step='invented-step')

def test_completed_task_marks_unrun_optional_review_as_skipped(tmp_path):
    store,pid=fixture(tmp_path);jid=store.job('owner',pid,'manuscript-export')
    store.set_job(jid,status='running');store.set_job(jid,step='layout');store.set_job(jid,step='save')
    store.set_job(jid,status='completed',result={'name':'结果.docx','url':'/research/api/projects/'+pid+'/download?area=manuscript&name=result.docx'})
    task=store.jobs('owner',pid)[0]['task']
    assert [s['state'] for s in task['steps']]==['done','done','done','skipped']
    assert len(task['artifacts'])==1

def test_download_wait_retry_and_existing_phase_receipts(tmp_path):
    store,pid=fixture(tmp_path);jid=store.job('owner',pid,'literature-download',{'subject':'具体论文题名'})
    store.set_job(jid,result={'phase':'queued','entry':{'title':'具体论文题名'}},stage='等待下载设备')
    task=store.jobs('owner',pid)[0]['task']
    assert task['waiting'] and task['steps'][0]['state']=='waiting'
    store.set_job(jid,status='running',result={'phase':'downloading'})
    store.set_job(jid,result={'phase':'validating'});store.set_job(jid,status='failed',error='PDF 身份未核对通过')
    assert store.jobs('owner',pid)[0]['task']['steps'][1]['state']=='failed'
    store.set_job(jid,status='queued',result={'phase':'queued'},error='')
    task=store.jobs('owner',pid)[0]['task']
    assert task['current_step']=='download' and task['completed_steps']==0
    assert task['steps'][1]['state']=='pending'
    assert any(e['state']=='failed' for e in task['events'])

def test_real_snapshot_import_emits_steps_and_file_count(tmp_path):
    store,pid=fixture(tmp_path);jid=store.job('owner',pid,'material-import',{'source_name':'模拟结果.zip'})
    output=io.BytesIO()
    with zipfile.ZipFile(output,'w') as archive:
        archive.writestr('workbench-import.json',json.dumps({'format':'workbench-project.v2','source':'task pipeline test'}))
        archive.writestr('project/docs/result.md','# 实际导入结果\n已保存的原文。')
    store.set_job(jid,status='running')
    result=import_bundle(store,'owner',pid,output.getvalue(),progress=lambda step,message,counts=None:store.set_job(jid,step=step,stage=message,counts=counts))
    store.set_job(jid,status='completed',result=result,stage='已完成')
    task=store.jobs('owner',pid)[0]['task']
    assert task['completed_steps']==4 and task['summary']=='已导入 1 个文件'
    assert (store.path('owner',pid)/'project/docs/result.md').read_text(encoding='utf8').startswith('# 实际导入结果')
    assert [e['step'] for e in task['events'] if e['state']=='running']==['inspect','files','document','catalog']

def test_legacy_records_are_readable_without_fabricated_step_history(tmp_path):
    store,pid=fixture(tmp_path);stamp=now()
    with store.db() as db:db.execute('INSERT INTO jobs(id,owner,project,kind,status,stage,created,updated,result) VALUES(?,?,?,?,?,?,?,?,?)',('legacy','owner',pid,'material-import','completed','已完成',stamp,stamp,'{"files":173}'))
    task=store.jobs('owner',pid)[0]['task']
    assert task['legacy'] and task['steps']==[] and task['summary']=='已导入 173 个文件'
    assert '水分扩散' in task['title']
    other=store.create('another','另一个账户')
    assert store.jobs('another',other['id'])==[]
    with pytest.raises(KeyError):store.jobs('another',pid)

def test_existing_database_gets_additive_tracking_column(tmp_path):
    folder=tmp_path/'old';folder.mkdir()
    with sqlite3.connect(folder/'workbench.sqlite3') as db:
        db.execute("CREATE TABLE jobs(id TEXT PRIMARY KEY,owner TEXT,project TEXT,kind TEXT,status TEXT,stage TEXT,created TEXT,updated TEXT,result TEXT DEFAULT '{}',error TEXT DEFAULT '')")
        db.execute("INSERT INTO jobs(id,result) VALUES('retained','{}')")
    Store(folder)
    with sqlite3.connect(folder/'workbench.sqlite3') as db:
        assert db.execute("SELECT tracking FROM jobs WHERE id='retained'").fetchone()==('{}',)


def test_receipt_metadata_does_not_invent_another_completion(tmp_path):
    store,pid=fixture(tmp_path);jid=store.job('owner',pid,'material-import')
    store.set_job(jid,status='running');store.set_job(jid,step='catalog');store.set_job(jid,status='completed',result={'files':1})
    before=store.jobs('owner',pid)[0]['task']['events']
    store.set_job(jid,result={'files':1,'name':'导入记录.md'})
    assert store.jobs('owner',pid)[0]['task']['events']==before


def test_saved_export_and_failed_review_remain_distinct(tmp_path):
    store,pid=fixture(tmp_path);jid=store.job('owner',pid,'manuscript-export')
    store.set_job(jid,status='running')
    for step in ['layout','save','review']:store.set_job(jid,step=step)
    store.set_job(jid,status='completed',result={'name':'清稿.pdf','quality':{'decision':'evaluation_failed','can_proceed':False,'reason':'评审服务未返回有效结果'}})
    row=store.jobs('owner',pid)[0]
    assert row['status']=='completed'
    assert row['task']['steps'][-1]['state']=='failed' and row['task']['completed_steps']==3
    assert row['task']['summary']=='产物已保存，阶段评审未完成'
