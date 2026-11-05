"""Receive the completed private outputs in bounded authenticated byte ranges."""
from concurrent.futures import ThreadPoolExecutor,as_completed
from pathlib import Path
from urllib.parse import quote
from urllib.request import Request,urlopen
from zipfile import ZipFile
import argparse,json,re

ROOT=Path(__file__).resolve().parents[1];out=ROOT/'verification/user-issues/native';out.mkdir(exist_ok=True,parents=True)
BASE='http://127.0.0.1:47901/research/api/projects/05a893386c09449d88366cf6dfdc825f/download?area=manuscript&name='
parser=argparse.ArgumentParser();parser.add_argument('--chinese-name',default='中文稿-西北工业大学学报');parser.add_argument('--chinese-only',action='store_true');args=parser.parse_args()
files=[(args.chinese_name+'.docx','chinese.docx'),(args.chinese_name+'.pdf','chinese.pdf')]
if not args.chinese_only:files += [('英文稿-CAS.docx','english.docx'),('期刊排版预览.pdf','cas-preview.pdf')]
report=[]
for name,local in files:
 url=BASE+quote(name);chunk=131072
 def receive(start,end):
  for attempt in range(3):
   try:
    with urlopen(Request(url,headers={'Range':f'bytes={start}-{end}'}),timeout=25) as r:
     data=r.read();match=re.fullmatch(r'bytes (\d+)-(\d+)/(\d+)',r.headers.get('Content-Range',''))
     assert r.status==206 and match and int(match[1])==start
     assert len(data)==int(match[2])-start+1
     return start,data,int(match[3])
   except (OSError,TimeoutError):
    if attempt==2:raise
 first,data,total=receive(0,chunk-1);buffer=bytearray(total);buffer[:len(data)]=data
 with ThreadPoolExecutor(max_workers=4) as pool:
  for future in as_completed([pool.submit(receive,start,min(total-1,start+chunk-1)) for start in range(chunk,total,chunk)]):
   start,data,expected=future.result();assert expected==total;buffer[start:start+len(data)]=data
 path=out/local;pending=path.with_suffix(path.suffix+'.part');pending.write_bytes(buffer)
 if local.endswith('.docx'):
  with ZipFile(pending) as archive:assert archive.testzip() is None and 'word/document.xml' in archive.namelist()
 else:assert buffer.startswith(b'%PDF-') and b'%%EOF' in buffer[-2048:]
 pending.replace(path);row={'name':name,'local':str(path),'bytes':total,'validated':True};report.append(row);print(json.dumps(row,ensure_ascii=False),flush=True)
(out/'downloads.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
