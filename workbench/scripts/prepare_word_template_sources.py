"""Change only journal names in retained original OOXML template copies."""
from pathlib import Path
import json,re,zipfile
from lxml import etree as E
ROOT=Path(__file__).resolve().parents[1]/'templates/manuscripts/source'
NS={'w':'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
PATTERNS=[(r'力\s*学\s*学\s*报','中文期刊'),(r'Chinese Journal of Theoretical and Applied Mechanics','Journal template'),(r'CHINESE JOURNAL OF THEORETICAL AND APPLIED MECHANICS','Journal template'),(r'Computers\s+and\s+Electronics\s+in\s+Agriculture','Journal template'),(r'Computers\s*&\s*Electronics\s*in\s*Agriculture','Journal template'),(r'COMPAG','Journal template')]


def replace_paragraph(paragraph):
    nodes=paragraph.findall('.//w:t',NS);text=''.join(n.text or '' for n in nodes);changes=0
    for pattern,replacement in PATTERNS:
        for match in reversed(list(re.finditer(pattern,text,re.I))):
            offsets=[];at=0
            for node in nodes:offsets.append((at,at+len(node.text or ''),node));at=offsets[-1][1]
            touched=[(a,b,n) for a,b,n in offsets if a<match.end() and b>match.start()]
            for i,(a,b,node) in enumerate(touched):
                value=node.text or '';left=max(0,match.start()-a);right=min(len(value),match.end()-a)
                node.text=value[:left]+(replacement if i==0 else '')+value[right:]
            changes+=1;text=''.join(n.text or '' for n in nodes)
    return changes


def prepare(original,target):
    changed=[];edits=0
    with zipfile.ZipFile(ROOT/original) as source,zipfile.ZipFile(ROOT/target,'w',zipfile.ZIP_DEFLATED) as output:
        for info in source.infolist():
            data=source.read(info.filename)
            if info.filename.startswith('word/') and info.filename.endswith('.xml'):
                xml=E.fromstring(data);count=sum(replace_paragraph(p) for p in xml.findall('.//w:p',NS))
                if count:data=E.tostring(xml,xml_declaration=True,encoding='UTF-8',standalone=True);changed.append(info.filename);edits+=count
            output.writestr(info,data)
    return {'original':original,'copy':target,'changed_parts':changed,'journal_name_replacements':edits,'other_package_members_unchanged':True}


if __name__=='__main__':
    report=[prepare('chinese-journal-original.docx','chinese-journal.docx'),prepare('elsevier-research-original.docx','elsevier-research.docx')]
    (ROOT/'neutral-template-provenance.json').write_text(json.dumps({'copies':report,'english_source':'https://legacyfileshare.elsevier.com/promis_misc/Research%20Article%20template%20and%20guidance.docx','chinese_source':'User-provided 力学学报模版.doc','changes':'Journal names only; source styles, sections, drawings, equations and instructions retained.'},ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps(report,ensure_ascii=False))
