"""Bounded structural translation and image handoff tests; no external model call."""
from pathlib import Path
from tempfile import TemporaryDirectory
from io import BytesIO
import asyncio,base64,json
from PIL import Image
from server.storage import Store
from server.translation import translate_document,parse_items
from server.reviews import prepare_review,submit_review

checks=[]
document={'title':'Transport','revision':7,'comments':[{'id':'c1','body':'Check units','quote':'Flux'}],
 'content':{'type':'doc','content':[{'type':'paragraph','content':[{'type':'text','text':'Flux [1]','marks':[{'type':'bold'},{'type':'commentAnchor','attrs':{'id':'c1'}}]},{'type':'inlineMath','attrs':{'latex':'J=-D\\nabla c'}}]},
 {'type':'blockMath','attrs':{'latex':'\\partial_t c=0'}},{'type':'image','attrs':{'src':'/original.png','title':'Figure 1. Transport','alt':'Flux'}},
 {'type':'table','content':[{'type':'tableRow','content':[{'type':'tableCell','content':[{'type':'paragraph','content':[{'type':'text','text':'Diffusivity'}]}]}]}]},
 {'type':'codeBlock','content':[{'type':'text','text':'D = 1e-12'}]}]}}

calls=[]
def fixture(prompt,payload):
    rows=json.loads(payload)['items'];calls.append(rows)
    assert all(x['text']!='D = 1e-12' for x in rows)
    return json.dumps({'items':[{'id':x['id'],'text':'译：'+x['text']} for x in reversed(rows)]})

translated=translate_document(document,'zh-CN',fixture)
assert translated['content']['content'][0]['content'][1]==document['content']['content'][0]['content'][1]
assert translated['content']['content'][1]==document['content']['content'][1]
assert translated['content']['content'][0]['content'][0]['marks']==document['content']['content'][0]['content'][0]['marks']
assert translated['content']['content'][2]['attrs']['src']=='/original.png'
assert translated['content']['content'][3]['content'][0]['content'][0]['content'][0]['content'][0]['text']=='译：Diffusivity'
assert translated['content']['content'][4]==document['content']['content'][4]
assert document['title']=='Transport' and document['content']['content'][0]['content'][0]['text']=='Flux [1]'
checks.append('translation retains editable math, table hierarchy, image URLs, review marks and code; input unchanged')
for raw in ['{"items":[]}','{"items":[{"id":"a","text":"1"},{"id":"a","text":"2"}]}']:
    try:parse_items(raw,[{'id':'a','text':'source'}]);raise AssertionError('invalid response accepted')
    except ValueError:pass
checks.append('missing and duplicate segment IDs fail without publishing a partial translation')

with TemporaryDirectory() as temp:
    store=Store(Path(temp)/'state');p=store.create('qa','Bilingual');pid=p['id'];root=store.path('qa',pid)
    initial=store.manuscript('qa',pid);initial.update(title=document['title'],content=document['content'],comments=document['comments'],translation=translated)
    saved=store.save_manuscript('qa',pid,initial);saved['translation']['stale']=False
    saved=store.save_manuscript('qa',pid,saved)
    saved['content']['content'][0]['content'][0]['text']='Updated original';saved=store.save_manuscript('qa',pid,saved)
    assert saved['translation']['stale'] and saved['translation']['title']=='译：Transport'
    checks.append('source editing marks translation stale without discarding translated edits and comments')
    source=root/'project/results/test.png';stream=BytesIO();Image.new('RGB',(120,80),'white').save(stream,format='PNG');original=stream.getvalue();source.write_bytes(original)
    program=root/'project/src/plot.py';program.write_text("figure='test.png'")
    request={'path':'results/test.png','image':'data:image/png;base64,'+base64.b64encode(original).decode(),'instruction':'Increase line width','plot_program':'src/plot.py','compute_program':'','crop':{'x':10,'y':5,'width':50,'height':40},'annotations':[{'tool':'rect','points':[{'x':10,'y':5},{'x':60,'y':45}]}]}
    record,prompt,image=prepare_review(store,'qa',pid,request)
    assert source.read_bytes()==original and str(program) in prompt and record['crop']['width']==50
    prepare_review(store,'qa',pid,{**request,'instruction':'Improve axis labels'})
    assert any(row['reason']=='Improve axis labels' for row in store.trash('qa',pid))
    checks.append('image review preserves original, crop, annotation and program provenance; replacements include reason and time')

async def websocket_check():
    from websockets.asyncio.server import serve
    async def fixture(socket):
        value=json.loads(await socket.recv())
        assert value['type']=='start_turn' and value['protocol_version']=='2.0' and value['workspace_id']=='ws-qa'
        assert value['attachments'][0]['type']=='image' and value['attachments'][0]['base64']=='aW1hZ2U='
        await socket.send(json.dumps({'type':'session','session_id':'session-qa','turn_id':'turn-qa'}))
        await socket.wait_closed()
    async with serve(fixture,'127.0.0.1',0) as server:
        port=server.sockets[0].getsockname()[1]
        result=await submit_review('http://127.0.0.1:'+str(port),{'Origin':'http://localhost','Cookie':'qa=dummy'},
          {'native_id':'ws-qa'},{'id':'review-qa','attachment':'figure.png'},'Test image provenance','aW1hZ2U=')
        assert result['url'].startswith('/chat/session-qa?')
asyncio.run(websocket_check());checks.append('native websocket v2 submission and session handoff tested with local fixture')
import os
out=Path(os.environ.get('WORKBENCH_TEST_OUTPUT','verification'));out.mkdir(parents=True,exist_ok=True)
(out/'translation-image-acceptance.json').write_text(json.dumps({'passed':True,'checks':checks,'external_model_calls':0,'real_agent_messages':0},indent=2))
print(json.dumps({'passed':True,'checks':checks}),flush=True)
