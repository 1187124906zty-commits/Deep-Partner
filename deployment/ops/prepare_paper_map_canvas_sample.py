"""Build an explicitly limited introduction canvas from the read Qin source."""
from pathlib import Path
import json,sys

ROOT=Path(__file__).resolve().parents[1]
SOURCE=Path('D:/Development/research-workbench')
sys.path.insert(0,str(SOURCE))
from server.paper_map_core import normalize_map

folder=ROOT/'reports/氯硫框架具体化/paper-maps-20261104/qin2020'
source=json.loads((folder/'automatic-source.json').read_text(encoding='utf8'))
read=json.loads((folder/'content-map.json').read_text(encoding='utf8'))
originals={u['id']:u for u in source['units']}

def sentence(uid,start):
    text=originals[uid]['text'];i=text.index(start);j=text.find('. ',i)
    return text[i:j+1] if j>=0 else text[i:]

def node(ident,parent,kind,label,content,uid=None,quote=None,**extra):
    return {'id':ident,'parent_id':parent,'kind':kind,'section_type':'introduction' if kind!='paper' else 'other',
            'label':label,'content':content,'keywords':[label],'source_ids':[uid] if uid else [],
            'source_quotes':[{'source_id':uid,'quote':quote}] if uid and quote else [],'order':len(nodes),**extra}

nodes=[]
nodes.append(node('paper',None,'paper','硫酸盐侵蚀膨胀','本文考察钙溶出与温度怎样改变外硫酸盐侵蚀中的膨胀和损伤预测。'))
nodes.append(node('sec.s0002','paper','section','引言','先说明硫酸盐侵蚀中的反应与劣化，再分析已有模型及钙溶出、温度的遗漏，最后提出相应模型与试验比较。','u00003',source_section_id='s0002'))
labels=['硫酸盐反应与材料劣化','反应—传输—损伤模型','钙溶出与温度影响','溶出—温度耦合模型']
for i,uid in enumerate(['u00003','u00004','u00005','u00006']):
    text=originals[uid]['text'];quote=sentence(uid,text[:50])
    nodes.append(node('para.'+uid,'sec.s0002','paragraph',labels[i],read['intro_nodes'][i]['content'],uid,quote))

elements={
 'u00003':[
 ('硫酸根侵入','外来硫酸根打破孔液平衡，引起膨胀产物生成及CH、C–S–H的变化。','The intrusion of external sulfate ions'),
 ('石膏与钙矾石填孔','石膏和钙矾石等产物填充孔隙，随后出现微裂纹和膨胀。','Expansion products, such as gypsum and ettringite'),
 ('微裂纹与膨胀','产物填孔与微裂纹、膨胀在同一句中建立联系。','Expansion products, such as gypsum and ettringite'),
 ('C–S–H脱钙','C–S–H脱钙削弱水泥浆与骨料间的黏结。','Decalcification of C-S-H'),
 ('混凝土强度下降','作者将强度下降联系到C–S–H脱钙引起的黏结弱化。','Decalcification of C-S-H')],
 'u00004':[
 ('多离子传输与平衡','作者回顾以局部平衡处理扩散和化学反应的多离子传输描述。','Marchand and coworkers'),
 ('损伤对扩散的反馈','已有研究将累计力学损伤对扩散的影响纳入描述。',None),
 ('裂缝吸液','新生未饱和裂缝的吸液作用可以加快扩散。',None),
 ('膨胀、变形与应力','已有综合模型把扩散、化学反应和力学行为连接到膨胀等预测量。','An integrated model with diffusion')],
 'u00005':[
 ('模型中的溶出省略','作者认为所评述模型仍多忽略钙溶出并采用等温假设。','However, most models'),
 ('CH溶解与C–S–H脱钙','原文按CH先溶解、C–S–H随后脱钙描述钙溶出。','Calcium leaching associated with sulfate attack'),
 ('扩散率增大','作者将钙溶出引起的传输劣化具体表述为扩散率增大。','Calcium leaching causes transport properties'),
 ('强度下降','同一句将钙溶出引起的力学劣化具体表述为强度下降。','Calcium leaching causes transport properties'),
 ('温度变化','温度变化影响离子扩散和化学反应的速率。','Temperature variation has'),
 ('扩散与反应速率','这两个速率是温度影响侵蚀过程的入口。','Temperature variation has')],
 'u00006':[
 ('固液平衡曲线','本文通过固液平衡曲线描述钙溶出中的扩散与溶解。','Calcium leaching is considered'),
 ('CH/C–S–H溶解增孔','模型包含硫酸盐浸泡加快溶出，以及CH、C–S–H溶解带来的孔隙变化。','The proposed model accounts'),
 ('温度梯度与过程速率','模型从温度梯度、反应和溶出速率及离子传输速率分析温度作用。','The effects of temperature variation'),
 ('两组试验对照','本文用Rozière和Hossack、Thomas发表的试验结果检查模型。','The model is validated using')],
}
exact={('u00004',1):'Sarkar et al. [20] used continuum damage mechanics to quantify the effects of cumulative mechanical damage on diffusion.',
       ('u00004',2):'Yu et al. [1] introduced the cracking suction effect into their model to describe the suction action of newly formed unsaturated cracks in accelerating the diffusion process.'}
for uid,entries in elements.items():
    for index,(label,content,start) in enumerate(entries):
        quote=exact.get((uid,index)) or sentence(uid,start)
        if start=='The model is validated using':quote=originals[uid]['text'][originals[uid]['text'].index(start):]
        nodes.append(node('element.'+uid+'.'+str(index),'para.'+uid,'element',label,content,uid,quote))

edges=[]
def edge(a,b,relation,explanation,ids):
    edges.append({'id':'relation-'+str(len(edges)+1),'from':a,'to':b,'relation':relation,'explanation':explanation,'source_ids':ids,'basis':'inferred'})
for uid,a,b,relation,why in [
 ('u00003',0,1,'诱发反应','硫酸根进入改变孔液状态，后文进一步具体到膨胀产物。'),
 ('u00003',1,2,'引起','原文把低溶解度产物填孔接到微裂纹与膨胀。'),
 ('u00003',3,4,'削弱','脱钙通过黏结弱化解释强度下降。'),
 ('u00004',0,1,'引入力学反馈','已有描述由离子扩散及反应推进到损伤对扩散的影响。'),
 ('u00004',1,2,'补充裂缝作用','累计损伤以外，裂缝吸液提供另一项影响迁移的作用。'),
 ('u00004',2,3,'共同描述','已有模型把传输、反应和力学行为连接到宏观膨胀等量。'),
 ('u00005',0,1,'具体过程','作者先指出溶出被省略，再说明溶出的相变化次序。'),
 ('u00005',1,2,'改变传输','CH溶解与C–S–H脱钙被接到扩散率增大。'),
 ('u00005',1,3,'改变力学性能','同一溶出过程也被接到强度下降。'),
 ('u00005',4,5,'改变速率','温度变化影响离子扩散及化学反应速率。'),
 ('u00006',0,1,'计入孔隙变化','钙溶出关系进一步连接到CH、C–S–H溶解产生的孔隙变化。'),
 ('u00006',1,2,'并入温度作用','作者同时补入温度梯度及各过程速率的影响。'),
 ('u00006',2,3,'试验检查','新增描述最终以两组试验的膨胀结果作检查。')]:
    edge('element.'+uid+'.'+str(a),'element.'+uid+'.'+str(b),relation,why,[uid])
for a,b,relation,why in [
 ('u00003','u00004','已有模型怎样描述','第一段的反应、脱钙和劣化，使第二段讨论扩散—反应—损伤模型具有具体对象。'),
 ('u00004','u00005','哪些影响仍被省略','已有模型已能预测膨胀与损伤，作者继而问忽略钙溶出和温度会漏掉什么。'),
 ('u00005','u00006','将影响写入模型','前段解释了溶出和温度为何会改变侵蚀预测，末段才提出对应的计算关系与试验。')]:
    edge('para.'+a,'para.'+b,relation,why,[a,b])
story={'author_question':read['author_question'],'main_claim':read['one_sentence_argument'],'organization_summary':'此候选只展示Qin论文引言的主题词组、段内关系和段间联系，供作者检查图谱效果。','means_ends':[],'promise_evidence':[],'learning_points':[]}
graph=normalize_map(source,{'nodes':nodes,'edges':edges,'keywords':['硫酸盐侵蚀','钙溶出','温度','膨胀','孔隙变化'],'story':story})
graph['coverage']['needs_review'].insert(0,'作者试读候选：本图仅包含引言，尚未纳入方法、结果和结论；不作为完整论文图谱验收。')
graph['review_status']='awaiting_author_feedback'
target=folder/'intro-canvas-candidate.json';target.write_text(json.dumps(graph,ensure_ascii=False,indent=2),encoding='utf8')
print(json.dumps({'path':str(target),'nodes':len(graph['nodes']),'edges':len(graph['edges']),'verified_sentences':sum(len(n['source_quotes']) for n in graph['nodes'])},ensure_ascii=False))
