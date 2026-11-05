"""Signal one test-owned child; do not launch a model or touch real tasks."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile

spec=importlib.util.spec_from_file_location('worker_cancel_check','/opt/coder_service.py')
worker=importlib.util.module_from_spec(spec);spec.loader.exec_module(worker)
with tempfile.TemporaryDirectory(prefix='coder-cancel-check-') as directory:
    worker.STATE=Path(directory)
    value=worker.enqueue({'task':'Cancellation transport check','project':'test','mode':'plan'})
    tid=value['id']
    process=subprocess.Popen([sys.executable,'-c','import time;time.sleep(120)'],start_new_session=True)
    worker.RUNNING[tid]=process
    with worker.db() as conn:conn.execute("UPDATE tasks SET status='running' WHERE id=?",(tid,))
    result=worker.cancel_task(tid)
    code=process.wait(timeout=5)
    with worker.db() as conn:status=conn.execute('SELECT status FROM tasks WHERE id=?',(tid,)).fetchone()['status']
    assert result['cancelled'] and status=='cancelled' and code!=0
    output={'test_owned_process_terminated':True,'status':status,'exit_code':code,'verified':True}
    print(json.dumps(output))
