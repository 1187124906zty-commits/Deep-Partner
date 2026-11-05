"""Render the actual repaired candidates while their text-only review runs."""
from pathlib import Path
import json
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]


def main():
    sys.stdout.reconfigure(encoding='utf8')
    subprocess.run(['scp','-q','-o','ProxyJump=research-cluster-xh5',str(ROOT/'ops/patch_author_docx.py'),
        'papers-research:/srv/research-workbench/tools/patch_author_docx.py'],check=True,timeout=60)
    code=r'''from pathlib import Path
import sys,json,subprocess
sys.path.insert(0,'/opt/workbench-tools')
from patch_author_docx import patch
from server.manuscripts import export_manuscript
from PIL import Image,ImageDraw
import fitz
base=Path('/workspace/outputs/.deeptutor/chat/2e1f7a59cda65ffb9355b8afa9e999f9/workspaces')
for ws,rid,label in [('ws_0e6fc7aba58a4b258e25e1195702fde3','7f057f9e0e5a441aa7e9238337d93f3e','intro'),('ws_06a666b5802645998b8ad9513dbc10ab','f4daf4284d7448e0824b281f059bf938','moisture')]:
 root=base/ws;folder=root/'.workbench/writing/runs'/rid;state=json.loads((folder/'state.json').read_text())
 assert (folder/'parser-repair.json').exists()
 target=folder/'author-review-candidate.docx'
 if label=='moisture':
  edits=[]
  for stage in ['narrow','wide']:
   p=folder/(stage+'-edits.json')
   for report in json.loads(p.read_text())['reports']:edits.extend(report['accepted'])
  result=patch(root/'project/docs/最新作者稿.docx',target,state['source_document'],edits)
  assert result['saved'],result
  (folder/'author-word-patch.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
 else:
  data,_,_=export_manuscript(root,state['candidate_document'],'docx');target.write_bytes(data)
 out=folder/'render-candidate'
 result=subprocess.run(['python','/opt/workbench-tools/render_writing_docx.py',str(target),'--output_dir',str(out),'--emit_pdf'],capture_output=True,text=True,timeout=180)
 assert result.returncode==0,result.stdout+result.stderr
 pdf=next(out.glob('*.pdf'));doc=fitz.open(pdf)
 for start in range(0,len(doc),6):
  sheet=Image.new('RGB',(1440,2040),'#e8e8e8');draw=ImageDraw.Draw(sheet)
  for j,page in enumerate(list(doc)[start:start+6]):
   pix=page.get_pixmap(matrix=fitz.Matrix(.8,.8),alpha=False);im=Image.frombytes('RGB',[pix.width,pix.height],pix.samples);im.thumbnail((690,640))
   x=(j%2)*720+(720-im.width)//2;y=(j//2)*680+30;sheet.paste(im,(x,y))
   draw.text(((j%2)*720+18,(j//2)*680+9),label+' candidate page '+str(start+j+1),fill='black')
  sheet.save(out/('contact-'+str(start//6+1)+'.jpg'),quality=85)
 report={'task':label,'word':str(target),'word_bytes':target.stat().st_size,'pdf':str(pdf),'pages':len(doc),'contact_sheets':len(list(out.glob('contact-*.jpg'))),'author_approval':'pending'}
 (folder/'candidate-render.json').write_text(json.dumps(report,ensure_ascii=False,indent=2));print(json.dumps(report),flush=True)
'''
    result=subprocess.run(['ssh','-o','ProxyJump=research-cluster-xh5','papers-research','docker exec -i research-workbench python -'],
        input=code,capture_output=True,text=True,encoding='utf8',timeout=300)
    print(result.stdout);print(result.stderr[-2000:]);assert result.returncode==0
    (ROOT/'reports/writing-candidate-renders.jsonl').write_text(result.stdout,encoding='utf8')


if __name__=='__main__':main()
