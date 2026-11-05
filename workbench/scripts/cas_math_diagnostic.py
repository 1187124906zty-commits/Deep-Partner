from pathlib import Path
import tempfile,shutil,subprocess,json
from server.journals import ROOT
import fitz
out=Path('/app/data/research-workbench/runtime-home/math-diagnostic');out.mkdir(parents=True,exist_ok=True)
for name in ['cas-dc.cls','cas-common.sty']:shutil.copyfile(ROOT/'templates/manuscripts/latex/cas'/name,out/name)
source=r'''\documentclass[a4paper,fleqn]{cas-dc}
\usepackage{xeCJK,unicode-math}
\setmainfont[Path=/usr/share/fonts/truetype/research-workbench/,BoldFont=STIX-Bold.otf]{STIX-Regular.otf}
\setmathfont[Path=/usr/share/fonts/truetype/research-workbench/]{STIXTwoMath-Regular.otf}
\setCJKmainfont[Path=/usr/share/fonts/truetype/research-workbench/]{simsun.ttc}
\begin{document}
\section{Formula font test}
\begin{equation}\frac{\partial H}{\partial t}=\nabla\cdot[D(H;\eta)\nabla H]+S_H,\quad q\in\mathbb{R},\quad -1<0.\tag{10}\end{equation}
中文编号：公式（10）；minus $-\nabla H$；member $q\in\mathcal Q_H$。
\end{document}
'''
(out/'math.tex').write_text(source)
r=subprocess.run(['/opt/workbench-tools/tectonic/tectonic','--untrusted','--keep-logs','--outdir',str(out),str(out/'math.tex')],cwd=out,capture_output=True,text=True,timeout=120)
print(r.returncode,r.stderr[-3000:])
if r.returncode==0:
 with fitz.open(out/'math.pdf') as d:
  print(d[0].get_text());d[0].get_pixmap(matrix=fitz.Matrix(2,2),alpha=False).save(out/'math.png')
