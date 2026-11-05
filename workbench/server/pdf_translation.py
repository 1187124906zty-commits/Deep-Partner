"""Export translations from PDF-native blocks while reusing original vector maths."""
from pathlib import Path
import json,re,subprocess,tempfile,shutil
from .storage import atomic_json,now


def translation_state(store,owner,pid,document_id):
    from .neoreader import engine,request_engine
    item=engine(store,owner,pid);mapping=json.loads((item['root'].parent/'neoread-map.json').read_text())
    entry=next((v for v in mapping.values() if v['document_id']==document_id),None)
    if not entry:raise ValueError('PDF不属于当前项目')
    analysis=item['root']/'cache'/document_id/'analysis';manifest=json.loads((analysis/'manifest.json').read_text())
    options=request_engine(item,'GET','/api/documents/'+document_id+'/translation-options');rows=request_engine(item,'GET','/api/documents/'+document_id+'/translations')
    translations={r['blockId']:r for r in rows if r['status']=='complete'}
    return entry,analysis,manifest,options,translations


def export_translation(store,owner,pid,document_id,columns=2,format='pdf',progress=None):
    from .journals import escape
    if progress:progress('read','正在读取原文版面与已完成译文')
    entry,analysis,manifest,options,translations=translation_state(store,owner,pid,document_id)
    if not translations:raise ValueError('当前语言还没有已完成的 PDF 译文')
    root=store.path(owner,pid);folder=root/'.workbench/pdf-translation'/document_id;folder.mkdir(parents=True,exist_ok=True)
    if progress:progress('layout','正在保留原文公式与图表版面')
    outputs=[];used=[];untranslated=[];target=options['targetLanguage']
    for b in manifest['blocks']:
        label=b['label']
        if label in ('header','footer','number','formula_number'):continue
        row=translations.get(b['id']);value=' '.join(s['target'] for s in row.get('sentences',[])) if row else b.get('protectedText',b.get('text',''))
        if b.get('image'):
            path=analysis/(b.get('vector') or b['image']);used.append(path)
            if label in ('display_formula','inline_formula'):
                outputs.append(r'\begin{center}\begin{adjustbox}{max width=\linewidth}\includegraphics{\detokenize{'+str(path)+r'}}\end{adjustbox}\end{center}')
            else:outputs.append(r'\begin{center}\includegraphics[width=\linewidth,height=.8\textheight,keepaspectratio]{\detokenize{'+str(path)+r'}}\end{center}')
            continue
        if not value.strip():continue
        if not row:untranslated.append(b['id'])
        tokens={p['token']:p for p in b.get('protected',[])};pieces=[];start=0
        for match in re.finditer(r'__WBM\d+__',value):
            pieces.append(escape(value[start:match.start()]));part=tokens.get(match[0])
            if part:
                path=analysis/(part.get('vector') or part['image']);used.append(path);height=min(2.4,max(.7,float(part.get('heightEm',1))))
                pieces.append(r'\raisebox{-.2ex}{\includegraphics[height='+str(round(height,2))+r'em]{\detokenize{'+str(path)+'}}}')
            start=match.end()
        pieces.append(escape(value[start:]));paragraph=''.join(pieces)
        if label in ('doc_title','paragraph_title'):paragraph=r'\subsection*{'+paragraph+'}'
        outputs.append(paragraph+'\n\n')
    font='/usr/share/fonts/truetype/research-workbench/'
    preamble=r'''\documentclass[10pt,__COLUMNS__]{article}
\usepackage{fontspec,xeCJK,graphicx,adjustbox,xurl,geometry}
\geometry{a4paper,left=18mm,right=18mm,top=18mm,bottom=20mm,columnsep=7mm}
\setmainfont[Path=__FONT__,BoldFont=timesbd.ttf,ItalicFont=timesi.ttf]{times.ttf}
\setCJKmainfont[Path=__FONT__,BoldFont=simhei.ttf]{simsun.ttc}
\setlength{\parskip}{4pt}\setlength{\parindent}{1em}
\begin{document}
'''
    tex=preamble.replace('__COLUMNS__','twocolumn' if columns==2 else 'onecolumn').replace('__FONT__',font)+''.join(outputs)+'\n'+r'\end{document}'
    source=folder/'translation.tex';source.write_text(tex,encoding='utf8')
    if progress:progress('compile','正在生成 PDF 译稿')
    engine=Path('/opt/workbench-tools/tectonic/tectonic');r=subprocess.run([str(engine),'--untrusted','--keep-logs','--outdir',str(folder),str(source)],cwd=folder,capture_output=True,text=True,timeout=180)
    (folder/'compile.txt').write_text(r.stdout+'\n'+r.stderr)
    pdf=folder/'translation.pdf'
    if r.returncode or not pdf.is_file():raise ValueError('PDF译文排版失败：'+r.stderr[-900:])
    import fitz
    with fitz.open(pdf) as d:pages=len(d)
    atomic_json(folder/'manifest.json',{'source_document':document_id,'source_revision':entry['revision'],'target_language':target,'columns':columns,'pages':pages,'completed':len(translations),'untranslated_blocks':untranslated,'vector_objects':len(used),'formula_policy':'original PDF vector','generated':now()})
    name=('英文' if target=='en' else '中文')+'PDF译文-'+('双栏' if columns==2 else '单栏')+'.pdf'
    if progress:progress('save','正在保存译稿与来源记录')
    path=root/'manuscript/exports'/name;store.replace(owner,pid,path,pdf.read_bytes(),'从原PDF版面与数学矢量生成译文')
    from urllib.parse import quote
    return {'url':'/research/api/projects/'+pid+'/download?area=manuscript&name='+quote(name),'name':name,'pages':pages,'columns':columns,'language':target,'untranslated':len(untranslated),'formula_policy':'original-vector'}


def install(app,store,pool,run_job):
    from fastapi import Depends
    from .native import actor
    @app.post('/research/api/projects/{pid}/pdf-translation/export')
    async def export(pid:str,payload:dict,user=Depends(actor)):
        owner=user['id'];store.get(owner,pid);document_id=str(payload.get('document_id',''));columns=int(payload.get('columns',2))
        if not re.fullmatch(r'[a-f0-9]{32}',document_id) or columns not in (1,2):raise ValueError('请选择PDF与译文栏数')
        jid=store.job(owner,pid,'pdf-translation-export',{'subject':store.manuscript(owner,pid)['title'],'document_id':document_id,'format':'pdf'});run_job(jid,lambda:export_translation(store,owner,pid,document_id,columns,progress=lambda step,message:store.set_job(jid,step=step,stage=message)));return {'job_id':jid}
