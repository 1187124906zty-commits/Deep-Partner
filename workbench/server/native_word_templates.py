"""Reference styles copied from actual Word template paragraphs and sections."""
from copy import deepcopy
from pathlib import Path
import re


def make_reference(folder,spec,columns):
    from docx import Document
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    from .storage import atomic_json
    source=Path(__file__).resolve().parents[1]/'templates/manuscripts/source'/spec['source_file']
    folder=Path(folder);folder.mkdir(parents=True,exist_ok=True);path=folder/(spec['id']+'.docx');stamp=path.with_suffix('.json')
    version={'native_reference_version':3,'source_modified':source.stat().st_mtime_ns,'source_bytes':source.stat().st_size,'columns':columns}
    if path.exists() and stamp.exists() and __import__('json').loads(stamp.read_text())==version:return path
    doc=Document(source);paragraphs=list(doc.paragraphs);chinese=spec['language']=='zh-CN'
    def find(pattern,default=0):return next((i for i,p in enumerate(paragraphs) if re.search(pattern,p.text,re.I)),default)
    body_index=find(r'请注重引言') if chinese else find(r'^An Introduction should')
    reference_heading=find(r'^参考文献[（(]')
    samples={'Title':0 if chinese else find(r'^The Title Should'),'Authors':1 if chinese else find(r'^List all authors'),'Affiliation':2 if chinese else find(r'^a Please clearly'),'Abstract':find(r'^摘要') if chinese else find(r'^A concise and factual Abstract'),'Normal':find(r'请注重引言') if chinese else find(r'^An Introduction should'),'Heading 1':find(r'^1 稿件选用要求') if chinese else find(r'^Introduction$'),'Heading 2':find(r'^1\.1 论文清稿') if chinese else find(r'^Materials and methods$'),'Heading 3':find(r'^1\.\d\.\d',body_index) if chinese else find(r'^Materials and methods$'),'Caption':find(r'^图\s*1',body_index) if chinese else find(r'^Fig(?:ure)?\.?\s*1',body_index),'Table Caption':find(r'^表\s*1',body_index) if chinese else find(r'^Table\s*1',body_index),'Bibliography':reference_heading+1 if chinese else body_index}
    defaults=doc.styles.element.find(qn('w:docDefaults'))
    excluded={qn('w:'+tag) for tag in ('sectPr','numPr','pStyle','rPr','vertAlign','rStyle','footnoteReference')}
    def merged_property(prototype,tag):
        merged=OxmlElement('w:'+tag)
        def add(original):
            if original is None:return
            for child in original:
                if child.tag in excluded:continue
                old=merged.find(child.tag)
                if child.tag==qn('w:rFonts') and old is not None:old.attrib.update(child.attrib)
                else:
                    if old is not None:merged.remove(old)
                    merged.append(deepcopy(child))
        if defaults is not None:add(defaults.find(qn('w:'+tag+'Default')+'/'+qn('w:'+tag)))
        chain=[];ancestor=prototype.style
        while ancestor is not None:
            chain.append(ancestor);ancestor=ancestor.base_style
        if not any(style.style_id==doc.styles['Normal'].style_id for style in chain):chain.append(doc.styles['Normal'])
        for style in reversed(chain):add(style.element.find(qn('w:'+tag)))
        paragraph_properties=prototype._p.find(qn('w:pPr'))
        if tag=='pPr':add(paragraph_properties)
        else:
            if paragraph_properties is not None:add(paragraph_properties.find(qn('w:rPr')))
            sample=max((run for run in prototype.runs if run.text.strip()),key=lambda run:len(run.text),default=None)
            if sample is not None:add(sample._r.rPr)
            # Explicitly materialize source defaults so an unrelated target
            # Heading/Title style cannot supply its theme color or font.
            fonts=merged.find(qn('w:rFonts'))
            if fonts is not None:
                for literal,theme in (('ascii','asciiTheme'),('hAnsi','hAnsiTheme'),('eastAsia','eastAsiaTheme'),('cs','cstheme')):
                    if fonts.get(qn('w:'+literal)):fonts.attrib.pop(qn('w:'+theme),None)
            if merged.find(qn('w:color')) is None:
                color=OxmlElement('w:color');color.set(qn('w:val'),'auto');merged.append(color)
        return merged
    # Resolve every prototype before mutating the shared source Normal style.
    captured={name:{tag:merged_property(paragraphs[index],tag) for tag in ('pPr','rPr')} for name,index in samples.items()}
    for name,properties in captured.items():
        style=doc.styles[name] if name in doc.styles else doc.styles.add_style(name,1)
        style.base_style=None
        for tag,merged in properties.items():
            current=style.element.find(qn('w:'+tag))
            if current is not None:style.element.remove(current)
            style.element.append(merged)
    for name in ('Body Text','First Paragraph'):
        target=doc.styles[name] if name in doc.styles else doc.styles.add_style(name,1)
        target.base_style=doc.styles['Normal']
        for tag in ('pPr','rPr'):
            old=target.element.find(qn('w:'+tag))
            if old is not None:target.element.remove(old)
    sections=list(doc.sections)
    selected=next((i for i,s in enumerate(sections) if s._sectPr.find(qn('w:cols')) is not None and s._sectPr.find(qn('w:cols')).get(qn('w:num'))=='2'),1 if len(sections)>1 else 0) if chinese else next((i for i,s in enumerate(sections) if s._sectPr.find(qn('w:lnNumType')) is not None),0)
    section=deepcopy(sections[selected]._sectPr)
    for tag in ('headerReference','footerReference'):
        inherited={}
        for prior in sections[:selected+1]:
            for ref in prior._sectPr.findall(qn('w:'+tag)):inherited[ref.get(qn('w:type'))]=ref
        for ref in section.findall(qn('w:'+tag)):section.remove(ref)
        if chinese:
            for ref in sections[0]._sectPr.findall(qn('w:'+tag)):
                if ref.get(qn('w:type'))=='first':inherited['first']=ref
        for ref in inherited.values():section.insert(0,deepcopy(ref))
    for item in list(doc._element.body):doc._element.body.remove(item)
    doc._element.body.append(section)
    doc.add_paragraph('Reference styles only');doc.save(path);atomic_json(stamp,version);return path
