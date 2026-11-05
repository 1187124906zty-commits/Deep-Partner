"""Reproduce the real workflow preparation logger contract without an LLM."""
import asyncio,logging,sys,tempfile
from pathlib import Path

sys.path.insert(0,'C:/Users/DEVELOPER/.codex/skills/deep-partner-research/scripts')
from deepcode_native import prepare
prepare()
from workflows.environment import prepare_workflow_environment

class StrictLog(logging.Handler):
    def emit(self,record):record.getMessage()

async def main():
    from loguru import logger
    bad=logging.getLogger('native-workflow-probe');bad.setLevel(logging.INFO);bad.addHandler(StrictLog())
    with tempfile.TemporaryDirectory() as d:
        root=Path(d);source=root/'source.md';source.write_text('Integration source')
        try:await prepare_workflow_environment(str(source),enable_indexing=False,task_id='bad',logger=bad,workspace_root=root/'bad')
        except TypeError as e:print('REPRODUCED:',str(e))
        else:raise AssertionError('Probe did not reach the original logger bug')
        result=await prepare_workflow_environment(str(source),enable_indexing=False,task_id='fixed',logger=logger,workspace_root=root/'fixed')
        assert result.task_dir.is_dir();print('FIXED: native preparation completes with kernel-compatible logger')

asyncio.run(main())
