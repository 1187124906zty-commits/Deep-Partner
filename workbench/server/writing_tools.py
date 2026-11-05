"""Source tools for the four interfaces in 1111.pdf.

GROBID TEI, existing page-anchored Markdown, Crossref, SciPy and Pint are
adapters behind these functions; the writing roles own their interpretation.
"""
from __future__ import annotations
from collections import Counter
from pathlib import Path
import json
import os
import re
import statistics
import sys
import xml.etree.ElementTree as ET
import httpx
from .storage import child

if Path('/opt/workbench-tools/writing-libs').is_dir():sys.path.insert(0,'/opt/workbench-tools/writing-libs')

GROBID_URL = os.environ.get('WRITING_GROBID_URL', 'https://grobidorg-grobid.hf.space').rstrip('/')
TOOL_SOURCES = [
    {'name':'GROBID','role':'论文章节、段落、引用、公式与图表结构','url':'https://github.com/grobidOrg/grobid'},
    {'name':'Crossref REST API','role':'期刊身份、ISSN及已发表论文题录','url':'https://www.crossref.org/documentation/retrieve-metadata/rest-api/'},
    {'name':'OpenAlex Sources API','role':'期刊身份与主页','url':'https://help.openalex.org/api/endpoints/'},
    {'name':'SciPy','role':'数据统计与置信区间计算','url':'https://docs.scipy.org/doc/scipy/reference/stats.html'},
    {'name':'Pint','role':'量纲与单位解析','url':'https://pint.readthedocs.io/'},
]


def parse_tei(xml, source):
    root=ET.fromstring(xml);ns={'t':'http://www.tei-c.org/ns/1.0'}
    text=lambda n:' '.join(''.join(n.itertext()).split())
    paragraphs=[]
    for n in root.findall('.//t:text//t:p',ns):
        value=text(n)
        if value:paragraphs.append({'text':value,'source':source,'locator':{'paragraph':len(paragraphs)+1},
            'citation_count':len(n.findall('.//t:ref[@type="bibr"]',ns))})
    return {'engine':'GROBID','source':source,'title':next((text(n) for n in root.findall('.//t:titleStmt/t:title',ns)),''),
        'headings':[text(n) for n in root.findall('.//t:text//t:head',ns)],'paragraphs':paragraphs,
        'formulas':[text(n) for n in root.findall('.//t:formula',ns)],
        'figure_count':len(root.findall('.//t:figure',ns)),
        'references':[text(n) for n in root.findall('.//t:listBibl/t:biblStruct',ns)]}


def structure(root:Path, relative:str):
    path=child(root,relative)
    if not path.is_file():raise ValueError('标杆文件不存在：'+relative)
    cache=root/'.workbench/writing/structure-cache'/(path.stem+'.json')
    signature={'source':relative,'bytes':path.stat().st_size,'modified_ns':path.stat().st_mtime_ns}
    if cache.is_file():
        saved=json.loads(cache.read_text(encoding='utf8'))
        if saved.get('signature')==signature:return saved['result']
    def finish(result):
        cache.parent.mkdir(parents=True,exist_ok=True)
        cache.write_text(json.dumps({'signature':signature,'result':result},ensure_ascii=False),encoding='utf8')
        return result
    if path.suffix.lower()=='.pdf':
        try:
            with httpx.Client(timeout=180,trust_env=False) as client, path.open('rb') as pdf:
                r=client.post(GROBID_URL+'/api/processFulltextDocument',files={'input':(path.name,pdf,'application/pdf')},
                    data={'consolidateHeader':'0','consolidateCitations':'0','segmentSentences':'1','includeRawCitations':'1'})
                r.raise_for_status();result=parse_tei(r.text,relative)
                if result['paragraphs']:return finish(result)
                error='GROBID未返回可用段落'
        except (httpx.HTTPError,ET.ParseError,ValueError) as exc:
            error=type(exc).__name__+': '+str(exc)[:220]
        import fitz
        paragraphs=[]
        with fitz.open(path) as pdf:
            for i,page in enumerate(pdf):
                for block in page.get_text('blocks'):
                    value=str(block[4]).strip()
                    if value:paragraphs.append({'text':value,'source':relative,'locator':{'page':i+1,'block':len(paragraphs)+1}})
        return finish({'engine':'PyMuPDF','source':relative,'paragraphs':paragraphs,'headings':[],
                'grobid_status':error,'formula_count':None,'figure_count':None,'references':[]})
    text=path.read_text(encoding='utf-8',errors='replace')
    values=[];page=1
    for n,part in enumerate(re.split(r'\n\s*\n',text)):
        found=re.search(r'(?:PDF page|page-)(\d+)',part,re.I)
        if found:page=int(found[1])
        if part.strip():values.append({'text':part.strip(),'source':relative,'locator':{'paragraph':n+1,'page':page}})
    return finish({'engine':'page-anchored Markdown','source':relative,'paragraphs':values,
            'headings':re.findall(r'^#{1,5}\s+(.+)',text,re.M),'references':[]})


def exemplar_structural_deconstructor(root, exemplar_document_ids, journal_guideline_text=''):
    documents=[structure(root,p) for p in exemplar_document_ids]
    for d in documents:
        lengths=[len(p['text'].split()) for p in d['paragraphs']]
        d['paragraph_statistics']={'count':len(lengths),'mean_words':statistics.mean(lengths) if lengths else 0,
                                   'citation_count':sum(p.get('citation_count',0) for p in d['paragraphs'])}
    return {'journal_guideline_text':journal_guideline_text,'documents':documents,'tool_sources':TOOL_SOURCES[:1]}


def comparative_metric_calculator(root, data_source_id, target_metric, reference_baseline='', control_condition='', reference_column=''):
    import pandas as pd
    import numpy as np
    from scipy import stats
    path=child(root,data_source_id)
    frame=pd.read_csv(path,sep='\t' if path.suffix.lower()=='.tsv' else ',')
    if target_metric not in frame:raise ValueError('数据表没有指标列：'+target_metric)
    numbers=pd.to_numeric(frame[target_metric],errors='coerce').dropna().to_numpy(dtype=float)
    numbers=numbers[np.isfinite(numbers)]
    if not len(numbers):raise ValueError('指标列没有有限数值')
    result={'data_source_id':data_source_id,'target_metric':target_metric,'reference_baseline':reference_baseline,
        'control_condition':control_condition,'n':len(numbers),'mean':float(numbers.mean()),'min':float(numbers.min()),
        'max':float(numbers.max()),'engine':'pandas + NumPy + SciPy'}
    if len(numbers)>1:
        sem=float(stats.sem(numbers))
        interval=(float(numbers.mean()),float(numbers.mean())) if sem==0 else stats.t.interval(.95,len(numbers)-1,loc=numbers.mean(),scale=sem)
        result.update(std=float(np.std(numbers,ddof=1)),confidence_interval_mean_95=list(map(float,interval)))
    if reference_column:
        if reference_column not in frame:raise ValueError('数据表没有参照列：'+reference_column)
        pair=frame[[target_metric,reference_column]].apply(pd.to_numeric,errors='coerce').dropna()
        predicted=pair[target_metric].to_numpy(dtype=float);reference=pair[reference_column].to_numpy(dtype=float)
        finite=np.isfinite(predicted)&np.isfinite(reference);predicted=predicted[finite];reference=reference[finite]
        if not len(reference):raise ValueError('没有可配对比较的数据')
        error=predicted-reference;denom=float(np.linalg.norm(reference))
        result.update(paired_n=len(reference),rmse=float(np.sqrt(np.mean(error**2))),mae=float(np.mean(np.abs(error))),
                      relative_l2=float(np.linalg.norm(error)/denom) if denom else None,
                      reference_column=reference_column)
    return result


def intrinsic_scientific_rigor_auditor(assets, declarations=None):
    from pint import UnitRegistry
    units=UnitRegistry();declarations=declarations or {}
    checks=[]
    for item in declarations.get('quantities',[]):
        try:dim=str(units.parse_units(item['unit']).dimensionality);status='parsed'
        except Exception as exc:dim=str(exc);status='invalid'
        checks.append({'symbol':item.get('symbol'),'unit':item.get('unit'),'dimensions':dim,'status':status})
    roles={
        'LOCK_1_ASSUMPTION_JUSTIFICATION':r'假设|边界|assum|boundary',
        'LOCK_2_VARIABLE_DECOUPLING':r'消融|对照|控制变量|ablation|control|decoupl',
        'LOCK_3_CONVERGENCE_AND_SCALE':r'收敛|网格|敏感|converg|mesh|sensitiv',
        'LOCK_4_BENCHMARK_VALIDATION':r'验证|基准|解析|实验|benchmark|validat|analytic|experiment'}
    return {'engine':'Pint + source inventory','unit_checks':checks,'evidence_candidates':{
        name:[{'path':a['path'],'excerpt':a.get('text','')[:1800]} for a in assets
              if re.search(pattern,a['path']+' '+a.get('text','')[:6000],re.I)] for name,pattern in roles.items()},
        'asset_count':len(assets),'tool_sources':TOOL_SOURCES[4:]}


def rhetorical_alignment_inspector(draft_segment, genome, macro_slot='FULL_PAPER'):
    paragraphs=[p for p in re.split(r'\n\s*\n',draft_segment) if p.strip()]
    body=re.split(r'(?im)^#{1,6}\s*(?:参考文献|References|Bibliography)\s*$',draft_segment,maxsplit=1)[0]
    prose=[p.strip() for p in re.split(r'\n\s*\n',body) if p.strip() and not p.lstrip().startswith('#')]
    def ending(value):
        sentences=[s.strip() for s in re.split(r'(?<=[。！？!?])\s*|(?<=\.)\s+(?=[A-Z])',value) if s.strip()]
        return sentences[-1] if sentences else value
    windows=[{'paragraph':i+1,'text':value,'ending':ending(value),
              'next_paragraph':prose[i+1] if i+1<len(prose) else '',
              'instruction':'原文相邻窗口；判断群体综合、科学立场与承接需实际阅读，不按词形或篇数自动评分'}
             for i,value in enumerate(prose)]
    openers=[' '.join(re.sub(r'^[#*\s]+','',p).split()[:4]) for p in paragraphs]
    counts=Counter(openers)
    return {'macro_slot':macro_slot,'paragraph_count':len(paragraphs),
        'repeated_openers':[{'opener':k,'count':n} for k,n in counts.items() if n>1],
        'paragraph_lengths':[len(p) for p in paragraphs],
        'journal_profile':genome.get('journal_profile',{}),
        'native_expression_bank':genome.get('native_expression_bank',{}),
        'argument_windows':windows,
        'inspection_targets':['因果过渡','总体方案与模块分工','中观粒度','固有属性与算例解耦','领域搭配','功过平衡批评','研究群体的共同认识及条件','段尾判断与下一段承接','问题与本文方法回应']}
