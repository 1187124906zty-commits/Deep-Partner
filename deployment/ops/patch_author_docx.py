"""Apply the accepted native text patches inside a copy of the author's DOCX.

All original package parts are retained. Only matched w:t text is changed;
equations, image objects, tables, styles, headers and citation fields stay native.
"""
from copy import deepcopy
from pathlib import Path
import json
import zipfile
from lxml import etree as ET

W='http://schemas.openxmlformats.org/wordprocessingml/2006/main'
NS={'w':W}


def plain(node):
    if node.get('type')=='text':return node.get('text','')
    if node.get('type')=='citation':return '['+str(node.get('attrs',{}).get('number','?'))+']'
    if node.get('type') in ('inlineMath','blockMath'):return ''
    return ''.join(plain(n) for n in node.get('content',[]))


def native_node(document,path):
    node=document['content']
    for index in path:node=node['content'][index]
    return node


def text_offset(node,path):
    offset=0
    for depth,index in enumerate(path):
        for sibling in node.get('content',[])[:index]:offset+=len(plain(sibling))
        node=node['content'][index]
    return offset


def replace_text(paragraph,start,end,replacement):
    parts=paragraph.xpath('.//w:t',namespaces=NS);offset=0;targets=[]
    for node in parts:
        value=node.text or '';left=offset;right=offset+len(value)
        if left<end and right>start:targets.append((node,left,right,value))
        offset=right
    if not targets:raise ValueError('未找到对应Word文本片段')
    first=targets[0];last=targets[-1]
    if len(targets)==1:first[0].text=first[3][:start-first[1]]+replacement+first[3][end-first[1]:]
    else:
        first[0].text=first[3][:start-first[1]]+replacement
        for node,_,_,_ in targets[1:-1]:node.text=''
        last[0].text=last[3][end-last[1]:]
    for node,_,_,_ in targets:node.set('{http://www.w3.org/XML/1998/namespace}space','preserve')


def patch(source,output,baseline,edits):
    with zipfile.ZipFile(source) as z:
        entries=[(info,z.read(info.filename)) for info in z.infolist()]
    document_data=next(data for info,data in entries if info.filename=='word/document.xml')
    tree=ET.fromstring(document_data);paragraphs=tree.xpath('//w:p',namespaces=NS)
    mapping={};native=deepcopy(baseline);accepted=[];unmapped=[]
    for edit in edits:
        try:
            pindex=edit['path'][0]
            if pindex not in mapping:
                base=plain(native['content']['content'][pindex])
                candidates=[p for p in paragraphs if ''.join(p.xpath('.//w:t/text()',namespaces=NS))==base]
                if len(candidates)!=1:raise ValueError('原稿段落不能唯一精确对应：'+str(len(candidates)))
                mapping[pindex]=candidates[0]
            paragraph=mapping[pindex];node=native_node(native,edit['path'])
            if node['text']!=edit['before']:raise ValueError('原文节点已变化')
            start=text_offset(native['content']['content'][pindex],edit['path'][1:]);end=start+len(edit['before'])
            actual=''.join(paragraph.xpath('.//w:t/text()',namespaces=NS))
            if actual[start:end]!=edit['before']:raise ValueError('Word文本位置与原文节点不一致')
            replace_text(paragraph,start,end,edit['after']);node['text']=edit['after'];accepted.append(edit)
        except (KeyError,ValueError,IndexError) as exc:unmapped.append({**edit,'error':str(exc)})
    if unmapped:return {'applied':len(accepted),'unmapped':unmapped,'saved':False}
    data=ET.tostring(tree,xml_declaration=True,encoding='UTF-8',standalone=True)
    with zipfile.ZipFile(output,'w',zipfile.ZIP_DEFLATED) as z:
        for info,original in entries:z.writestr(info,data if info.filename=='word/document.xml' else original)
    return {'applied':len(accepted),'unmapped':[],'saved':True,'all_other_package_parts_unchanged':True}


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('source');parser.add_argument('output');parser.add_argument('baseline');parser.add_argument('edits');args=parser.parse_args()
    result=patch(args.source,args.output,json.loads(Path(args.baseline).read_text(encoding='utf8')),json.loads(Path(args.edits).read_text(encoding='utf8')))
    Path(args.output+'.patch.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps(result,ensure_ascii=False));raise SystemExit(0 if result['saved'] else 1)
