"""Project OfficeMath run styles into Writer's formula import without data edits."""
from pathlib import Path
from zipfile import ZipFile,ZIP_DEFLATED
from xml.dom import minidom
import re,unicodedata
M='http://schemas.openxmlformats.org/officeDocument/2006/math'


def mathematical_alphabet(value,alphabet,bold=False):
    """Use the same mathematical glyph when Writer discards an OMath script."""
    holes={'script':dict(zip('BEFHILMRego','ℬℰℱℋℐℒℳℛℯℊℴ')),
           'double-struck':dict(zip('CHNPQRZ','ℂℍℕℙℚℝℤ'))}
    family='BOLD SCRIPT' if alphabet=='script' and bold else alphabet.upper()
    result=[]
    for char in value:
        if char.isascii() and char.isalpha():
            name='MATHEMATICAL '+family+(' CAPITAL ' if char.isupper() else ' SMALL ')+char.upper()
            try:char=unicodedata.lookup(name)
            except KeyError:char=holes.get(alphabet,{}).get(char,char)
        result.append(char)
    return ''.join(result)


def run_style(run):
    if run.namespaceURI!=M or run.localName!='r':return None
    properties=run.getElementsByTagNameNS(M,'rPr')
    if not properties:return None
    props=properties[0];styles=props.getElementsByTagNameNS(M,'sty');normal=bool(props.getElementsByTagNameNS(M,'nor'))
    script=props.getElementsByTagNameNS(M,'scr')
    alphabet=script[0].getAttributeNS(M,'val') if script else ''
    if alphabet not in ('roman','','script','double-struck'):return None
    style=styles[0].getAttributeNS(M,'val') if styles else 'p' if normal else ''
    value=''.join(t.firstChild.nodeValue if t.firstChild else '' for t in run.getElementsByTagNameNS(M,'t'))
    if alphabet in ('script','double-struck'):
        return 'p',alphabet,False,mathematical_alphabet(value,alphabet,style in ('b','bi'))
    if style not in ('p','b','bi'):return None
    if not value or style=='p' and not re.search(r'[A-Za-z\u0370-\u03ff\u4e00-\u9fff]',value):return None
    return style,normal,bool(re.search(r'[\u4e00-\u9fff]',value)),value


def prepare_math_styles(source,target):
    """Use temporary literal markers; the delivered source DOCX stays intact."""
    styles={}
    with ZipFile(source) as archive:
        tree=minidom.parseString(archive.read('word/document.xml'))
        for parent in list(tree.getElementsByTagName('*')):
            if parent.namespaceURI==M and parent.localName=='fName':continue
            runs=[n for n in parent.childNodes if n.nodeType==n.ELEMENT_NODE];i=0
            while i<len(runs):
                first=runs[i];style=run_style(first)
                if style is None:i+=1;continue
                merged=[first];value=style[3];j=i+1
                while j<len(runs):
                    following=run_style(runs[j])
                    if following is None or following[:3]!=style[:3]:break
                    merged.append(runs[j]);value+=following[3];j+=1
                n=len(styles);letters=''
                while True:
                    letters=chr(97+n%26)+letters;n=n//26-1
                    if n<0:break
                marker='wbmathstyle'+letters;styles[marker]={'style':style[0],'cjk':style[2],'text':value}
                texts=first.getElementsByTagNameNS(M,'t');text=texts[0]
                while text.firstChild:text.removeChild(text.firstChild)
                text.appendChild(tree.createTextNode(marker))
                for extra in list(texts)[1:]:extra.parentNode.removeChild(extra)
                for extra in merged[1:]:parent.removeChild(extra)
                i=j
        encoded=tree.toxml(encoding='utf-8')
        with ZipFile(target,'w',compression=ZIP_DEFLATED) as output:
            for name in archive.namelist():output.writestr(name,encoded if name=='word/document.xml' else archive.read(name))
    return styles


def restore_math_styles(formula,styles):
    count=0
    for marker,style in styles.items():
        if not re.search(r'\b'+re.escape(marker)+r'\b',formula):continue
        value=style['text'].replace('\\',' ').replace('"',r'\"').replace('\n',' ')
        commands=('' if style['cjk'] else 'font serif ')+('bold ' if style['style'] in ('b','bi') else '')+('italic ' if style['style']=='bi' else 'nitalic ')
        formula=re.sub(r'"'+re.escape(marker)+r'"|\b'+re.escape(marker)+r'\b',lambda m:'{ '+commands+'{ "'+value+'" } }',formula);count+=1
    return formula,count
