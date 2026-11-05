"""Native edit transport executes the reader protocol instead of rewriting it."""
from unittest.mock import patch
from tempfile import TemporaryDirectory
from pathlib import Path
import asyncio,json,httpx
from server import app as module
from server.storage import Store
from server.neoreader import instances,native_sessions
with TemporaryDirectory() as folder:
 root=Path(folder);module.store=Store(root/'store');module.api_path=lambda owner:root/'unconfigured.json'
 p=module.store.create('fixture','Native reader protocol');pid=p['id'];instances[pid]={'owner':'fixture','token':'fixture'};native_sessions[pid]={'Origin':'fixture'}
 seen=[]
 def invoke(settings,headers,native,prompt,text,base,structured,task):
  seen.append((prompt,text));return '{"blockId":"p1-b1","sentences":[{"source":"湿度","target":"humidity"}]}'
 async def exercise():
  transport=httpx.ASGITransport(app=module.app,client=('127.0.0.1',1234))
  async with httpx.AsyncClient(transport=transport,base_url='http://127.0.0.1') as client:
   r=await client.post('/internal/reader-model/'+pid+'/v1/chat/completions',headers={'Authorization':'Bearer fixture'},json={'messages':[{'role':'system','content':'Reading assistant.'},{'role':'user','content':'只输出 JSONL。逐段翻译为科技英语。输入资料：\n{"batch":{"paragraphs":[{"blockId":"p1-b1","source":"湿度"}]}}\n数学标记必须保留。'}]})
   assert r.status_code==200
   assert 'humidity' in r.json()['choices'][0]['message']['content']
 with patch('server.models.complete',invoke):asyncio.run(exercise())
 assert len(seen)==1 and '直接执行' in seen[0][0] and '不要重写' in seen[0][0] and '数学标记必须保留' in seen[0][0]
 assert json.loads(seen[0][1])['batch']['paragraphs'][0]['source']=='湿度'
 assert '只输出' not in seen[0][1]
 instances.pop(pid,None);native_sessions.pop(pid,None)
 print(json.dumps({'passed':True,'checks':['execute native reader task','do not rewrite operation prompt','source JSONL input unchanged']}))
