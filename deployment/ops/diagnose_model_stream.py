"""Probe the configured Tutor provider without changing a research session."""
from pathlib import Path
import json
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]

REMOTE_PROBE = r'''
import asyncio, json, time
from deeptutor.services.llm.config import get_llm_config
from deeptutor.services.llm.provider_factory import build_isolated_provider

async def main():
    config = get_llm_config()
    provider = build_isolated_provider(config)
    start = time.monotonic()
    report = {'model': config.model, 'reasoning_effort': config.reasoning_effort,
              'api_format': config.api_format, 'endpoint': config.effective_url,
              'provider_class': type(provider).__name__, 'deltas': [],
              'prompt': 'Reply with exactly MODEL_CONNECTION_OK. Do not use tools.'}
    async def delta(text):
        if text and len(report['deltas']) < 5:
            report['deltas'].append({'seconds': round(time.monotonic()-start, 3), 'chars': len(text)})
    try:
        response = await asyncio.wait_for(provider.chat_stream(
            messages=[{'role': 'user', 'content': report['prompt']}],
            model=config.model, max_tokens=512, reasoning_effort=config.reasoning_effort,
            on_content_delta=delta, on_reasoning_delta=delta), timeout=65)
        report.update(finish_reason=response.finish_reason, content=response.content[:800],
                      passed=response.finish_reason != 'error' and 'MODEL_CONNECTION_OK' in response.content)
    except Exception as exc:
        report.update(passed=False, error=type(exc).__name__+': '+str(exc))
    report['seconds'] = round(time.monotonic()-start, 3)
    print(json.dumps(report, ensure_ascii=False), flush=True)

asyncio.run(main())
'''


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    result = subprocess.run(
        ['ssh', '-o', 'BatchMode=yes', 'papers-research', 'docker exec -i deeptutor python -'],
        input=REMOTE_PROBE, text=True, encoding='utf-8', capture_output=True, timeout=90,
    )
    if result.returncode:
        raise RuntimeError(result.stderr[:1000])
    report = json.loads(result.stdout.strip().splitlines()[-1])
    (ROOT/'reports/model-connection-probe.json').write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False), flush=True)
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
