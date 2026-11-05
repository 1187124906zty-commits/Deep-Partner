"""Print Writer's import of the reference fixture's mathematical structures."""
from pathlib import Path
from zipfile import ZipFile
import os,subprocess
from lxml import etree as ET

root=Path('/app/data/research-workbench/runtime-home/chinese-writing-example/check')
path=root/'fixture.docx'
with ZipFile(path) as z:
    tree=ET.fromstring(z.read('word/document.xml'))
    ns={'m':'http://schemas.openxmlformats.org/officeDocument/2006/math'}
    for math in tree.findall('.//m:oMath',ns):print('OFFICEMATH',ET.tostring(math,encoding='unicode')[-2600:])
worker=Path('/workbench/server/uno_pdf_worker.py').read_text()
worker=worker.replace('height=args.size',"print('IMPORTED',repr(model.Formula),flush=True);height=args.size")
script=root/'diagnostic-worker.py';script.write_text(worker)
p=subprocess.run(['/usr/bin/python3',str(script),str(path),str(root/'diagnostic.pdf'),'--profile',str(root/'diagnostic-profile'),'--font','Times New Roman','--math-font','Cambria Math','--size','10.5'],capture_output=True,text=True,timeout=120,env={**os.environ,'PYTHONPATH':'/workbench/server'})
print(p.stdout,p.stderr);assert p.returncode==0
