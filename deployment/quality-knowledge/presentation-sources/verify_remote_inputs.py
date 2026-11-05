"""Verify the uploaded private queue's relative files without external requests."""
from pathlib import Path
import json

root=Path(__file__).resolve().parent
queue=json.loads((root/'mineru-queue.json').read_text(encoding='utf8'))
rows=[]
for item in queue['items']:
    entry={'source_id':item['source_id'],'model_version':item['model_version']}
    for field in ('input_path','original_path'):
        path=(root/item[field]).resolve()
        if not path.is_relative_to(root) or not path.is_file():raise ValueError('Missing/outside source path: '+item[field])
        data=path.read_bytes()
        if not data:raise ValueError('Empty source: '+item[field])
        if path.suffix=='.pdf' and not data.startswith(b'%PDF-'):raise ValueError('Not PDF: '+item[field])
        entry[field]={'relative_path':item[field],'bytes':len(data),'readable':True}
    rows.append(entry)
report={'checked_items':len(rows),'all_inputs_and_originals_readable':True,'root':str(root),'items':rows}
(root/'remote-input-validation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
print(json.dumps({'checked_items':len(rows),'all_inputs_and_originals_readable':True,'source_ids':[x['source_id'] for x in rows]}))
