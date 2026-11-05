"""Finalize review copies from the real workflow's selected native text patches."""
from pathlib import Path
from collections import Counter
import json
import os
import sys
import zipfile
import httpx
from lxml import etree
from patch_author_docx import patch
from workspace_interactions_fixture import login,ORIGIN

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'reports/真实写作验收'


def load(path):return json.loads(path.read_text(encoding='utf8'))


def main():
    sys.stdout.reconfigure(encoding='utf8');os.environ.setdefault('WORKBENCH_PROXY_JUMP','research-cluster-xh5')
    full=OUT/'水分扩散_实际工作流记录';summary=load(full/'run-summary.json')
    assert summary['status']=='completed' or (summary['stage']=='review' and (full/'parser-repair.json').exists())
    edits=[]
    for stage in ['narrow','wide']:
        for batch in load(full/(stage+'-edits.json'))['reports']:edits.extend(batch['accepted'])
    source=OUT/'水分扩散_原稿.docx';output=OUT/'水分扩散_第一轮小改候选.docx'
    result=patch(source,output,load(full/'baseline.json'),edits)
    assert result['saved'],result
    with zipfile.ZipFile(source) as original,zipfile.ZipFile(output) as candidate:
        assert original.namelist()==candidate.namelist()
        changed=[name for name in original.namelist() if original.read(name)!=candidate.read(name)]
        assert changed==['word/document.xml'],changed
        old=etree.fromstring(original.read('word/document.xml'));new=etree.fromstring(candidate.read('word/document.xml'))
    ns={'w':'http://schemas.openxmlformats.org/wordprocessingml/2006/main',
        'm':'http://schemas.openxmlformats.org/officeDocument/2006/math'}
    objects={}
    for name,xpath in [('equations','//m:oMath'),('drawings','//w:drawing'),('tables','//w:tbl'),('fields','//w:fldChar')]:
        left=old.xpath(xpath,namespaces=ns);right=new.xpath(xpath,namespaces=ns)
        assert len(left)==len(right),(name,len(left),len(right))
        if name!='tables':assert [etree.tostring(x) for x in left]==[etree.tostring(x) for x in right],name
        objects[name]=len(left)
    result.update(changed_package_parts=changed,preserved_word_objects=objects,author_approval='pending')
    (OUT/'水分扩散_Word保真检查.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
    (full/'accepted-word-patches.json').write_text(json.dumps(edits,ensure_ascii=False,indent=2),encoding='utf8')
    if '--full-only' in sys.argv:
        print(json.dumps({'moisture_docx':str(output),'word_check':result},ensure_ascii=False));return
    intro=load(OUT/'氯硫_实际工作流记录/run-summary.json');assert intro['status']=='completed'
    path=intro['outputs']['docx_path'].removeprefix('project/')
    with httpx.Client(base_url=ORIGIN,headers={'Origin':ORIGIN},proxy='http://127.0.0.1:12000',timeout=180,trust_env=False) as client:
        login(client);response=client.get('/research/api/projects/'+intro['project_id']+'/file',params={'path':path});response.raise_for_status()
    target=OUT/'氯硫_五段引言第一轮候选.docx';target.write_bytes(response.content)
    with zipfile.ZipFile(target) as z:assert 'word/document.xml' in z.namelist()
    print(json.dumps({'moisture_docx':str(output),'word_check':result,'introduction_docx':str(target)},ensure_ascii=False))


if __name__=='__main__':main()
