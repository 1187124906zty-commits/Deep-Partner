"""Build the requested upstream NeoRead server on the registered Slurm channel."""
from pathlib import Path
import json,subprocess,tarfile
from cluster_build import ROOT,REMOTE,SSH,SCP,remote

source=ROOT/'build/neoread-source/apps/server';archive=ROOT/'build/neoread-server-source.tar.gz'
with tarfile.open(archive,'w:gz') as tar:
    for path in source.rglob('*'):
        if path.is_file():tar.add(path,arcname=path.relative_to(source))
subprocess.run([SCP,'-q',str(archive),'research-cluster-xh5:'+REMOTE+'/neoread-server-source.tar.gz'],check=True,timeout=90)
go=json.loads((ROOT/'verification/go-source.json').read_text())
setup=f'''from pathlib import Path
import urllib.request,hashlib,tarfile,json
r=Path({REMOTE!r});src=r/'neoread-server';src.mkdir(exist_ok=True)
with tarfile.open(r/'neoread-server-source.tar.gz') as t:t.extractall(src,filter='data')
sdk=r/'tools/go/bin/go'
if not sdk.exists():
 p=r/'tools'/{go['filename']!r}
 with urllib.request.urlopen('https://go.dev/dl/'+{go['filename']!r},timeout=45) as response,p.open('wb') as out:
  while True:
   block=response.read(1024*1024)
   if not block:break
   out.write(block)
 assert hashlib.sha256(p.read_bytes()).hexdigest()=={go['sha256']!r},'Official SDK download integrity mismatch'
 with tarfile.open(p) as t:t.extractall(r/'tools',filter='data')
 p.unlink()
print('NeoRead source and official Go SDK ready')
'''
print(remote('/public/software/apps/anaconda3/2023.09/bin/python -',setup,timeout=120),flush=True)
job=f'''#!/bin/bash
#SBATCH --partition=xhacnormalb
#SBATCH --account=cluster_user
#SBATCH --qos=user_cluster_user
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=6G
#SBATCH --time=00:18:00
#SBATCH --output={REMOTE}/logs/neoread-%j.log
set -euo pipefail
export PATH={REMOTE}/tools/go/bin:$PATH
export GOCACHE={REMOTE}/tools/go-cache
export GOMODCACHE={REMOTE}/tools/go-modules
export GOPATH={REMOTE}/tools/go-work
export GOPROXY=https://goproxy.cn,direct
export GOTOOLCHAIN=local
export CGO_ENABLED=0
export GOMAXPROCS=4
cd {REMOTE}/neoread-server
go version
gofmt -w internal/neoread/translation_language.go internal/neoread/translation_language_test.go internal/neoread/translation.go internal/neoread/translation_source.go internal/neoread/translation_batch.go internal/neoread/translation_export.go internal/neoread/processing.go internal/neoread/formula.go internal/neoread/server.go internal/neoread/retranslation_layout.go
go test ./internal/neoread -run 'TestWorkbenchTranslationLanguage|TestWorkbenchProtectedMath|TestTranslationPromptAsksForKaTeXInlineMath|TestTranslationExportBundlesImagesAndPreservesFormulaAndCode'
go build -trimpath -ldflags='-s -w -X main.neoreadVersion=0.10.0-workbench -X main.buildCommit=ccfb94df9f477381daf1a6aee27f77f660daeebe' -o {REMOTE}/artifacts/neoread-server ./cmd/neoread-server
file {REMOTE}/artifacts/neoread-server
echo NEOREAD_SERVER_BUILD_PASSED
'''
print(remote('/public/software/apps/anaconda3/2023.09/bin/python -',f'from pathlib import Path\nPath({REMOTE!r}+"/neoread.sbatch").write_text({job!r})\n'),flush=True)
jid=remote('sbatch --parsable '+REMOTE+'/neoread.sbatch').strip().split(';')[0]
report={'job_id':jid,'state':'submitted','connection':'research-cluster-xh5','commit':'ccfb94df9f477381daf1a6aee27f77f660daeebe','source':REMOTE+'/neoread-server','binary':REMOTE+'/artifacts/neoread-server','log':REMOTE+'/logs/neoread-'+jid+'.log'}
(ROOT/'verification/neoread-build.json').write_text(json.dumps(report,indent=2),encoding='utf8');print(json.dumps(report),flush=True)
