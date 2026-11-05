"""A source-bound trial of Qin's pivotal argument, rather than a concept list."""
from pathlib import Path
import json,sys
ROOT=Path(__file__).resolve().parents[1]
SOURCE=Path('D:/Development/research-workbench');sys.path.insert(0,str(SOURCE))
from server.paper_map_core import normalize_map,source_sentences

folder=ROOT/'reports/氯硫框架具体化/paper-maps-20261104/qin2020'
source=json.loads((folder/'automatic-source.json').read_text(encoding='utf8'))
by_id={u['id']:u for u in source['units']}
def exact(uid,start,end=None):
    text=by_id[uid]['text'];a=text.index(start)
    if end is not None:return text[a:text.index(end,a)+len(end)]
    return next(sentence['text'] for sentence in source_sentences(by_id[uid]) if sentence['text'].startswith(start))

definitions=[
 ('model','仅忽略溶解引起的孔隙变化，或完全忽略钙溶出，对照膨胀预测','本文用固液平衡描述钙溶出，并把硫酸盐加速溶出及氢氧化钙和水化硅酸钙溶解导致的孔隙变化纳入模型；后文分别计算仅不考虑溶解引起的孔隙变化、完全不考虑钙溶出两种模型的膨胀响应；后一项同时关闭钙离子补给及溶解引起的孔隙变化。','u00139','results',exact('u00139','Fig. 2 shows the influence'),'approach'),
 ('tempcompare','比较10°C和23°C条件下的试件膨胀','作者比较相同对照砂浆在10°C和23°C下的膨胀。这两个恒温条件用于分析温度改变扩散和反应后的材料响应，不能替代变温梯度场的验证。','u00144','results',exact('u00144','The focus is on the expansion profile'),'approach'),
 ('overestimate','不考虑溶解引起的孔隙变化，会高估试验中的膨胀','氢氧化钙溶解和水化硅酸钙脱钙增加可容纳产物的孔隙。仅省略这一孔隙变化，会让较少的产物就产生膨胀，因而高估试件膨胀。原文图2及相邻解释承担这项判断。','u00140','results',exact('u00140','Fig. 2 shows that expansion strain is overestimated'),'evidence'),
 ('underestimate','完全忽略钙溶出，会低估试验中的膨胀','完全关闭钙溶出同时切断反应中的钙离子的补充。初始孔液钙消耗后，反应和钙矾石生成减弱，膨胀被低估。这与仅不考虑溶解引起的孔隙变化的对照不是同一模型变化。','u00141','results',exact('u00141','However, expansion is underestimated'),'evidence'),
 ('competition','钙溶出对膨胀的影响取决于钙离子补给与孔隙增加的相对作用','作者用参与反应的铝酸钙含量和溶解的固相钙含量解释两类作用的竞争。硫酸盐浓度变化会改变两项变化的相对大小，故不能把溶出对膨胀的作用写成固定单向影响。','u00140','results',exact('u00140','Thus the effect of calcium leaching on expansion'),'finding'),
 ('temperature','同一砂浆在23°C下的膨胀大于10°C','作者用扩散和化学反应加快、更多产物生成解释较高温度下的较大膨胀。此处是同一对照砂浆的恒温比较；没有把一般温度梯度求解也称为已验证。','u00144','results',exact('u00144','These interpretations show'),'evidence'),
 ('limit','模型低估低温下的膨胀，仍需补充温度相关的化学过程','低温下偏差更大，作者讨论碳硫硅钙石形成与钙矾石溶解度等未充分描述的因素。图中保留这一剩余偏差，不将温度响应写成已完整解释。','u00146','results',exact('u00146','More data and amendment'),'scope'),
]
nodes=[{'id':'paper','parent_id':None,'kind':'paper','section_type':'other','label':'钙溶出与温度变化如何影响硫酸盐侵蚀引起的膨胀','content':'Qin等研究钙溶出与温度对外硫酸盐侵蚀膨胀的影响。主图并列两条研究路径：比较仅忽略溶解引起的孔隙变化与完全忽略钙溶出、比较两种恒温条件，再将响应方向连接到相应认识和边界。已有模型及一般背景保留在原文详情中。','keywords':['钙溶出','硫酸盐膨胀'],'source_ids':[],'order':0,'argument_role':'question'}]
for order,(ident,label,content,uid,role,quote,argument_role) in enumerate(definitions,1):
    parent='model' if ident in ('overestimate','underestimate','competition') else 'temperature' if ident=='limit' else 'tempcompare' if ident=='temperature' else 'paper'
    nodes.append({'id':ident,'parent_id':parent,'kind':{'introduction':'paragraph','methods':'analysis','results':'comparison','discussion':'discussion','conclusion':'conclusion'}[role],
                  'section_type':role,'label':label,'content':content,'keywords':[label],'source_ids':[uid],
                  'source_quotes':[{'source_id':uid,'quote':quote}],'key_point':True,'argument_role':argument_role,'order':order})
model_node=next(n for n in nodes if n['id']=='model')
model_node['source_ids']=['u00139','u00140','u00141']
model_node['source_quotes']=[{'source_id':'u00140','quote':exact('u00140','Fig. 2 shows that expansion strain is overestimated')},{'source_id':'u00141','quote':exact('u00141','However, expansion is underestimated')}]
edges=[]
for a,b,relation,reason in [
 ('paper','model','模型省略对照','研究问题中的钙溶出作用，由上述两种省略条件的膨胀比较回答。'),
 ('paper','tempcompare','恒温条件对照','研究问题中的温度影响，由同一砂浆在两种恒温条件下的膨胀比较回答。'),
 ('model','overestimate','不考虑溶解引起的孔隙变化','相同模型和试验背景下，仅不计溶出带来的孔隙增加时，膨胀预测偏大。'),
 ('model','underestimate','完全忽略钙溶出','另一项对照把钙溶出整体关闭，钙离子的补充被切断，膨胀预测偏小。'),
 ('overestimate','competition','说明孔隙容纳产物的作用','高估情形说明产物生成以外的孔隙容纳不可省略；此箭头是作者的证据论证关系，并非膨胀高估会物理导致竞争。'),
 ('underestimate','competition','说明钙离子补给的作用','低估情形说明钙离子的补充对产物生成的重要性；两项响应共同支持钙离子补给与孔隙变化的相对作用的解释。'),
 ('tempcompare','temperature','温度对照结果','在两种恒温条件下，作者用反应和扩散速率增加解释较高温度时更大的膨胀。'),
 ('temperature','limit','限定温度解释','较高温度的响应解释并不消除低温条件下的未解释膨胀。')]:
    ids=list(dict.fromkeys(u for n in nodes if n['id'] in (a,b) for u in n['source_ids']))
    edges.append({'id':'key-'+str(len(edges)+1),'from':a,'to':b,'relation':relation,'explanation':reason,'source_ids':ids,'basis':'inferred','show_label':False})
story={'author_question':'钙溶出和温度怎样改变硫酸盐侵蚀中的膨胀预测？','main_claim':'钙溶出为化学反应补充钙离子，同时增加膨胀产物可以填充的孔隙空间；忽略不同作用，会使膨胀偏差方向相反。温度对照仍留下低温条件下的未解释偏差。','organization_summary':'研究钙溶出与温度的两条并列路径：具体处理→对照响应→材料认识或剩余偏差。','key_node_ids':[n['id'] for n in nodes[1:]],'means_ends':[],'promise_evidence':[],'learning_points':[]}
graph=normalize_map(source,{'nodes':nodes,'edges':edges,'keywords':['钙溶出','膨胀偏差','钙离子补给与孔隙变化','温度'],'story':story})
graph['coverage']['needs_review'].insert(0,'作者试读候选：这里只精选推进论文认识的关键判断，完整逐节逐段图谱尚未合入；内容与视觉效果等待作者反馈。')
graph['review_status']='awaiting_author_feedback'
target=folder/'key-canvas-candidate.json';target.write_text(json.dumps(graph,ensure_ascii=False,indent=2),encoding='utf8')
print(json.dumps({'path':str(target),'nodes':len(nodes),'edges':len(edges)},ensure_ascii=False))
