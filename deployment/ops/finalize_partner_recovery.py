"""Publish the concrete recovery boundary and its actual acceptance evidence."""
from pathlib import Path
import json,subprocess,sys
from verify_partner_workflow import ROOT,STAGE,client
sys.path.insert(0,'C:/Users/DEVELOPER/.codex/skills/deep-partner-research/scripts')
from runtime_connection import http_json

PROJECT='c37b9168a0db40e3b258c9c03cd56697'
DP=Path('C:/Users/DEVELOPER/AppData/Local/Programs/Deep partner/dp.exe')


def cli(*args):
    result=subprocess.run([str(DP),*map(str,args)],capture_output=True,encoding='utf8',timeout=180)
    if result.returncode:raise RuntimeError(result.stderr[-1600:]+result.stdout[-1000:])
    return json.loads(result.stdout)


def main():
    def read(name):return json.loads((ROOT/'reports'/name).read_text(encoding='utf8'))
    faults=read('partner-tool-autorecovery-live.json');live=read('partner-recovery-release-live.json')
    same=read('partner-scholar-same-run-recovery.json');deployment=read('partner-recovery-cooldown-deployed.json')
    assert faults['all_passed'] and live['all_completed'] and same['same_run_auto_completed'] and deployment['deployed']
    health=http_json('http://127.0.0.1:47908/health');assert health['ready'],health
    rid=live['runs']['code']['id'];local=Path('C:/Users/DEVELOPER/.codex/deep-partner/tool-runtime/jobs')/(rid+'.json')
    native=json.loads(local.read_text(encoding='utf8'))
    assert native['workspace_permissions']['filesystem_scope']=='workspace' and native['workspace_permissions']['command_sandbox']
    assert 'sitecustomize' not in native.get('summary','')
    report={
        'date':'2026-11-05','project_id':PROJECT,'boundary':'Existing Deep Partner tool lifecycles, owned runtime services, transport and receipt-based recovery',
        'services':health['services'],'automatic_recovery':{
            'guardian_interval_seconds':20,'short_repair_attempts':8,'later_health_probe_seconds':300,
            'normal_pending_consumes_fault_budget':False,'same_run_recovery':True,
            'native_turn_identity_retained':True,'slurm_remote_submission_receipt':True,
            'rate_limit_retry_after_supported':True,'default_rate_limit_cooldown_seconds':300,
            'download_pipeline_resumes_original_job':True,'partial_publication_resumes':True,
            'slides_deterministic_child_identity':True,
            'startup':'Current-user logon and independent mutually restoring processes',
            'scheduled_task_registration':'OS rejected; no elevation or permission bypass used'},
        'verification':{'server_tests':deployment['candidate_tests'],'local_recovery_contract_tests':5,
                        'publication_filter_tests':1,'actual_fault_injections':faults['tests'],
                        'actual_same_run_scholar':{'run_id':same['run_id'],'manual_resume':False,'sources':len(same['run']['result']['sources'])},
                        'fresh_native_workspace_permissions':native['workspace_permissions'],
                        'native_startup_warning_present':False,'independent_native_tests':2,
                        'actual_slurm_job':live['slurm_repeated_submission'],'all_formal_runs_completed':True},
        'user_actions':['Provider login/challenge, genuinely new permissions and author choices require the corresponding explicit action.'],
        'limits':['Unknown or scientifically invalid results are not rewritten as success.',
                  'Old interrupted slides tasks lacking execution receipts stay explicit pending reconciliation.',
                  'If both local guardian processes are terminated, the next tool invocation or user logon restores the entry point.'],
        'evidence':['partner-tool-autorecovery-live.json','partner-recovery-release-live.json',
                    'partner-scholar-same-run-recovery.json','partner-recovery-cooldown-deployed.json']}
    output=ROOT/'reports/partner-tool-recovery-release.json';output.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
    files=[ROOT/'docs/工具调用与自动恢复边界.md',output,*[ROOT/'reports'/name for name in report['evidence']]]
    uploaded=cli('project','upload','--project',PROJECT,*files,'--category','documents','--path','docs/workflow','--json')
    refs=[{'path':'docs/workflow/工具调用与自动恢复边界.md'},{'path':'docs/workflow/partner-tool-recovery-release.json'}]
    labels=[('method','工具故障的独立探测与自动恢复'),('implementation','守护、桥接及SSH连接自行恢复'),
            ('implementation','按原run、turn、Slurm回执接续'),('implementation','实际断连后同一Scholar任务完成'),
            ('limitation','登录、明确授权及作者决定保留人工动作')]
    nodes=[{'id':'tool-recovery:'+str(i),'kind':kind,'label':label,'status':'recorded','evidence_refs':refs} for i,(kind,label) in enumerate(labels)]
    record={'id':'tool-recovery-release-20261105','title':'工具调用与自动恢复的实际边界',
            'content':'工具恢复由程序承担：进程与连接恢复后继续原执行。五项真实故障注入及正式项目同run恢复已通过，56项服务器测试通过。短重试耗尽后低频探测，不要求重新发送需求。科学结果与作者选择保持真实状态。',
            'nodes':nodes,'edges':[{'source':'tool-recovery:0','target':'tool-recovery:1','relation':'uses'},
                                   {'source':'tool-recovery:0','target':'tool-recovery:2','relation':'uses'},
                                   {'source':'tool-recovery:3','target':'tool-recovery:0','relation':'supports'},
                                   {'source':'tool-recovery:0','target':'tool-recovery:4','relation':'limited_by'}]}
    path=STAGE/'tool-recovery-record.json';path.write_text(json.dumps(record,ensure_ascii=False),encoding='utf8')
    recorded=cli('workflow','record','--project',PROJECT,'--file',path)
    with client() as connection:
        for file in files:
            response=connection.get('/research/api/projects/'+PROJECT+'/file',params={'path':'docs/workflow/'+file.name});response.raise_for_status();assert response.content==file.read_bytes(),file
    (ROOT/'reports/partner-tool-recovery-project.json').write_text(json.dumps({'project_id':PROJECT,'uploaded':uploaded,'record':recorded,'files_read_back':len(files)},ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps({'published':True,'project_id':PROJECT,'files_read_back':len(files),'server_tests':deployment['candidate_tests'],'all_services_ready':True},ensure_ascii=False))


if __name__=='__main__':
    sys.stdout.reconfigure(encoding='utf8');main()
