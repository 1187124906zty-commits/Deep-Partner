"""Locate an existing paired ScanSci device; never enroll or expose its token."""
from pathlib import Path
import hashlib,json,os,time
from runtime_connection import spawn,pid_alive,stop_owned

def discover():
    user=Path.home();path=Path(os.environ.get('CODEX_HOME',user/'.codex'))/'workbench-download/worker.json'
    if not path.is_file():return {'configured':False}
    value=json.loads(path.read_text(encoding='utf-8-sig'))
    python=Path('D:/Development/电脑答疑/scansci-pdf/.venv312/Scripts/python.exe')
    if not python.is_file():return {'configured':False,'reason':'Original ScanSci interpreter is unavailable'}
    return {'configured':True,'device_id':hashlib.sha256(value['token'].encode()).hexdigest(),'origin':value['origin'],
            'runtime':{'python':str(python),'device_config':str(path),'data_dir':str(user/'AppData/Local/ScanSciPDF')}}

def restore():
    selected=discover()
    if not selected.get('configured'):return {'ready':False,'requires_input':True,'reason':selected.get('reason','download_device_not_configured')}
    runtime=selected['runtime'];config_path=Path(runtime['device_config']);status_path=config_path.with_suffix('.status.json')
    def current():
        try:return json.loads(status_path.read_text(encoding='utf8'))
        except (OSError,ValueError):return {}
    status=current()
    if time.time()-status.get('heartbeat',0)<45 and pid_alive(status.get('pid')):
        if status.get('runtime_revision')=='automatic-recovery-1' or status.get('state')!='idle':
            result={'ready':status.get('state') in ('idle','working'),'state':status.get('state'),'pid':status.get('pid'),'reused':True,'runtime_revision':status.get('runtime_revision'),'upgrade_pending':not status.get('runtime_revision')}
            if not result['ready']:
                message=str(status.get('error','')).casefold();needs_input=status.get('state')=='waiting_input' or '401' in message or '403' in message
                result.update(reason='download_authentication_required' if needs_input else 'download_reconnecting',requires_input=needs_input,retryable=not needs_input)
            return result
        if not stop_owned(status['pid'],'download_worker.py'):
            return {'ready':False,'reason':'existing_download_worker_requires_review','requires_input':True}
    source=Path('D:/Development/电脑答疑/deeptutor-desktop/assets/download_worker.py')
    installed=Path(os.environ.get('LOCALAPPDATA',Path.home()/'AppData/Local'))/'DeepPartner/downloads/download_worker.py'
    script=source if source.is_file() else installed
    if not script.is_file():return {'ready':False,'reason':'download_worker_missing','requires_input':True}
    env=os.environ.copy();env['SCANSCI_PDF_DATA_DIR']=runtime['data_dir']
    process=spawn([runtime['python'],'-X','utf8','-u',str(script),'--config',str(config_path)],config_path.parent,'supervised-worker',env)
    (config_path.parent/'supervised-process.json').write_text(json.dumps({'pid':process.pid}),encoding='utf8')
    for _ in range(30):
        status=current()
        if time.time()-status.get('heartbeat',0)<45 and status.get('runtime_revision')=='automatic-recovery-1' and pid_alive(status.get('pid')):return {'ready':True,'state':status.get('state'),'pid':status.get('pid'),'reused':False,'runtime_revision':status['runtime_revision']}
        if process.poll() is not None:break
        time.sleep(.1)
    return {'ready':False,'reason':'download_worker_start_pending','retryable':True}

if __name__=='__main__':print(json.dumps(discover(),ensure_ascii=False))
