"""Scientific paragraph grammar can move while equations and values stay exact."""
from copy import deepcopy
import json
from server.academic_translation import translate_document,encode_inline,decode_inline

math={'type':'inlineMath','attrs':{'latex':r'H=\alpha_v^2'}}
source={'title':'湿度重建','revision':7,'content':{'type':'doc','content':[
 {'type':'paragraph','content':[{'type':'text','text':'采用五个传感器测量湿度 '},math,{'type':'text','text':'，误差降低75%。','marks':[{'type':'bold'}]}]},
 {'type':'blockMath','attrs':{'latex':r'R=\begin{cases}a,&\text{给定通量},\\b,&\text{给定湿度}.\end{cases}'}}
]},'comments':[]}
original=deepcopy(source);seen=[]
def model(prompt,payload):
    rows=json.loads(payload)['items'];seen.extend(rows)
    replacements={'湿度重建':'Humidity reconstruction','给定通量':'prescribed flux','给定湿度':'prescribed humidity'}
    return json.dumps({'items':[{'id':r['id'],'text':replacements.get(r['text'],'Five sensors measured the humidity __WBO0__<wb0>, reducing the error by 75%.</wb0>')} for r in rows]})
translated=translate_document(source,'en',model)
assert len([r for r in seen if r['kind']=='paragraph'])==1,'Paragraph fragmented around its equation'
assert translated['content']['content'][0]['content'][1]==math
assert translated['content']['content'][0]['content'][2]['marks']==source['content']['content'][0]['content'][2]['marks']
assert translated['content']['content'][1]['attrs']['latex']==source['content']['content'][1]['attrs']['latex'].replace('给定通量','prescribed flux').replace('给定湿度','prescribed humidity')
assert source==original
encoded,objects,styles=encode_inline(source['content']['content'][0]['content'])
for invalid in [encoded.replace('__WBO0__',''),encoded.replace('75','85'),encoded.replace('__WBO0__','__WBO0____WBO0__')]:
    try:decode_inline(invalid,encoded,objects,styles)
    except ValueError:pass
    else:raise AssertionError('Changed scientific object/value was accepted')
try:decode_inline('C80 concrete: 0.372','C80 concrete: −0.372',{}, {})
except ValueError:pass
else:raise AssertionError('Negative sign changed during translation')
attempts=[]
def repairs(prompt,payload):
    data=json.loads(payload);attempts.append(data)
    return json.dumps({'items':[{'id':i['id'],'text':('Error decreased by 75%.' if data.get('validation_error') else 'Error decreased by 85%.')} for i in data['items']]})
retry_source={'title':'Test','revision':1,'content':{'type':'doc','content':[{'type':'paragraph','content':[{'type':'text','text':'误差降低75%。'}]}]}}
repaired=translate_document(retry_source,'en',repairs)
assert repaired['content']['content'][0]['content'][0]['text']=='Error decreased by 75%.' and len(attempts)==2
print(json.dumps({'passed':True,'checks':['one paragraph across math runs','exact formula object','editable marks','math prose labels only','numeric fidelity','protected object count','original unchanged']}))
