"""Restore the existing local Scholar MCP bridge/tunnel only when a search needs it."""
from pathlib import Path
import json,os,subprocess,time,urllib.request
from runtime_connection import ensure_tunnel,spawn

ROOT=Path(os.environ.get('CODEX_HOME',Path.home()/'.codex'))/'workbench-search'
SOURCE=Path('D:/Development/research-workbench')
def restore():
    path=ROOT/'bridge.json'
    if not path.is_file():return {'ready':False,'reason':'scholar_not_configured','requires_input':True}
    config=json.loads(path.read_text(encoding='utf-8-sig'));port=int(config.get('port',47903))
    if not Path(config['python']).is_file():
        original=SOURCE/'search-tools/scholar-env/Scripts/python.exe'
        if not original.is_file():return {'ready':False,'reason':'interpreter_missing','requires_input':True}
        config['python']=str(original);path.write_text(json.dumps(config,ensure_ascii=False),encoding='utf8')
    def healthy():
        try:
            opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
            with opener.open(f'http://127.0.0.1:{port}/health',timeout=2) as response:return json.load(response).get('source')=='Google Scholar · MCP'
        except (OSError,ValueError):return False
    if not healthy():
        process=spawn([config['python'],'-X','utf8',str(SOURCE/'scripts/local_search_bridge.py'),'--config',str(path)],ROOT,'bridge')
        (ROOT/'bridge-process.json').write_text(json.dumps({'pid':process.pid}),encoding='utf8')
        for _ in range(20):
            if healthy():break
            time.sleep(.1)
    if not healthy():return {'ready':False,'reason':'Local Scholar bridge did not start'}
    return {**ensure_tunnel(ROOT,port),'local_ready':True}

if __name__=='__main__':print(json.dumps(restore(),ensure_ascii=False))
