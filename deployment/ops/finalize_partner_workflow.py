"""Publish the bounded release evidence into the actual integration project."""
from pathlib import Path
import json,subprocess,sys

ROOT=Path(__file__).resolve().parents[1]
PROJECT='c37b9168a0db40e3b258c9c03cd56697'
DP=Path('C:/Users/DEVELOPER/AppData/Local/Programs/Deep partner/dp.exe')

def read(name):return json.loads((ROOT/'reports'/name).read_text(encoding='utf8'))
def main():
    live=read('partner-workflow-live.json');canvas=read('partner-canvas-live.json')
    code=read('partner-code-direct-live.json');recovery=read('partner-code-recovery-live.json')
    analysis=read('partner-analysis-live.json');slides=read('partner-slides-live.json')
    native=read('partner-native-installed.json')
    assert all(live['checks'].values()) and all(canvas['checks'].values())
    assert code['status']=='completed' and recovery['status']=='completed' and analysis['status']=='completed'
    assert native['installed'] and native['tests_passed']
    report={
        'released':'2026-11-05','project_id':PROJECT,
        'project_url':'https://tutor.example.invalid/research/?project='+PROJECT,
        'entry':{'user_instructions':'C:/Users/DEVELOPER/.codex/AGENTS.md',
                 'skill':'C:/Users/DEVELOPER/.codex/skills/deep-partner-research/SKILL.md',
                 'mcp':'deep-partner','previous_orchestrator_enabled':False,'cli':str(DP),
                 'mcp_visibility':'Existing Codex sessions refresh their tool catalog or use dp immediately.'},
        'routing':{'search':'Google Scholar MCP, then Crossref on actual failure',
                   'download':'paired ScanSci, PDF identity, project literature receipt',
                   'survey':'search, download, bounded excerpts, source-linked synthesis, archive',
                   'analyze':'selected project PDFs, bounded excerpts, source-linked synthesis',
                   'code':'direct DeepCode task, execute, explicit artifacts, save and read back',
                   'slides':'Paper2Slides planning; optional export uses existing review and author decisions'},
        'verification':{'backend_targeted_tests':8,'frontend_workbench_tests':40,'frontend_unified_tests':47,
                        'project_and_cli_checks':live['checks'],'canvas_checks':canvas['checks'],
                        'actual_mcp':read('partner-mcp-live.json'),
                        'analysis_status':analysis['status'],'analysis_report':'partner-analysis-live.json',
                        'new_direct_code_status':code['status'],'recovered_code_status':recovery['status'],
                        'slides_planning_status':slides['status'],'slides_full_export_verified':False,
                        'native':native},
        'reading_policy':{'default_max_sources':3,'max_characters_per_pdf':14000,
                          'coverage':'Actual page numbers are retained; bounded excerpts are not full-paper review.'},
        'memo':{'id':'13b41246-dd41-4cf6-9bec-62cf22c5b378','project_id':PROJECT,
                'automatic_incremental_sync_verified':True,'project_directory':'docs/idea-memo'},
        'limits':['Scientific conclusions remain source-bound synthesis, not exhaustive novelty certification.',
                  'Paper2Slides content planning was run; full PPT export did not pass review on acceptance content.'],
        'evidence_files':['partner-workflow-live.json','partner-analysis-live.json','partner-code-direct-live.json',
                          'partner-code-recovery-live.json','partner-slides-live.json','partner-canvas-live.json',
                          'partner-mcp-live.json','partner-native-installed.json']}
    output=ROOT/'reports/partner-workflow-release.json';output.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
    files=[ROOT/'docs/DeepPartner自动研究工作流.md',output]
    p=subprocess.run([str(DP),'project','upload','--project',PROJECT,*map(str,files),'--category','documents','--path','docs/workflow','--json'],capture_output=True,text=True,encoding='utf8',timeout=120)
    if p.returncode:raise RuntimeError(p.stderr[-1800:]+p.stdout[-1000:])
    receipt=json.loads(p.stdout)
    evidence=[{'path':'docs/workflow/DeepPartner自动研究工作流.md'},{'path':'docs/workflow/partner-workflow-release.json'}]
    labels=[('question','研究材料、判断与对话如何连续保存在所属项目？'),
            ('method','按结构化任务自动调用工具'),('method','Scholar 检索与 ScanSci 文献入库'),
            ('method','带页码的分批阅读与研究综合'),('implementation','DeepCode 执行、保存与文件回读'),
            ('implementation','项目会话流式连接与断线恢复'),('method','Paper2Slides 内容规划与导出阶段'),
            ('decision','保存公开判断、理由、证据与反证'),('limitation','有限检索不能断言世界上无人研究')]
    nodes=[{'id':'workflow:'+str(i),'kind':kind,'label':label,'status':'recorded',
            'detail':'实现及验收范围见本项目 docs/workflow/ 中的使用说明与实际回执。','evidence_refs':evidence} for i,(kind,label) in enumerate(labels)]
    edges=[{'source':'workflow:0','target':'workflow:1','relation':'motivates'}]
    edges += [{'source':'workflow:1','target':'workflow:'+str(i),'relation':'uses'} for i in range(2,8)]
    edges += [{'source':'workflow:3','target':'workflow:8','relation':'limited_by'},
              {'source':'workflow:7','target':'memo:13b41246-dd41-4cf6-9bec-62cf22c5b378','relation':'records'}]
    record={'id':'workflow-release-20261105','title':'Deep Partner 自动研究工作流 · 实际交付',
            'content':'工具路由负责检索、下载、执行、保存和图谱更新。研究者与作者作科学判断。项目会话与 idea memo 保持明确归属。完整说明与验收见 docs/workflow/。',
            'nodes':nodes,'edges':edges}
    path=ROOT/'.local/partner-workflow/release-record.json';path.write_text(json.dumps(record,ensure_ascii=False),encoding='utf8')
    result=subprocess.run([str(DP),'workflow','record','--project',PROJECT,'--file',str(path)],capture_output=True,text=True,encoding='utf8',timeout=90)
    if result.returncode:raise RuntimeError(result.stderr[-1800:]+result.stdout[-1000:])
    sys.path.insert(0,str(ROOT/'ops'));from verify_partner_workflow import client
    with client() as c:
        for file in files:
            response=c.get('/research/api/projects/'+PROJECT+'/file',params={'path':'docs/workflow/'+file.name})
            response.raise_for_status();assert response.content==file.read_bytes(),file
        graph=c.get('/research/api/projects/'+PROJECT+'/research-flow/graph');graph.raise_for_status()
        assert any(n['id']=='workflow:1' for n in graph.json()['nodes'])
    delivered={'project_id':PROJECT,'files':receipt,'record':json.loads(result.stdout),'actual_readback':True}
    (ROOT/'reports/partner-release-project.json').write_text(json.dumps(delivered,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps({'published':True,'project_id':PROJECT,'actual_readback':True},ensure_ascii=False))

if __name__=='__main__':sys.stdout.reconfigure(encoding='utf8');main()
