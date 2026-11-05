"""Prepare the author's requested folder through the packaged local tool; never apply."""
from pathlib import Path
from http.cookiejar import CookieJar
import json,os,subprocess,urllib.request,urllib.error,zipfile
ROOT=Path(__file__).resolve().parents[1]
NATIVE=Path('D:/Development/电脑答疑/deeptutor-desktop')
SOURCE=Path('D:/博士工作/博士项目/水分扩散/2026-11-2/网站项目')

def main():
    profile=NATIVE/'verification/import-prepare-profile';profile.mkdir(exist_ok=True)
    (profile/'config.json').write_text(json.dumps({'workspace':str(SOURCE),'bridge_port':19387}),encoding='utf8')
    child=subprocess.Popen([str(NATIVE/'dist/Deep partner.exe'),'--headless-ui'],
        env=dict(os.environ,DEEP_PARTNER_HOME=str(profile)),stdout=subprocess.PIPE,stderr=subprocess.PIPE,
        text=True,encoding='utf8',creationflags=0x08000000)
    try:
        line=child.stdout.readline()
        if not line:raise RuntimeError(child.stderr.read()[:800])
        info=json.loads(line);url=info['url'];origin=url.split('/desktop/bootstrap')[0]
        client=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(CookieJar()))
        client.open(url,timeout=15).read()
        payload={'name':'project_import','arguments':{'action':'prepare','source':str(SOURCE)}}
        try:
            response=client.open(urllib.request.Request(origin+'/desktop/tools',data=json.dumps(payload).encode(),
                headers={'Origin':origin,'Content-Type':'application/json'}),timeout=120)
        except urllib.error.HTTPError as error:raise RuntimeError(error.read().decode('utf8')) from error
        receipt=json.load(response)
        assert receipt['status']=='prepared' and receipt['applied'] is False,receipt
        with zipfile.ZipFile(receipt['bundle']) as bundle:
            names=bundle.namelist();meta=json.loads(bundle.read('workbench-import.json'))
            assert 'project/src/mois_net.py' in names or any(n.startswith('project/') and n.endswith('.py') for n in names)
            assert 'manuscript/main.json' in names
            assert not any(n.startswith('.workbench/') or n.endswith('.pkl') for n in names)
            assert meta['source_project_id']=='05a893386c09449d88366cf6dfdc825f'
            assert bundle.testzip() is None
            report={'passed':True,'applied':False,'source':str(SOURCE),'files':receipt['files'],
                'source_bytes':receipt['bytes'],'zip_bytes':Path(receipt['bundle']).stat().st_size,
                'main_manuscript_present':True,'programs_present':True,'runtime_objects_excluded':True,
                'unicode_paths_preserved':any('中文' in n for n in names),'package_version':info['version']}
        (ROOT/'reports/project-import-prepare.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
        print(json.dumps(report,ensure_ascii=False))
    finally:
        child.terminate();child.wait(timeout=10)
if __name__=='__main__':main()
