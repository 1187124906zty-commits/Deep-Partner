"""Install the official portable Tectonic binary in the existing tools mount."""
from pathlib import Path
import json,io,tarfile,urllib.request,zipfile
from deploy import remote

ROOT=Path(__file__).resolve().parents[1]
URL='https://assets.ctfassets.net/o78em1y1w4i4/4MpsJHO0MOJ2xZuwGTAbOZ/7bc64af36477c5d6cfce335a1f872363/elsarticle.zip'
def main():
    folder=ROOT/'templates/manuscripts/latex/elsevier';folder.mkdir(parents=True,exist_ok=True)
    with urllib.request.urlopen(URL,timeout=45) as response:data=response.read()
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        members=[]
        for name in archive.namelist():
            file=Path(name)
            if file.name in ('elsarticle.cls','elsarticle.dtx','elsarticle.ins','README','README.md','elsdoc.pdf') or file.suffix=='.bst':
                (folder/file.name).write_bytes(archive.read(name));members.append(file.name)
    if not (folder/'elsarticle.cls').is_file():
        original=(folder/'elsarticle.dtx').read_text(encoding='utf8')
        body=original.split('%<*class>',1)[1].split('%</class>',1)[0]
        license=(folder/'elsarticle.ins').read_text().split('\\preamble',1)[1].split('\\endpreamble',1)[0]
        (folder/'elsarticle.cls').write_text('%% Generated from the official elsarticle.dtx class guard.\n'+'\n'.join('%% '+line for line in license.splitlines())+'\n'+'\n'.join(line for line in body.splitlines() if not line.startswith('%'))+'\n',encoding='utf8')
        members.append('elsarticle.cls')
    (folder/'provenance.json').write_text(json.dumps({'publisher':'Elsevier','official_page':'https://www.elsevier.com/researcher/author/policies-and-guidelines/latex-instructions','download':URL,'files':members,'adaptation':'Official elsarticle 5p/twocolumn class. The workbench adds a draft header with the selected journal and never invents publication metadata.'},indent=2),encoding='utf8')
    code='''from pathlib import Path
import io,json,subprocess,tarfile,urllib.request,os
root=Path('/srv/research-workbench/tools/tectonic');root.mkdir(parents=True,exist_ok=True)
url='https://github.com/tectonic-typesetting/tectonic/releases/download/tectonic%400.17.0/tectonic-0.17.0-x86_64-unknown-linux-musl.tar.gz'
if not (root/'tectonic').is_file():
 with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'ResearchWorkbench/1.0'}),timeout=80) as response:data=response.read()
 with tarfile.open(fileobj=io.BytesIO(data),mode='r:gz') as archive:
  member=next(m for m in archive.getmembers() if Path(m.name).name=='tectonic' and m.isfile())
  (root/'tectonic').write_bytes(archive.extractfile(member).read())
 os.chmod(root/'tectonic',0o755)
version=subprocess.check_output([str(root/'tectonic'),'--version'],text=True).strip()
(root/'provenance.json').write_text(json.dumps({'version':version,'source':url}))
print(json.dumps({'installed':True,'version':version,'path':str(root/'tectonic')}))
'''
    print(remote(code,timeout=120,root=True))
    print('Official Elsevier template received')


if __name__=='__main__':main()
