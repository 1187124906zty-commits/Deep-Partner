import asyncio
import json
import time
import sys
from pathlib import Path
sys.path.insert(0, "/app")
from deeptutor.services.model_selection.runtime import resolve_llm_config_for_selection
from deeptutor.services.llm.factory import complete_with_config

async def main():
    config = json.loads(Path('/migration/desktop-terra-configuration.json').read_text())
    choice = config['computer_model']
    selection = {k: choice[k] for k in ('profile_id','model_id')}
    llm = resolve_llm_config_for_selection(selection)
    start = time.monotonic()
    answer = await complete_with_config(config=llm, prompt='只回复：Terra电脑助手连接正常', system_prompt='你是桌面电脑操作助手。按要求简短回复。', max_tokens=128)
    report = {'model': llm.model, 'answer': answer, 'elapsed_seconds': round(time.monotonic()-start,2), 'passed': 'Terra' in answer}
    Path('/migration/desktop-terra-verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
    print(json.dumps(report,ensure_ascii=False))

asyncio.run(main())
