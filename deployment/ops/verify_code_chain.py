"""Run a bounded real Tutor/DeepCode integration check; never print credentials.

Run locally with ``python ops/verify_code_chain.py``. SSH uses papers-research;
the existing private Tutor login remains inside the deeptutor container.
Use ``--resume-report`` to repeat only contract/readback checks for the saved
task; it never submits replacement computation.
"""
from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time


ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "reports/code-chain-live.json"
WORKSPACE = "ws_f5cecfd629bd4985be1624aefa509c5c"

TUTOR_PROGRAM = r'''
import asyncio,json,time
from pathlib import Path
from urllib.parse import quote
import httpx,websockets

async def main():
 origin='https://tutor.example.invalid';workspace='ws_f5cecfd629bd4985be1624aefa509c5c'
 async with httpx.AsyncClient(timeout=90,trust_env=False) as client:
  account=json.loads(Path('/migration/admin-login.json').read_text())
  response=await client.post('http://127.0.0.1:8001/api/auth/login',json=account);response.raise_for_status()
  token=response.cookies.get('dt_token')
  prompt=('这是独立Dify部署的软件集成验收。请本轮实际调用coder_run(action=code)，project留空，执行下述已授权小型任务。'
   '不要只给建议；不要提交Slurm，不改任何API设置、不读或改正式项目、不用外部依赖。'
   '请在当前专用Code项目写src/diffusion_conservation.py，并实际运行生成results/diffusion.json和verification.json。'
   '标准库Python一维有限体积显式扩散：域长L=1，nx=32个单元，dx=1/nx，单元中心x=(i+0.5)*dx，'
   'D=1，dt=0.2*dx**2，steps=100，初场c=1+0.5*cos(2*pi*x)。两端外侧通量为0，'
   '边界更新分别c0+=r*(c1-c0)，cN+=r*(cNm1-cN)，内部标准二阶差分，r=D*dt/dx**2。'
   '另以同样网格/步长/100步测试常量3.25场不变。脚本必须有断言检查r<=0.5、质量绝对误差<1e-12、'
   '非负、最大最小值不越初值界、常量场最大变化<1e-12。提供--output参数（默认results/diffusion.json），'
   '使脚本能在干净临时目录重跑。输出JSON请严格使用键：nx,D,dx,dt,steps,r,initial,final,'
   'mass_initial,mass_final,mass_error_abs,minimum,maximum,constant_error_max；initial/final为32元数组。'
   '这只是软件集成与数值不变量验证，不写论文、不宣布物理模型已科学验收。完成后报告实际运行命令和文件。'
   '所有普通算例参数已明确；如仍有必须由用户决定的关键科学问题，请原样提问并等待，不能代答。')
  payload={'type':'start_turn','protocol_version':'2.0','capability':'code','language':'zh','tools':[],
           'workspace_id':workspace,'content':prompt}
  info={'workspace_id':workspace,'task_ids':[],'event_count':0,'tool_calls':[],'session_id':'','turn_id':''}
  started=time.monotonic()
  async with asyncio.timeout(660):
   async with websockets.connect('ws://127.0.0.1:8001/ws?dt_workspace='+quote(workspace),
    additional_headers={'Cookie':'dt_token='+token,'Origin':origin},max_size=20000000) as socket:
    await socket.send(json.dumps(payload,ensure_ascii=False))
    async for raw in socket:
     event=json.loads(raw);kind=event.get('type');meta=event.get('metadata') or {};info['event_count']+=1
     info['session_id']=event.get('session_id') or info['session_id'];info['turn_id']=event.get('turn_id') or info['turn_id']
     task=meta.get('coder_task_id')
     if task and task not in info['task_ids']:
      info['task_ids'].append(task);print(json.dumps({'progress':'task_started','task_id':task,'session_id':info['session_id'],'turn_id':info['turn_id']}),flush=True)
     if kind=='tool_call':info['tool_calls'].append(meta.get('tool_name'))
     if kind=='tool_result' and meta.get('tool_name')=='coder_run':
      try:
       value=json.loads(event.get('content') or '{}');task=value.get('id')
       if task and task not in info['task_ids']:info['task_ids'].append(task)
      except ValueError:pass
     if kind=='wait_for_input':
      info.update(status='waiting_input',question={'content':event.get('content'),'metadata':meta})
      print(json.dumps({'result':'tutor','data':info},ensure_ascii=False),flush=True);return
     if kind in {'error','protocol_error'}:info.setdefault('errors',[]).append({'type':kind,'message':event.get('content')})
     if kind=='result':info['response']=meta.get('response') or event.get('content') or ''
     if kind=='done':
      info['status']=meta.get('status');break
  info['elapsed_seconds']=round(time.monotonic()-started,3)
  print(json.dumps({'result':'tutor','data':info},ensure_ascii=False),flush=True)
asyncio.run(main())
'''

WORKER_PROGRAM = r'''
import json,os,pathlib,sqlite3,urllib.request,urllib.error,urllib.parse
task_id=TASK_ID
root=pathlib.Path(os.getenv('CODER_STATE','/home/coder/.deeptutor-bridge'))
db=sqlite3.connect(root/'tasks.sqlite3');db.row_factory=sqlite3.Row
row=db.execute('SELECT * FROM tasks WHERE id=?',(task_id,)).fetchone()
assert row is not None,'Native task not found'
payload=json.loads(row['request_json'])
token=pathlib.Path(os.getenv('CODER_TOKEN_FILE',os.getenv('CODER_TOKEN_PATH','/run/secrets/coder-token'))).read_text().strip()
headers={'Authorization':'Bearer '+token,'Content-Type':'application/json'}
def request(path,body=None):
 req=urllib.request.Request('http://127.0.0.1:8010'+path,headers=headers,data=None if body is None else json.dumps(body).encode())
 try:
  with urllib.request.urlopen(req,timeout=25) as response:return response.status,json.load(response)
 except urllib.error.HTTPError as error:
  return error.code,json.load(error)
first_status,first=request('/tasks',payload)
second_status,second=request('/tasks',payload)
changed=json.loads(json.dumps(payload));changed['task']+='\nChanged payload for a deliberate conflict probe; must not execute.'
conflict_status,conflict=request('/tasks',changed)
assert first_status==second_status==202 and first['id']==second['id']==task_id
assert first.get('deduplicated') is True and second.get('deduplicated') is True
assert conflict_status==409
cursor=0;events=[];cursors=[]
while True:
 status,value=request('/tasks/'+task_id+'?offset='+str(cursor));assert status==200
 next_cursor=value['next_offset'];batch=value['events'];events.extend(batch)
 cursors.append({'offset':cursor,'next_offset':next_cursor,'count':len(batch),'event_count':value['event_count'],'has_more':value['has_more']})
 assert next_cursor-cursor==len(batch)
 if not value['has_more']:break
 assert next_cursor>cursor;cursor=next_cursor
assert len(events)==value['event_count']==next_cursor
persisted=[json.loads(item['body']) for item in db.execute('SELECT body FROM task_events WHERE task_id=? ORDER BY seq',(task_id,))]
assert events==persisted,'HTTP cursor replay differs from persisted native event sequence'
cut=max(0,next_cursor//2)
_,tail=request('/tasks/'+task_id+'?offset='+str(cut))
assert tail['events']==events[cut:cut+100]
_,empty=request('/tasks/'+task_id+'?offset='+str(next_cursor));assert empty['events']==[]
query={key:payload['identity'][key] for key in ('owner_id','workspace_id','session_id','turn_id')}
query['ancestor_turn_ids']=json.dumps(payload['identity'].get('ancestor_turn_ids',[]));query['explicit_project']='true'
route='/projects/'+urllib.parse.quote(value['project'],safe='')+'/files?'
_,listing=request(route+urllib.parse.urlencode(query))
artifacts={}
for path in ['src/diffusion_conservation.py','results/diffusion.json','verification.json']:
 q={**query,'path':path,'start_line':1,'line_count':1000}
 status,artifact=request(route+urllib.parse.urlencode(q));assert status==200,(path,status)
 artifacts[path]=artifact
summary={key:value.get(key) for key in ['id','project','logical_project','mode','status','exit_code','owner_id','workspace_id','tutor_session_id','tutor_turn_id','native_turn_id','session_id','branch_mode','verification','execution','cluster_jobs']}
print(json.dumps({'result':'worker','data':{'task':summary,'deduplication':{'http_statuses':[first_status,second_status],'same_task':True,'deduplicated':True,'command_id':payload['identity']['command_id']},'conflict':{'http_status':conflict_status,'error':conflict.get('error')},'events':{'count':len(events),'cursor_pages':cursors,'resume_cut':cut,'tail_matches':True,'matches_persisted_sequence':True,'terminal_cursor_empty':True,'kinds':sorted({str((event.get('msg') or event).get('type')) for event in events})},'files':listing,'artifacts':artifacts}},ensure_ascii=False))
'''


def remote(container, source, on_message=None):
    command = ["ssh", "papers-research", "docker", "exec", "-i", container, "python", "-"]
    process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE, text=True, encoding="utf-8")
    process.stdin.write(source)
    process.stdin.close()
    result = None
    for line in process.stdout:
        try:
            value = json.loads(line)
        except ValueError:
            continue
        if value.get("progress"):
            print(json.dumps(value, ensure_ascii=False), flush=True)
            if on_message:
                on_message(value)
        if value.get("result"):
            result = value["data"]
    error = process.stderr.read()
    code = process.wait()
    if code or result is None:
        # No request headers, account material or raw remote logs are printed.
        raise RuntimeError(f"Remote {container} check failed (exit {code}; stderr {len(error)} chars)")
    return result


def artifact_text(value):
    if isinstance(value, str):
        return value
    for key in ("content", "text"):
        if isinstance(value.get(key), str):
            assert not value.get("truncated"), "Artifact API read was truncated"
            # Native code_files is a line-addressed text view, not raw bytes.
            return "\n".join(re.sub(r"^\d+: ", "", line) for line in value[key].splitlines())
    raise ValueError("Unrecognized artifact response fields: " + ",".join(value))


def independent_check(artifacts):
    source = artifact_text(artifacts["src/diffusion_conservation.py"])
    reported = json.loads(artifact_text(artifacts["results/diffusion.json"]))
    with tempfile.TemporaryDirectory(prefix="code-chain-independent-") as directory:
        temporary = Path(directory)
        script = temporary / "diffusion_conservation.py"
        output = temporary / "rerun.json"
        script.write_text(source, encoding="utf-8")
        ran = subprocess.run([sys.executable, "-I", "-X", "utf8", str(script), "--output", str(output)],
                             cwd=temporary, capture_output=True, text=True,
                             encoding="utf-8", timeout=25)
        assert ran.returncode == 0, "Independent artifact rerun failed"
        rerun = json.loads(output.read_text(encoding="utf-8"))
    nx, diffusivity, steps = 32, 1.0, 100
    dx = 1.0 / nx
    dt = 0.2 * dx * dx
    initial = [1.0 + 0.5 * math.cos(2.0 * math.pi * (i + 0.5) * dx) for i in range(nx)]
    def evolve(values):
        for _ in range(steps):
            flux = [0.0] + [-diffusivity * (values[i] - values[i-1]) / dx for i in range(1, nx)] + [0.0]
            values = [values[i] - dt / dx * (flux[i+1] - flux[i]) for i in range(nx)]
        return values
    expected = evolve(initial.copy())
    constant = evolve([3.25] * nx)
    errors = {}
    for name, value in (("recorded", reported), ("rerun", rerun)):
        assert value["nx"] == nx and value["D"] == diffusivity and value["steps"] == steps
        assert len(value["initial"]) == len(value["final"]) == nx
        assert abs(value["dx"]-dx) < 1e-15 and abs(value["dt"]-dt) < 1e-15
        assert abs(value["r"]-0.2) < 1e-15
        field_error = max(abs(a-b) for a,b in zip(value["final"], expected))
        initial_error = max(abs(a-b) for a,b in zip(value["initial"], initial))
        mass0 = sum(initial) * dx
        mass1 = sum(value["final"]) * dx
        assert field_error < 1e-12 and initial_error < 1e-12
        assert abs(value["mass_initial"]-mass0) < 1e-12 and abs(value["mass_final"]-mass1) < 1e-12
        assert abs(value["mass_error_abs"]-abs(mass1-mass0)) < 1e-12
        assert abs(value["minimum"]-min(value["final"])) < 1e-12
        assert abs(value["maximum"]-max(value["final"])) < 1e-12
        assert value["constant_error_max"] < 1e-12
        assert min(value["final"]) >= min(initial)-1e-12 and max(value["final"]) <= max(initial)+1e-12
        errors[name] = {"field_max_abs_error":field_error,"initial_max_abs_error":initial_error,
                        "mass_error_abs":abs(mass1-mass0),"minimum":min(value["final"]),
                        "maximum":max(value["final"])}
    assert max(abs(x-3.25) for x in constant) == 0
    assert "assert" in source, "Artifact must contain the requested assertions"
    return {"passed":True,"artifact_rerun_exit_code":ran.returncode,
            "independent_python_version":sys.version.split()[0],"absolute_tolerance":1e-12,
            "independent_reference":"separate conservative face-flux implementation",
            "errors":errors,"r":diffusivity*dt/dx**2,
            "constant_error_max":max(abs(x-3.25) for x in constant),
            "scope":"software integration and declared numerical invariants; no independent experimental validation"}


def save(report):
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")


def main():
    started = time.monotonic()
    resume = "--resume-report" in sys.argv
    report = (json.loads(REPORT.read_text(encoding="utf-8")) if resume else
              {"verified":False,"workspace_id":WORKSPACE,"scope":"bounded Code integration validation",
               "no_slurm_requested":True,"started_at":time.strftime("%Y-%m-%dT%H:%M:%SZ",time.gmtime())})
    save(report)
    def progress(value):
        report.update(value)
        save(report)
    try:
        tutor = report["tutor"] if resume else remote("deeptutor", TUTOR_PROGRAM, progress)
        report["tutor"] = tutor
        save(report)
        if tutor.get("status") == "waiting_input":
            report["status"] = "requires_user_input"
            return
        assert tutor.get("status") == "completed" and not tutor.get("errors"), "Tutor turn did not complete successfully"
        assert "coder_run" in tutor.get("tool_calls", []), "Real Tutor coder_run invocation was not observed"
        assert tutor.get("task_ids"), "Tutor did not produce a real Code task"
        worker = remote("deeptutor-coder", "TASK_ID=" + repr(tutor["task_ids"][-1]) + "\n" + WORKER_PROGRAM)
        report["worker"] = worker
        save(report)
        assert worker["task"]["status"] == "completed" and worker["task"]["exit_code"] == 0
        assert not worker["task"].get("cluster_jobs"), "Unexpected registered Slurm jobs"
        report["independent_validation"] = independent_check(worker["artifacts"])
        report.update(verified=True,status="passed")
        report.pop("error", None)
        report.pop("progress", None)
    except Exception as error:
        report.update(status="failed",error=type(error).__name__ + ": " + str(error))
        raise
    finally:
        report["validation_stage_elapsed_seconds"] = round(time.monotonic()-started,3)
        report["elapsed_seconds"] = round(time.time()-datetime.fromisoformat(report["started_at"].replace("Z", "+00:00")).timestamp(),3)
        report["finished_at"] = datetime.now(timezone.utc).isoformat()
        save(report)
        print(json.dumps({"report":str(REPORT),"verified":report["verified"],"status":report.get("status"),
                          "task_ids":report.get("tutor",{}).get("task_ids",[])},ensure_ascii=False),flush=True)


if __name__ == "__main__":
    main()
