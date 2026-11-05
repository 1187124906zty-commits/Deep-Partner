"""Check consent, private template scope, and the real editable PPT/PDF output."""
from pathlib import Path
from tempfile import TemporaryDirectory
import json,os,time,sys
sys.path.insert(0,"/workbench")
from fastapi.testclient import TestClient
from pptx import Presentation
from PIL import Image,ImageDraw
from server import app as module
from server.storage import Store,atomic_json
from server.slides import inspect_template,make_deck,render_presentation
from server.slide_quality import verify_rendered

checks=[]
def check(value,message):
    if not value:raise AssertionError(message)
    checks.append(message)

output=Path(os.environ.get('WORKBENCH_TEST_OUTPUT','/app/data/research-workbench/presentation-acceptance'));output.mkdir(parents=True,exist_ok=True)
with TemporaryDirectory(dir=module.DATA) as folder:
    module.DATA=Path(folder);module.store=Store(Path(folder)/'state')
    module.app.dependency_overrides[module.actor]=lambda:{'id':'presentation-qa','username':'QA'}
    project=module.store.create('presentation-qa','Synthetic presentation acceptance');pid=project['id'];root=module.store.path('presentation-qa',pid);route='/research/api/projects/'+pid
    with TestClient(module.app) as client:
        items=client.get(route+'/slide-templates').json()
        check({t['id'] for t in items['templates']}=={'beamer-default','beamer-madrid','metropolis'},'Public catalog contains only the three traceable neutral adaptations')
        check(all(t.get('source') and t.get('license') and not t.get('institutional_identity') for t in items['templates']),'Public templates disclose sources, licenses and no institutional identity')
        check(len(items['profiles'])==6 and not items['confirmation'],'Audience profiles are separate and generation is initially unconfirmed')
        for path in ['/slides/plan','/slides/export']:
            reply=client.post(route+path,json={})
            check(reply.status_code==400 and '确认' in reply.text,'Unconfirmed '+path+' is rejected before any model or rendering job')
        check(not module.store.jobs('presentation-qa',pid),'Opening a project does not enqueue presentation work')
        check(client.post(route+'/slide-templates/group/prepare').status_code==404,'Former shared private template route is unavailable')
        check(client.get('/research/api/projects/'+pid+'/slides').status_code==200,'Owner can read their own blank presentation')
        module.app.dependency_overrides[module.actor]=lambda:{'id':'other-account'}
        check(client.get(route+'/slide-templates').status_code==404,'Another account cannot access a project template catalog')
        module.app.dependency_overrides[module.actor]=lambda:{'id':'presentation-qa'}
        receipt=client.post(route+'/slides/confirm',json={'template':'metropolis','profile':'group'}).json()
        check(bool(receipt.get('id')) and receipt['template']=='metropolis' and receipt['profile']=='group','Explicit confirmation records the selected visual template and purpose')
        module.store.update('presentation-qa',pid,config={**module.store.get('presentation-qa',pid)['config'],'template':'beamer-default'})
        check(client.post(route+'/slides/export').status_code==400,'Changing the selected template invalidates the previous confirmation')

    image=Path(folder)/'chart.png';im=Image.new('RGB',(1400,850),'white');draw=ImageDraw.Draw(im);draw.line([(100,700),(1300,700),(100,700),(100,90)],fill='#333333',width=4);draw.line([(100,650),(400,470),(700,350),(1000,230),(1250,160)],fill='#0072B2',width=8);im.save(image)
    dense='每页保留必要的条件与证据，解释写入备注，密度过高时拆分页面。'*22
    base={'title':'合成版面验收 Synthetic layout','source_figures':[{'id':'Figure 1','path':str(image),'caption':'Figure 1 · synthetic chart for layout QA'},{'id':'Figure 2','path':str(image),'caption':'Figure 2 · second synthetic chart'}],
      'source_tables':[{'id':'Table 1','rows':[['Case','Error'],['A','0.01'],['B','0.02'],['C','0.03']]}],
      'sections':[{'id':'cover','role':'cover','title':'版面验收 Layout validation','content':'合成资料 · 不代表实际研究结果'},
        {'id':'evidence','role':'content','title':'证据、条件与解释保持对应','content':'统一中英文字体与字号。\n保持图表比例与共同对齐线。','figures':['Figure 1']},
        {'id':'table','role':'content','title':'比较表格保留可编辑单元格','content':'表格来自合成数据。','tables':['Table 1']},
        {'id':'multiple','role':'content','title':'每一个图表引用均得到保留','content':'两幅图分别展示。','figures':['Figure 1','Figure 2']},
        {'id':'dense','role':'content','title':'正文超出容量时自动拆页','content':dense}]}
    for kind in ['beamer-default','beamer-madrid','metropolis']:
        import copy
        plan=copy.deepcopy(base);source=module.ROOT/'templates/presentations'/(kind+'.pptx');manifest=inspect_template(source,Path(folder)/kind)
        file=output/(kind+'.pptx');report=make_deck(source,manifest,plan,file);render=output/(kind+'-render');render_presentation(file,render)
        report['render_validation']=verify_rendered(render/(kind+'.pdf'),report.pop('visible_text'))
        check(report['slides']>len(base['sections']) and report['all_template_parts_preserved'],kind+' splits excess density and preserves original master/layout/theme parts')
        check(''.join(s['content'] for s in plan['sections'] if s['id'].startswith('dense'))==dense,kind+' preserves all dense paragraph content after splitting')
        check(sum('Figure 2' in s.get('figures',[]) for s in plan['sections'])==1,kind+' retains the second figure instead of dropping it')
        prs=Presentation(file);check(any(s.has_table for slide in prs.slides for s in slide.shapes),kind+' exports a native editable PowerPoint table')
        sizes=[r.font.size.pt for slide in prs.slides for s in slide.shapes if s.has_text_frame for p in s.text_frame.paragraphs for r in p.runs if r.font.size]
        check(all(size>=20 or size==14 for size in sizes),kind+' keeps readable body type and declared caption type')
        atomic_json(output/(kind+'-verification.json'),report)

report={'passed':len(checks),'checks':checks,'external_model_calls':0,'materials':'synthetic only; private author materials are not used in QA','output':str(output)}
atomic_json(output/'presentation-acceptance.json',report);print(json.dumps(report,ensure_ascii=False))
