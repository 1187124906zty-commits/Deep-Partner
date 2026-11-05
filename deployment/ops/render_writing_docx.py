"""Use the bundled DOCX renderer with existing LibreOffice and PyMuPDF rasterization.

The deployed research runtime has LibreOffice and PyMuPDF but no Poppler.
Only the renderer's PDF-to-PNG backend is supplied here; its DOCX conversion
and layout handling remain the bundled implementation.
"""
from pathlib import Path
import runpy
import sys
import types
import fitz


def pdfinfo_from_path(value,**kwargs):
    with fitz.open(value) as doc:
        rect=doc[0].rect
        return {'Pages':len(doc),'Page size':f'{rect.width} x {rect.height} pts'}


def convert_from_path(value,dpi=150,output_folder=None,output_file='page',paths_only=False,**kwargs):
    out=Path(output_folder);out.mkdir(exist_ok=True,parents=True);paths=[]
    with fitz.open(value) as doc:
        for i,page in enumerate(doc):
            path=out/f'{output_file}-{i+1}.png';page.get_pixmap(matrix=fitz.Matrix(dpi/72,dpi/72),alpha=False).save(path);paths.append(str(path))
    return paths


module=types.ModuleType('pdf2image');module.pdfinfo_from_path=pdfinfo_from_path;module.convert_from_path=convert_from_path
sys.modules['pdf2image']=module
renderer=Path('/opt/workbench-tools/documents-render_docx.py')
runpy.run_path(str(renderer),run_name='__main__')
