"""Real author-dialogue and whole-manuscript candidates, without replacing originals."""
from pathlib import Path
import argparse,json,os,sys
import httpx
from workspace_interactions_fixture import login,ORIGIN

ROOT=Path(__file__).resolve().parents[1]
CACHE=ROOT/'.local/writing-real'
STATE=CACHE/'agentic-tests.json'


def main():
    sys.stdout.reconfigure(encoding='utf8');os.environ.setdefault('WORKBENCH_PROXY_JUMP','research-cluster-xh5')
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['start-intro','start-full','status']);args=parser.parse_args()
    state=json.loads(STATE.read_text(encoding='utf8')) if STATE.exists() else {}
    with httpx.Client(base_url=ORIGIN,headers={'Origin':ORIGIN},proxy='http://127.0.0.1:12000',timeout=150,trust_env=False) as c:
        login(c)
        if args.action=='status':
            report={}
            for name,item in state.items():
                r=c.get('/research/api/projects/'+item['project_id']+'/writing/runs/'+item['id']);r.raise_for_status();run=r.json();report[name]=run
                print(json.dumps({'test':name,'id':run['id'],'status':run['status'],'stage':run['stage'],
                    'plan':run.get('stage_plan'),'completed':[s['stage'] for s in run.get('stage_history',[])],
                    'dify_routes':len(run.get('dify_runs',[])),'error':run.get('error'),'agentic_calls':run.get('agentic_calls'),
                    'output':{k:v for k,v in (run.get('outputs') or {}).items() if k!='text'}},ensure_ascii=False))
            (ROOT/'reports/writing-real-agentic-tests.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
            return
        intro=args.action=='start-intro';name='chloride-sulfate-introduction' if intro else 'moisture-full-manuscript'
        pid='1ea03384007d4bb9b88d43e3368099f3' if intro else '638495c5ba024a93a305ff69b4658811'
        prefix='/research/api/projects/'+pid
        r=c.get('/research/api/journals/search',params={'q':'Cement and Concrete Research'});r.raise_for_status()
        journal=next(x for x in r.json()['items'] if x['name']=='Cement and Concrete Research')
        paths=['literature/reading/Meng2024_combined.pdf','literature/reading/Yu2021_competitive_antagonism.pdf'] if intro else []
        c.put(prefix+'/writing/settings',json={'journal':journal,'phase':'auto','exemplar_paths':paths}).raise_for_status()
        if intro:
            conversation=json.loads((CACHE/'chloride-sulfate-author-dialogue.json').read_text(encoding='utf8'))
            request='''这是作者授权的真实写作工作流验收。请读取附带的氯硫耦合会话中作者的连续对话，以最后一版五段引言为基线，按1111文档Agent 0至4的职责优化中文引言，交给作者验收。
重点理解作者最新反馈：贯穿宏观概念，主次清楚、前后连贯；按一类研究形成结论和局限，不逐篇罗列；主语和术语明确，物理参数具体；研究主题围绕氯硫耦合下化学、孔隙、损伤与传输反馈，并说明B-PINN的科学作用。目标期刊CCR已明确。
标杆论文主要用于学习专业搭配、句式、信息次序和段落表达；研究主题根据CCR实际范围与已发表研究定位。请实际利用MCP的双轨RAG、全文读取、skill与联网检索。至少读一份适用skill，并核对官方期刊范围；需要新资源时使用模型联网和下载工具，遇到单渠道失败继续其他可用来源。优先复用已读原文。
保留五段和原50篇参考文献的对应关系，在现有主线和段落上多次小改。只生成中文引言候选稿，不写不存在的实验结果、不生成整篇新论文。研究目的、科学贡献和结构性调整如果还有备选，放在修改说明供作者决定。本次没有要求作者再次确认是否启动工作流。
执行计划采用intent、exemplar、alignment、wide、review、deliver；narrow不另起方法章节。最后交付完整五段中文正文。'''
            request+='\n作者最新澄清：分轮由作者的验收与新意见驱动，本次只做一轮。先按评分规则检查最不合适的地方并区分必要修改、潜在优化和作者判断；只实施本轮选定的必要局部修订，评分复评后交作者验收，不自动第二轮。'
            body={'request':request,'operation_id':'real-author-intro-scored-round1-v2','engine':'agentic','proposal':True,'author_round':True,'revision_mode':'incremental',
                'history':conversation,'baseline_text':(CACHE/'chloride-sulfate-latest-output.md').read_text(encoding='utf8'),
                'session_id':'unified_1793679399973_9a3ea267'}
        else:
            request='''这是作者授权的水分扩散论文全文写作工作流验收。原稿为Mois-Net。按1111文档Agent 0至4进行，但全文的原则是多次小改和润色，保留作者现有题目、方法、结果、结构、公式、图表、引文、数字和参考文献，不能上来推翻。
第一轮在现有段落中修正主语、指代、句法、术语、重复及未完成占位语；第二轮基于第一轮改善衔接和节奏。逐节修改，每轮保留差异与理由供作者验收。材料未支持的改动记为作者问题，保持正文事实。标杆用于学习表达，期刊范围用于研究定位，二者分别处理。
实际调用MCP的RAG、原文和skill工具。允许模型联网寻找并下载适当资源；不要因为一个来源失败停止。已有科学结果不用重算，保持所有数值。编辑计划采用全部角色，narrow与wide只提出原文节点的小范围编辑，review进行第二轮小改。正式编辑器原稿不替换，输出候选完整Word与对照。'''
            request=request.replace('第一轮在现有段落中修正主语、指代、句法、术语、重复及未完成占位语；第二轮基于第一轮改善衔接和节奏。逐节修改，每轮保留差异与理由供作者验收。','本次只进行一轮：先按明确规则评分，找出最不合适的地方与潜在优化，区分必要修改、潜在优化、作者判断；只实施本轮选定的必要局部修订，完成后复评并交作者验收，收到作者的新意见后才能下一轮。')
            request=request.replace('review进行第二轮小改','review只复评本轮候选，不再次重写')
            body={'request':request,'operation_id':'real-moisture-scored-round1-v2','engine':'agentic','proposal':True,'revision_mode':'incremental','author_round':True}
        body['model_selection']={'profile_id':'llm-profile-agent-setup','model_id':'llm-model-gpt61sol-max-study'}
        body['resume']=True
        if name in state:body['reuse_run_id']=state[name]['id']
        r=c.post(prefix+'/writing/start',json=body)
        if not r.is_success:raise RuntimeError(str(r.status_code)+' '+r.text)
        run=r.json();state[name]={'id':run['id'],'project_id':pid}
        STATE.write_text(json.dumps(state,ensure_ascii=False,indent=2),encoding='utf8')
        print(json.dumps({'test':name,'id':run['id'],'status':run['status'],'stage':run['stage'],'engine':run.get('engine')},ensure_ascii=False))


if __name__=='__main__':main()
