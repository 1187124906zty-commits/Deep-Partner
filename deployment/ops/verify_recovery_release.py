"""Exercise the published scheduler, fresh native scope and Slurm receipt reuse."""
from pathlib import Path
import json,subprocess,sys,time
from verify_partner_workflow import ROOT,STAGE,client

DP=Path('C:/Users/DEVELOPER/AppData/Local/Programs/Deep partner/dp.exe')
PROJECT='64c6b5e79b824bc4bf23637e8204446c'


def cli(*args,timeout=150):
    result=subprocess.run([str(DP),*map(str,args)],capture_output=True,encoding='utf8',timeout=timeout)
    if result.returncode:raise RuntimeError(result.stderr[-1600:]+result.stdout[-1000:])
    return result.stdout


def main():
    report_path=ROOT/'reports/partner-recovery-release-live.json'
    session=cli('chat','send','--project',PROJECT,'--message','软件恢复工作流验收会话。仅回复 RECOVERY_SESSION_READY，不调用工具，不修改文件。','--jsonl')
    events=[json.loads(row) for row in session.splitlines() if row.startswith('{')]
    sid=next(row['session_id'] for row in events if row.get('session_id'))
    report={'project_id':PROJECT,'session_id':sid,'runs':{},'all_completed':False}
    payload={'kind':'code','code_engine':'agent','session_id':sid,'input_paths':[],
             'query':'新的项目会话自动继承明确授权并完成原生执行与保存',
             'instruction':'软件验收。只创建recovery_check.py和test_recovery_check.py。前者定义add(a,b)=a+b，后者用标准库unittest验证add(2,3)=5及add(-2,2)=0。使用C:/Users/DEVELOPER/DeepTutor/.venv/Scripts/python.exe -m unittest -v实际运行，报告真实结果。仅这两个文件，不安装依赖，不调用其他智能体。',
             'publish_root':'src/recovery-workflow-check','request_id':'recovery-fresh-native-20261105'}
    native=STAGE/'recovery-fresh-native.json';native.write_text(json.dumps(payload,ensure_ascii=False),encoding='utf8')
    report['runs']['code']=json.loads(cli('workflow','run','--project',PROJECT,'--file',native))
    simulation=json.loads((STAGE/'simulation-request.json').read_text(encoding='utf8'))
    simulation['request_id']='recovery-slurm-submit-once-20261105'
    simulation['query']='集群提交回执与恢复调度验收：Poisson制造解'
    sim_path=STAGE/'recovery-simulation.json';sim_path.write_text(json.dumps(simulation,ensure_ascii=False),encoding='utf8')
    report['runs']['simulate']=json.loads(cli('workflow','run','--project',PROJECT,'--file',sim_path))
    search={'kind':'search','query':'phase field reactive transport dissolution','limit':2,
            'request_id':'recovery-scholar-native-20261105','allow_search_fallback':False}
    path=STAGE/'recovery-search.json';path.write_text(json.dumps(search),encoding='utf8')
    report['runs']['search']=json.loads(cli('workflow','run','--project',PROJECT,'--file',path))
    report_path.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
    with client() as connection:
        end=time.monotonic()+480
        while True:
            for kind,row in list(report['runs'].items()):
                if row['status']=='completed':continue
                response=connection.get('/research/api/projects/'+PROJECT+'/research-flow/runs/'+row['id']);response.raise_for_status();value=response.json()
                assert value['status'] not in ('failed','cancelled','waiting_input'),{k:value.get(k) for k in ('id','status','stage','error')}
                report['runs'][kind]=value
            report_path.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
            if all(row['status']=='completed' for row in report['runs'].values()):break
            if time.monotonic()>end:raise TimeoutError('Existing published runs remain queued/running; preserve their IDs')
            time.sleep(3)
        code=report['runs']['code']['result']['code_result']
        assert code['native_tool'] and len(code['files'])==2
        output=STAGE/'recovery-source-readback';output.mkdir(exist_ok=True)
        for file in code['files']:
            response=connection.get('/research/api/projects/'+PROJECT+'/file',params={'path':file['path']});response.raise_for_status()
            assert len(response.content)==file['bytes'] and file['read_back']
            (output/Path(file['path']).name).write_bytes(response.content)
        check=subprocess.run([sys.executable,'-m','unittest','-v'],cwd=output,capture_output=True,encoding='utf8',timeout=30)
        assert check.returncode==0,check.stderr
        report['independent_code_tests']={'exit_code':check.returncode,'output':check.stderr}
    sys.path.insert(0,'C:/Users/DEVELOPER/.codex/skills/deep-partner-research/scripts')
    from cluster_pdf_runtime import submit_once
    simulation=report['runs']['simulate']['result']['simulation_result']
    original=simulation['job_id'];reused=submit_once(simulation['remote_root']+'/simulation.sbatch')
    assert original==reused,'Submission receipt must return the original job id'
    report['slurm_repeated_submission']={'original_job':original,'returned_job':reused,'same_job':True}
    report['all_completed']=True
    report_path.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps({'all_completed':True,'runs':{k:{'id':r['id'],'status':r['status']} for k,r in report['runs'].items()},'same_slurm_job':original},ensure_ascii=False))


if __name__=='__main__':
    sys.stdout.reconfigure(encoding='utf8');main()
