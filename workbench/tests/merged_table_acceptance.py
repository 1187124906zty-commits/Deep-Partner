"""Merged header rows retain their cell grid in real Word and PDF output."""
from pathlib import Path
from tempfile import TemporaryDirectory
from io import BytesIO
from copy import deepcopy
import json
import fitz
from docx import Document
from docx.oxml.ns import qn
from server.storage import Store
from server.cas_typesetting import table_header_rows
from server.manuscripts import export_manuscript

out=Path('/app/data/research-workbench/runtime-home/chinese-writing-example/check');out.mkdir(parents=True,exist_ok=True)
def cell(value,colspan=1,rowspan=1,header=False):
    return {'type':'tableHeader' if header else 'tableCell','attrs':{'colspan':colspan,'rowspan':rowspan},'content':[{'type':'paragraph','content':[{'type':'text','text':value}]}]}
rows=[
    [cell('模型',rowspan=2,header=True),cell('RMSE（%）',colspan=2,header=True),cell('决定系数',colspan=2,header=True)],
    [cell('训练集'),cell('测试集'),cell('训练集'),cell('测试集')],
    [cell('Mois-Net'),cell('1.87'),cell('3.24'),cell('0.990'),cell('0.955')],
    [cell('DNN'),cell('0.47'),cell('17.97'),cell('0.999'),cell('−0.372')],
]
table={'type':'table','content':[{'type':'tableRow','content':r} for r in rows]}
assert table_header_rows(table)==2
with TemporaryDirectory() as folder:
    store=Store(Path(folder));p=store.create('merged-header-qa','Merged header');root=store.path('merged-header-qa',p['id'])
    source={'title':'合并表头检查','template':'chinese-mechanics','columns':1,'revision':1,'comments':[],'content':{'type':'doc','content':[table]}}
    original=deepcopy(source);data,_,_=export_manuscript(root,source,'docx');(out/'merged-table.docx').write_bytes(data);word=Document(BytesIO(data))
    assert len(word.tables)==1
    t=word.tables[0];first=t.rows[0]._tr
    assert first.xpath('./w:tc/w:tcPr/w:vMerge[@w:val="restart"]'),'Vertical header merge lost'
    assert t.rows[1]._tr.xpath('./w:tc/w:tcPr/w:vMerge'),'Vertical header continuation lost'
    assert all(row._tr.find(qn('w:trPr')+'/'+qn('w:tblHeader')) is not None for row in t.rows[:2])
    data,_,_=export_manuscript(root,source,'pdf');(out/'merged-table.pdf').write_bytes(data)
    with fitz.open(stream=data,filetype='pdf') as pdf:
        assert len(pdf)==1,'Merged table flattened into a vertical text stream'
        page=pdf[0];spans=[s for b in page.get_text('dict')['blocks'] for l in b.get('lines',[]) for s in l['spans']]
        data_row=[next(s for s in spans if s['text'].strip()==text) for text in ['Mois-Net','1.87','3.24','0.990','0.955']]
        assert max(s['origin'][1] for s in data_row)-min(s['origin'][1] for s in data_row)<1,'A data row no longer shares one baseline'
        assert len({round(s['origin'][0]) for s in data_row})==5,'Table columns collapsed'
        page.get_pixmap(matrix=fitz.Matrix(1.5,1.5),alpha=False).save(out/'merged-table.png')
    assert source==original
    print(json.dumps({'passed':True,'header_rows':2,'columns':5,'pdf_pages':1,'data_row_preserved':True,'source_unchanged':True}))
