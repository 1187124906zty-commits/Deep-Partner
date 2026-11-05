"""Stage the author's selected source materials; originals are never changed."""
from pathlib import Path
import json,shutil,tarfile,subprocess,zipfile,xml.etree.ElementTree as ET
ROOT=Path(__file__).resolve().parents[1]
SOURCE=Path('D:/博士工作/博士项目/水分扩散/2026-10-20')
REMOTE='/work/home/cluster_user/research-projects/deeptutor-integration/research-workbench'
stage=ROOT/'build/moisture-import';stage.mkdir(parents=True,exist_ok=True)
def copy(source,relative):
    target=stage/relative;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source,target)
bundle=SOURCE/'Mois-Net_数据图件与绘图程序_20261025/Mois-Net_数据图件与绘图程序_20261025'
for p in (bundle/'绘图程序').glob('*.py'):copy(p,'project/src/plots/'+p.name)
for p in (bundle/'表格数据/tables').iterdir():
    if p.is_file():copy(p,'project/data/tables/'+p.name)
for folder,destination in [('assets','project/src/assets'),('表格数据/assets','project/data/assets')]:
    for p in (bundle/folder).rglob('*'):
        if p.is_file():copy(p,destination+'/'+p.relative_to(bundle/folder).as_posix())
for p in (bundle/'图件').iterdir():
    if p.suffix.lower() in ('.png','.svg','.pdf'):copy(p,'project/results/'+p.name)
copy(bundle/'图件/图件映射与数据核对.md','project/docs/图件映射与数据核对.md')
paper=next(SOURCE.glob('2026-10-30-APINN *.docx'));pdf=paper.with_suffix('.pdf')
copy(paper,'manuscript/source.docx');copy(paper,'project/docs/最新作者稿.docx')
if pdf.exists():copy(pdf,'manuscript/source.pdf');copy(pdf,'project/docs/最新作者稿.pdf')
ns={'w':'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
with zipfile.ZipFile(paper) as z:
    doc=ET.fromstring(z.read('word/document.xml'));first=doc.find('w:body/w:p',ns);title=''.join(n.text or '' for n in first.findall('.//w:t',ns))
state=json.loads((SOURCE/'图1_修订_20261029/figure-state.json').read_text(encoding='utf8'))
for key,path in state['artifacts'].items():
    p=Path(path)
    if p.is_file():copy(p,'project/docs/最新框架图/'+p.name)
meta={'version':1,'name':'Mois-Net · 水分扩散测试','title':title,'manuscript':'manuscript/source.docx','source':str(SOURCE),'source_manuscript':str(paper),'purpose':'Private workbench import and plotting/reading test; no network training or automatic PPT generation'}
(stage/'workbench-import.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2),encoding='utf8')
archive=ROOT/'build/moisture-input.tar.gz'
with tarfile.open(archive,'w:gz') as tar:
    for p in stage.rglob('*'):
        if p.is_file():tar.add(p,arcname=p.relative_to(stage).as_posix())
subprocess.run(['C:/Windows/System32/OpenSSH/scp.exe','-q',str(archive),'research-cluster-xh5:'+REMOTE+'/moisture-input.tar.gz'],check=True,timeout=120)
print(json.dumps({'archive':str(archive),'bytes':archive.stat().st_size,'source':str(SOURCE),'remote':REMOTE+'/moisture-input.tar.gz','title':title},ensure_ascii=False))
