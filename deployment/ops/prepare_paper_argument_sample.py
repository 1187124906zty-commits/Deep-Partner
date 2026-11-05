"""Connect the paper's purpose, consequential gaps, choices and bounded answer."""
from pathlib import Path
import json,sys
ROOT=Path(__file__).resolve().parents[1]
SOURCE=Path('D:/Development/research-workbench');sys.path.insert(0,str(SOURCE))
from server.paper_map_core import normalize_map,source_sentences

folder=ROOT/'reports/氯硫框架具体化/paper-maps-20261104/qin2020'
source=json.loads((folder/'automatic-source.json').read_text(encoding='utf8'))
by_id={u['id']:u for u in source['units']}
def quote(uid,start):
    text=next(s['text'] for s in source_sentences(by_id[uid]) if start in s['text'])
    return {'source_id':uid,'quote':text[text.index(start):]}

nodes=[]
def node(ident,parent,role,label,content,quotes,section_type):
    nodes.append({'id':ident,'parent_id':parent,'kind':'paper' if ident=='paper' else 'conclusion' if role=='scope' else 'paragraph' if role=='gap' else 'analysis',
       'section_type':section_type,'label':label,'content':content,'keywords':[label],
       'source_ids':list(dict.fromkeys(q['source_id'] for q in quotes)),'source_quotes':quotes,
       'argument_role':role,'key_point':ident!='paper','order':len(nodes)})

node('paper',None,'question','钙溶出与温度变化如何影响硫酸盐侵蚀引起的膨胀',
     '本文以硫酸盐侵蚀中的膨胀预测为主线。作者指出已有模型对钙溶出和温度的处理不足，据此增加模型关系和对照，再区分已解释的响应与低温下仍未解释的偏差。图中的不足服务于这一主线，并非全面列举该领域所有缺点。',
     [quote('u00006','The preceding literature survey suggests')],'introduction')
node('chemical_gap','paper','gap','现有模型常忽略钙溶出，可能漏掉改变膨胀的不同作用',
     '原文首先指出所评述模型多忽略钙溶出，又说明溶出会改变传输与力学性能。将这项不足与全文联系后，其职责是说明为什么需要把钙离子补给及溶解引起的孔隙变化写入膨胀模型，并区分它们的作用。本节点的“可能漏掉”属于依据引言与后文比较作出的组织解释。',
     [quote('u00005','However, most models'),quote('u00005','Calcium leaching causes transport properties')],'introduction')
node('temperature_gap','paper','gap','所评述模型对温度作用的考虑仍不足，膨胀的温度依赖性有待描述',
     '作者在评述既有模型时指出多采用等温假设，紧接着强调扩散、化学反应和膨胀随温度改变。这里的不足针对所评述模型对温度作用的考虑，不能解释为任何等温计算都无法比较温度：10°C和23°C两个工况仍可各自保持恒温。',
     [quote('u00005','However, most models'),quote('u00005','Temperature variation has')],'introduction')
node('chemical_choice','chemical_gap','approach','在模型中描述钙溶出与孔隙变化，比较省略不同作用后的膨胀预测',
     '为回应前一不足，本文在模型中描述钙溶出和相应孔隙变化，并比较完整模型、仅不考虑溶解引起的孔隙变化、完全忽略钙溶出等情形。完全忽略钙溶出会同时关闭钙离子补给及相应孔隙变化，不能把它写成严格独立的单因素关闭。',
     [quote('u00006','The proposed model accounts'),quote('u00140','Fig. 2 shows that expansion strain is overestimated'),quote('u00141','However, expansion is underestimated')],'results')
node('temperature_choice','temperature_gap','approach','使扩散、化学反应和钙溶出随温度变化，并与同一砂浆的10°C和23°C恒温膨胀试验对照',
     '为回应所评述模型对温度作用考虑不足的问题，作者使温度进入化学反应、钙溶出和离子传输关系，并与同一对照砂浆在10°C、23°C下的试验比较。实际对照主要属于两个恒温条件，未据此宣称温度梯度场得到验证。',
     [quote('u00006','The effects of temperature variation'),quote('u00144','The focus is on the expansion profile')],'results')
node('chemical_answer','chemical_choice','finding','仅忽略溶解引起的孔隙变化会高估膨胀，完全忽略钙溶出会低估膨胀',
     '这项比较回答了为什么不能把钙溶出当作单一方向的作用：矿物溶解为化学反应补充钙离子，也增加膨胀产物可以填充的孔隙空间。省略不同作用会使模型相对试验的膨胀偏差方向相反。该认识回应前文模型遗漏的实际后果，而不止得出“钙溶出很重要”。',
     [quote('u00150','The model would overestimate'),quote('u00150','However, the model would underestimate')],'conclusion')
node('temperature_answer','temperature_choice','finding','模型解释了较高温度下的较大膨胀，但仍低估低温膨胀',
     '温度对照支持作者用更快的扩散及化学反应解释23°C条件下较大的膨胀；低温条件的预测偏差更大，说明所增加的模型关系仍不足以解释全部温度影响。结论需要同时保留得到的解释与残余偏差。',
     [quote('u00144','These interpretations show'),quote('u00145','The discrepancy between model prediction'),quote('u00146','results underestimate the expansion')],'results')
node('outlook','temperature_answer','scope','用更多数据改进温度预测，并考虑碳硫硅钙石形成或钙矾石溶解度变化',
     '后续方向由低温条件的残余偏差产生。原文明确提出需要更多信息和数据，并考虑碳硫硅钙石形成或钙矾石溶解度变化；这是作者提出的模型改进方向，不是本研究已经实现的机制，也不是与结果无关的一般展望。',
     [quote('u00146','More data and amendment')],'conclusion')

edges=[]
def edge(a,b,relation,explanation):
    ids=list(dict.fromkeys(uid for n in nodes if n['id'] in (a,b) for uid in n['source_ids']))
    edges.append({'id':'purpose-'+str(len(edges)+1),'from':a,'to':b,'relation':relation,'explanation':explanation,
                  'source_ids':ids,'basis':'inferred','show_label':False})
edge('paper','chemical_gap','与主旨有关的不足','为解释膨胀预测，先识别会改变反应及孔隙作用的钙溶出遗漏。')
edge('paper','temperature_gap','与主旨有关的不足','同一膨胀预测目标还需要描述温度改变材料过程的作用，不能把单一温度下的描述直接外推。')
edge('chemical_gap','chemical_choice','因此选择模型和比较','钙溶出遗漏之所以值得提出，是因为后文将对应作用写入模型，并分别比较它们对预测的影响。')
edge('temperature_gap','temperature_choice','因此选择模型和试验对照','扩散与化学反应速率随温度变化，为采用温度相关关系及恒温试验对照提供理由。')
edge('chemical_choice','chemical_answer','比较回答了什么','省略不同作用引起的相反偏差，具体说明前述模型遗漏会怎样改变膨胀预测。')
edge('temperature_choice','temperature_answer','比较回答到哪里','较高温度响应得到解释，而低温偏差保留了当前模型的解释边界。')
edge('temperature_answer','outlook','残余问题决定后续方向','未来补充的化学过程和数据直接来自低温预测偏差，而非为了列展望而列展望。')

story={'author_question':nodes[0]['label'],'main_claim':'钙溶出和温度处理的不足因会改变膨胀预测而进入论证；相应模型及比较解释了不同作用，却留下低温化学描述需要补充的边界。',
       'organization_summary':'核心主旨→有关的不足及其后果→研究选择→回答与局限→由残余问题产生的改进方向。',
       'key_node_ids':[n['id'] for n in nodes[1:]],'means_ends':[],'promise_evidence':[],'learning_points':[],
       'purpose_routes':[
         {'gap_node_id':'chemical_gap','purpose':'区分钙溶出遗漏会怎样改变膨胀预测。','choice_node_ids':['chemical_choice'],'evidence_node_ids':['chemical_answer'],'source_ids':['u00005','u00006','u00140','u00141','u00150']},
         {'gap_node_id':'temperature_gap','purpose':'解释温度改变膨胀的程度与仍未解释的条件。','choice_node_ids':['temperature_choice'],'evidence_node_ids':['temperature_answer'],'limit_node_ids':['outlook'],'source_ids':['u00005','u00006','u00144','u00145','u00146']}
       ]}
graph=normalize_map(source,{'nodes':nodes,'edges':edges,'keywords':['硫酸盐侵蚀膨胀','钙溶出','温度变化','模型比较','低温偏差'],'story':story})
graph['coverage']['needs_review'].insert(0,'作者试读候选：主图精选全文论证联系，逐节逐段内容保留在后续完整图谱；效果等待作者反馈。')
graph['review_status']='awaiting_author_feedback'
(folder/'argument-purpose-canvas-candidate.json').write_text(json.dumps(graph,ensure_ascii=False,indent=2),encoding='utf8')
(folder/'key-canvas-candidate.json').write_text(json.dumps(graph,ensure_ascii=False,indent=2),encoding='utf8')
print(json.dumps({'nodes':len(nodes),'edges':len(edges),'source_quotes':sum(len(n['source_quotes']) for n in graph['nodes'])},ensure_ascii=False))
