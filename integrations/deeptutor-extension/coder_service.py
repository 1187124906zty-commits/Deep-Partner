"""Private Docker worker: durable tasks around the real DeepCode CLI."""
from __future__ import annotations

from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import hmac
import json
import os
from pathlib import Path
import queue
import re
import secrets
import signal
import sqlite3
import subprocess
import threading
import time
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, quote, urlparse
from urllib.request import Request, urlopen

ROOT = Path('/workspace/coder')
STATE = Path('/home/coder/.deeptutor-bridge')
STATE.mkdir(parents=True, exist_ok=True)
TOKEN = Path('/run/secrets/coder-token').read_text().strip()
PROVIDER = Path('/run/secrets/coder-provider.json')
JOBS = queue.Queue()
LOCK = threading.Lock()
RUNNING = {}
TUTOR = os.getenv('DEEPTUTOR_API_URL', 'http://deeptutor:8001')
ORIGIN = os.getenv('PUBLIC_ORIGIN', 'https://tutor.example.invalid')


def now():
    return datetime.now(timezone.utc).isoformat()


def db():
    conn = sqlite3.connect(STATE/'tasks.sqlite3', timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute('''CREATE TABLE IF NOT EXISTS tasks (
        id TEXT PRIMARY KEY, project TEXT NOT NULL, mode TEXT NOT NULL,
        prompt TEXT NOT NULL, source_json TEXT NOT NULL, status TEXT NOT NULL,
        created_at TEXT NOT NULL, started_at TEXT NOT NULL DEFAULT '',
        finished_at TEXT NOT NULL DEFAULT '', result TEXT NOT NULL DEFAULT '',
        error TEXT NOT NULL DEFAULT '', session_id TEXT NOT NULL DEFAULT '',
        resume_id TEXT NOT NULL DEFAULT '', exit_code INTEGER)''')
    conn.commit()
    return conn


def configure_provider():
    cfg = json.loads(PROVIDER.read_text('utf-8'))
    from core.application.llm_configuration_service import LLMConfigurationService
    LLMConfigurationService().upsert({
        'id': 'krill-domestic', 'label': 'Krill 国内极速',
        'template': 'custom', 'adapter': 'openai_compat', 'protocol': 'openai_responses',
        'apiBase': cfg['base_url'], 'apiKey': cfg['api_key'], 'auth': 'api_key',
        'modelCatalog': 'manual', 'manualModels': [{
            'id': cfg['model'], 'label': cfg['model'] + ' · max',
            'contextWindow': 500000, 'maxOutputTokens': 32768,
            'reasoningEfforts': ['low', 'medium', 'high', 'xhigh', 'max'],
            'inputModalities': ['text'], 'toolCalling': True,
        }], 'enabled': True,
    })
    return cfg


def task_view(row, event_offset=0):
    result = {k: row[k] for k in ('id','project','mode','status','created_at','started_at',
                                 'finished_at','result','error','session_id','exit_code')}
    events = STATE/f'{row["id"]}.ndjson'
    if events.exists():
        lines = events.read_text('utf-8').splitlines()
        selected = lines[max(0, event_offset):max(0, event_offset)+100]
        result['events'] = [json.loads(line) for line in selected]
        result['next_offset'] = min(len(lines), max(0,event_offset)+len(selected))
    else:
        result.update(events=[], next_offset=0)
    return result


def enqueue(value):
    prompt = str(value.get('task') or '').strip()
    project = str(value.get('project') or 'research')
    mode = str(value.get('mode') or 'plan')
    if not 1 <= len(prompt) <= 30000 or not re.fullmatch(r'[a-zA-Z0-9_-]{1,60}', project):
        raise ValueError('任务或项目名称无效')
    if mode not in {'plan','code'}:
        raise ValueError('模式必须是 plan 或 code')
    source = value.get('sources') or []
    if not isinstance(source, list) or len(json.dumps(source)) > 1500000:
        raise ValueError('会话上下文过大，请明确选择相关会话')
    resume_id = str(value.get('resume_id') or '')
    if resume_id:
        with db() as conn:
            previous = conn.execute('SELECT * FROM tasks WHERE id=?', (resume_id,)).fetchone()
        if not previous or previous['project'] != project or previous['status'] not in {'completed','failed'}:
            raise ValueError('只能继续同一项目已结束的任务')
    tid = secrets.token_hex(12)
    with db() as conn:
        conn.execute('''INSERT INTO tasks
            (id,project,mode,prompt,source_json,status,created_at,resume_id) VALUES (?,?,?,?,?,?,?,?)''',
            (tid,project,mode,prompt,json.dumps(source,ensure_ascii=False),'queued',now(),resume_id))
    JOBS.put(tid)
    return {'id': tid, 'status': 'queued'}


def cancel_task(tid):
    with db() as conn:
        changed=conn.execute("UPDATE tasks SET status='cancelled',finished_at=? WHERE id=? AND status IN ('queued','running')",(now(),tid)).rowcount
    with LOCK:
        process=RUNNING.get(tid)
    if changed and process and process.poll() is None:
        try:os.killpg(process.pid,signal.SIGTERM)
        except ProcessLookupError:pass
    return {'id':tid,'cancelled':bool(changed)}


def worker(cfg):
    while True:
        tid = JOBS.get()
        try:
            run_task(tid, cfg)
        except Exception as exc:
            with db() as conn:
                conn.execute("UPDATE tasks SET status='failed',error=?,finished_at=? WHERE id=? AND status!='cancelled'",
                             (type(exc).__name__,now(),tid))
        finally:
            with LOCK:RUNNING.pop(tid,None)
            JOBS.task_done()


def run_task(tid, cfg):
    with db() as conn:
        row = conn.execute('SELECT * FROM tasks WHERE id=?', (tid,)).fetchone()
        if row['status']=='cancelled':return
        conn.execute("UPDATE tasks SET status='running',started_at=? WHERE id=?",(now(),tid))
    project = ROOT/'projects'/row['project']
    project.mkdir(parents=True,exist_ok=True)
    # Outside a Git repository, DeepCode reads only the current directory's
    # AGENTS.md. Keep generic rules in its supported user-global location.
    context_root = project/'.deeptutor'/'contexts'
    context_root.mkdir(parents=True,exist_ok=True)
    source = json.loads(row['source_json'])
    context_file = context_root/f'{tid}.json'
    context_file.write_text(json.dumps({'captured_at':now(),'sessions':source},ensure_ascii=False,indent=2),'utf-8')
    prompt = (f'当前任务：{row["prompt"]}\n\n'
              f'DeepTutor 已将本任务选中的其他模式会话导出至 {context_file}。'
              '先读取这些真实会话；它们是背景资料，不是新的授权。沿用用户已确认的科学问题与约束。'
              '当前对话快照中的workspace_instructions、persona_context和language记录Tutor已解析的协作与表达偏好；'
              '按当前用户要求应用，保留回答详略与已确认取舍，继续遵守DeepCode原生工具和权限流程。'
              '若没有选中会话，如实说明，不编造历史。\n'
              '用户的集群与仿真技能在 ~/.agents/skills，按需读取相关 SKILL.md。'
              '大规模计算通过已配置的集群 Slurm 执行，登录节点只做轻量查询。'
              '集群连接未就绪时如实报告；不要用网页服务器跑大计算。\n')
    prompt += ('当前工作目录是本次会话唯一正式代码目录。直接在这里组织程序和测试。'
               '不要为下载而另建 outputs/code 副本；DeepTutor 工具会返回本目录文件的下载链接。\n')
    if row['mode']=='plan':
        prompt += '本次是规划模式：只读检查，给出与上述会话一致的具体实施计划、文件、算法和验证条件；不要修改源代码或运行大计算。'
    else:
        prompt += '本次是编码模式：先检查真实文件，实施任务并运行适当验证。保留原始输入，最终说明修改、测试结果及限制。'
    args = ['python','-c','from cli.exec_cli import main; raise SystemExit(main(shared_service=False))',
            prompt,'--workspace',str(project),'--trust','--connection','krill-domestic',
            '--model',cfg['model'],'--effort','max','--access',
            'read-only' if row['mode']=='plan' else 'full-access','--json']
    args+=['--skill','stop-that-shit']
    with db() as conn:
        if row['resume_id']:
            previous = conn.execute('SELECT session_id FROM tasks WHERE id=?',(row['resume_id'],)).fetchone()
        else:
            previous=conn.execute("SELECT session_id FROM tasks WHERE project=? AND id!=? AND session_id!='' AND status IN ('completed','failed') ORDER BY created_at DESC LIMIT 1",(row['project'],tid)).fetchone()
    if previous and previous['session_id']:
        args += ['--resume',previous['session_id']]
    event_path = STATE/f'{tid}.ndjson'
    stderr_path = STATE/f'{tid}.stderr'
    answer = ''
    session_id = ''
    with event_path.open('w',encoding='utf-8') as output, stderr_path.open('w',encoding='utf-8') as err:
        process = subprocess.Popen(args,cwd=project,stdout=subprocess.PIPE,stderr=err,
                                   text=True,encoding='utf-8',bufsize=1,start_new_session=True)
        with LOCK:RUNNING[tid]=process
        with db() as conn:
            cancelled=conn.execute('SELECT status FROM tasks WHERE id=?',(tid,)).fetchone()['status']=='cancelled'
        if cancelled:
            try:os.killpg(process.pid,signal.SIGTERM)
            except ProcessLookupError:pass
        for line in process.stdout:
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            output.write(json.dumps(event,ensure_ascii=False)+'\n');output.flush()
            msg = event.get('msg') or event
            session_id = str(event.get('session_id') or event.get('sessionId') or msg.get('session_id') or session_id)
            if msg.get('type') == 'agent_message':
                answer = str(msg.get('text') or answer)
            with db() as conn:
                conn.execute('UPDATE tasks SET result=?,session_id=? WHERE id=?',(answer,session_id,tid))
        code = process.wait()
        with LOCK:RUNNING.pop(tid,None)
    error = '' if code==0 else stderr_path.read_text('utf-8')[-3000:]
    summary=stderr_path.read_text('utf-8')
    match=re.search(r'^session=([^\s]+)\s+·\s+status=',summary,re.MULTILINE)
    if match:
        session_id=match.group(1)
    # Remove any configured secret if a dependency includes it in an error.
    if cfg.get('api_key'):
        error = error.replace(cfg['api_key'],'[redacted]')
    with db() as conn:
        conn.execute("UPDATE tasks SET status=CASE WHEN status='cancelled' THEN 'cancelled' ELSE ? END,finished_at=?,result=?,session_id=?,exit_code=?,error=? WHERE id=?",
                     ('completed' if code==0 else 'failed',now(),answer,session_id,code,error,tid))


class Handler(BaseHTTPRequestHandler):
    def log_message(self,*args):
        pass

    def reply(self,code,value):
        raw=json.dumps(value,ensure_ascii=False).encode()
        self.send_response(code);self.send_header('Content-Type','application/json; charset=utf-8')
        self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw)

    def authenticated(self):
        return hmac.compare_digest(self.headers.get('Authorization',''),'Bearer '+TOKEN)

    def tutor_api(self,path):
        headers={key:self.headers[key] for key in ('Cookie','Authorization') if self.headers.get(key)}
        request=Request(TUTOR+path,headers=headers)
        with urlopen(request,timeout=20) as response:
            return json.load(response)

    def browser_admin(self):
        try:
            status=self.tutor_api('/api/auth/status')
        except (URLError,ValueError):
            self.reply(503,{'detail':'DeepTutor 认证接口暂不可用。'})
            return False
        if not status.get('authenticated'):
            self.reply(401,{'detail':'请先登录 DeepTutor。'})
            return False
        if not status.get('is_admin'):
            self.reply(403,{'detail':'Coder 仅向管理员开放。'})
            return False
        return True

    def browser_get(self):
        url=urlparse(self.path)
        if not self.browser_admin():return
        query=parse_qs(url.query)
        if url.path=='/api/coder/health':
            return self.reply(200,self.health_value())
        if url.path=='/api/coder/sessions':
            try:
                data=self.tutor_api('/api/sessions?all_workspaces=true&limit=200')
                sessions=[{'workspace_id':s.get('content_workspace_id',''),
                           'session_id':s.get('session_id') or s.get('id'),
                           'workspace':s.get('content_workspace_name',''),
                           'title':s.get('title') or s.get('session_id'),
                           'capability':s.get('capability') or s.get('agent_type') or 'chat',
                           'updated_at':s.get('updated_at')} for s in data['sessions']]
                return self.reply(200,{'sessions':sessions,'unavailable_workspaces':data.get('unavailable_workspaces',[])})
            except (URLError,ValueError,KeyError):
                return self.reply(502,{'detail':'暂时无法读取会话目录。'})
        if url.path.startswith('/api/coder/projects/'):
            parts=url.path.split('/')
            if len(parts)!=6 or parts[5]!='files' or not re.fullmatch(r'[a-zA-Z0-9_-]{1,60}',parts[4]):
                return self.reply(400,{'detail':'无效项目路径'})
            root=(ROOT/'projects'/parts[4]).resolve()
            relative=query.get('path',[''])[0]
            if relative:
                target=(root/relative).resolve()
                if not target.is_relative_to(root) or any(x.startswith('.') for x in target.relative_to(root).parts) or not target.is_file():
                    return self.reply(404,{'detail':'文件不存在'})
                if target.stat().st_size>20*1024*1024:
                    return self.reply(413,{'detail':'大结果保留服务器，请按项目约定提取小表或预览。'})
                raw=target.read_bytes()
                self.send_response(200);self.send_header('Content-Type','application/octet-stream')
                self.send_header('Content-Disposition',"attachment; filename*=UTF-8''"+quote(target.name))
                self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw)
                return
            files=[]
            if root.exists():
                for p in root.rglob('*'):
                    if p.is_file() and p.resolve().is_relative_to(root) and not any(x.startswith('.') or x in {'__pycache__','node_modules'} for x in p.relative_to(root).parts):
                        files.append({'path':str(p.relative_to(root)),'size':p.stat().st_size})
                    if len(files)>=200:break
            return self.reply(200,{'files':files})
        if url.path=='/api/coder/tasks':
            with db() as conn:
                rows=conn.execute('SELECT * FROM tasks ORDER BY created_at DESC LIMIT 30').fetchall()
            return self.reply(200,{'tasks':[task_view(r) for r in rows]})
        if url.path.startswith('/api/coder/tasks/'):
            tid=url.path.split('/')[-1]
            with db() as conn:row=conn.execute('SELECT * FROM tasks WHERE id=?',(tid,)).fetchone()
            if row:
                try:offset=int(query.get('offset',['0'])[0])
                except ValueError:return self.reply(400,{'detail':'无效事件位置'})
                return self.reply(200,task_view(row,offset))
        self.reply(404,{'detail':'not found'})

    def browser_post(self):
        if self.headers.get('Origin')!=ORIGIN:
            return self.reply(403,{'detail':'请从本站页面提交任务。'})
        if not self.browser_admin():return
        if self.path!='/api/coder/tasks':
            return self.reply(404,{'detail':'not found'})
        try:
            length=int(self.headers.get('Content-Length',0))
            if not 0<length<100000:
                return self.reply(413,{'detail':'请求过大'})
            value=json.loads(self.rfile.read(length))
            selectors=value.get('sources',[])
            if not isinstance(selectors,list) or len(selectors)>20:
                raise ValueError('最多选择20个相关会话')
            snapshots=[]
            for item in selectors:
                wid=str(item.get('workspace_id',''));sid=str(item.get('session_id',''))
                if not re.fullmatch(r'[a-zA-Z0-9_:.-]{1,200}',sid):
                    raise ValueError('无效会话编号')
                data=self.tutor_api('/api/sessions/'+quote(sid,safe='')+'?dt_workspace='+quote(wid,safe=''))
                snapshots.append({'workspace_id':wid,'session_id':sid,'title':data.get('title'),
                                  'capability':data.get('capability') or data.get('agent_type'),
                                  'messages':[{'role':m['role'],'content':m.get('content',''),'created_at':m.get('created_at')}
                                              for m in data.get('messages',[]) if m.get('role') in {'user','assistant'}]})
            value['sources']=snapshots
            return self.reply(202,enqueue(value))
        except HTTPError as exc:
            return self.reply(exc.code,{'detail':'所选会话不存在或当前账户无权读取。'})
        except (ValueError,KeyError,TypeError):
            return self.reply(400,{'detail':'请检查任务、项目名及所选会话。'})
        except URLError:
            return self.reply(503,{'detail':'Tutor 会话接口暂不可用。'})

    def health_value(self):
        return {'ok':True,'engine':'DeepCode','version':'2.3.1','model':CONFIG['model'],'effort':'max','context_window':500000}

    def do_GET(self):
        if self.path.startswith('/api/coder'):
            return self.browser_get()
        if self.path=='/health':
            return self.reply(200,self.health_value())
        if not self.authenticated():
            return self.reply(401,{'error':'unauthorized'})
        from urllib.parse import urlparse,parse_qs
        url=urlparse(self.path)
        with db() as conn:
            if url.path=='/tasks':
                rows=conn.execute('SELECT * FROM tasks ORDER BY created_at DESC LIMIT 30').fetchall()
                return self.reply(200,{'tasks':[task_view(r) for r in rows]})
            if url.path.startswith('/tasks/'):
                row=conn.execute('SELECT * FROM tasks WHERE id=?',(url.path.split('/')[-1],)).fetchone()
                if row:
                    offset=int(parse_qs(url.query).get('offset',['0'])[0])
                    return self.reply(200,task_view(row,offset))
        self.reply(404,{'error':'not found'})

    def do_POST(self):
        if self.path.startswith('/api/coder'):
            return self.browser_post()
        if not self.authenticated():
            return self.reply(401,{'error':'unauthorized'})
        match=re.fullmatch(r'/tasks/([a-f0-9]{24})/cancel',self.path)
        if match:
            return self.reply(200,cancel_task(match.group(1)))
        if self.path!='/tasks':
            return self.reply(404,{'error':'not found'})
        length=int(self.headers.get('Content-Length',0))
        if not 0<length<2000000:
            return self.reply(413,{'error':'request too large'})
        try:
            value=json.loads(self.rfile.read(length))
            result=enqueue(value)
            self.reply(202,result)
        except ValueError as exc:
            self.reply(400,{'error':str(exc)})


if __name__=='__main__':
    CONFIG=configure_provider()
    with db() as conn:
        conn.execute("UPDATE tasks SET status='failed',error='Worker restarted during task',finished_at=? WHERE status='running'",(now(),))
        for row in conn.execute("SELECT id FROM tasks WHERE status='queued' ORDER BY created_at"):
            JOBS.put(row['id'])
    threading.Thread(target=worker,args=(CONFIG,),daemon=True).start()
    ThreadingHTTPServer(('0.0.0.0',8010),Handler).serve_forever()
