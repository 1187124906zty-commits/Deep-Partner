"""Exact desktop PDF chunk URL regression without model calls or user data."""
from pathlib import Path
from http.cookiejar import CookieJar
import json,os,subprocess,urllib.request,urllib.error

ROOT=Path(__file__).resolve().parents[1]
NATIVE=Path('D:/Development/电脑答疑/deeptutor-desktop')
def main():
    profile=NATIVE/'verification/reader-route-profile';profile.mkdir(exist_ok=True)
    env=dict(os.environ,DEEP_PARTNER_HOME=str(profile))
    child=subprocess.Popen([str(NATIVE/'dist/Deep partner.exe'),'--headless-ui'],env=env,
        stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,encoding='utf8',creationflags=0x08000000)
    try:
        info=json.loads(child.stdout.readline());url=info['url'];origin=url.split('/desktop/bootstrap')[0]
        client=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(CookieJar()))
        client.open(url,timeout=15).read()
        account=json.loads(subprocess.run(['ssh','-o','BatchMode=yes','papers-research','sudo -n cat /srv/deeptutor/migration/admin-login.json'],capture_output=True,text=True,check=True).stdout)
        client.open(urllib.request.Request(origin+'/api/auth/login',data=json.dumps(account).encode(),headers={'Origin':origin,'Content-Type':'application/json'}),timeout=25).read()
        route='/research/reader/c0b9c547b07c401aa7fc7454b0104345/assets/pdf-B0s6D7Gr.js'
        try:
            response=client.open(urllib.request.Request(origin+route,headers={'Origin':origin}),timeout=30)
            status=response.status;mime=response.headers.get('Content-Type','');data=response.read()
        except urllib.error.HTTPError as error:
            status=error.code;mime=error.headers.get('Content-Type','');data=error.read()
        report={'path':route,'status':status,'mime':mime,'bytes':len(data),
            'javascript':status==200 and ('javascript' in mime or 'ecmascript' in mime),
            'html_instead_of_module':b'<!doctype html>' in data[:100].lower()}
        (ROOT/'reports/reader-module-regression.json').write_text(json.dumps(report,indent=2),encoding='utf8')
        print(json.dumps(report))
        assert report['javascript'],'Desktop reader module is not delivered as JavaScript'
    finally:
        child.terminate();child.wait(timeout=10)
if __name__=='__main__':main()
