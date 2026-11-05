"""Apply the author's unbounded model-wait policy to the deployed Tutor sources.

Only model request deadlines are removed. Cancellation, provider errors and
post-completion usage collection keep their existing behavior.
"""
from pathlib import Path
import argparse
import json

CHANGES = {
    'deeptutor/agents/loop/agent_loop.py': [
        ('_STREAM_IDLE_TIMEOUT_SECONDS = 90.0',
         '# Model silence has no deadline; explicit cancellation remains available.\n'
         '_STREAM_IDLE_TIMEOUT_SECONDS = None'),
        ('"""#1421: a connected provider that never produces a chunk must settle."""',
         '"""Wait until the provider yields, closes, errors, or the caller cancels."""'),
        ('# The loop owns retries. Bound both connection setup and idle\n'
         '                # reads so cold-start failures cannot park a durable turn.',
         '# The loop owns retries for real transport failures. Model setup\n'
         '                # and silent reasoning have no local time deadline.'),
    ],
    'deeptutor/services/llm/provider_core/openai_compat_provider.py': [
        ('idle_timeout_s = 90', 'idle_timeout_s = None  # Wait for output or explicit cancellation.'),
    ],
    'deeptutor/services/llm/provider_core/anthropic_provider.py': [
        ('idle_timeout_s = 90', 'idle_timeout_s = None  # Wait for output or explicit cancellation.'),
        ('client_kw: dict[str, Any] = {"max_retries": 0}',
         'client_kw: dict[str, Any] = {"max_retries": 0, "timeout": None}'),
    ],
    'deeptutor/services/llm/provider_core/azure_openai_provider.py': [
        ('idle_timeout_s = 90', 'idle_timeout_s = None  # Wait for output or explicit cancellation.'),
        ('            max_retries=0,\n            **openai_client_kwargs(),',
         '            max_retries=0,\n            timeout=None,\n            **openai_client_kwargs(),'),
    ],
    'deeptutor/services/llm/provider_core/openai_codex_provider.py': [
        ('httpx.AsyncClient(timeout=60.0, verify=verify)',
         'httpx.AsyncClient(timeout=None, verify=verify)'),
    ],
    'deeptutor/services/llm/openai_http_client.py': [
        ('        "default_headers": headers or None,',
         '        "default_headers": headers or None,\n'
         '        "timeout": None,  # Model duration is controlled by provider completion/cancellation.'),
    ],
    'deeptutor/runtime/agentic/labeled_step.py': [
        ('# Defensive fallback for gateways that never emit ``finish_reason`` but have\n'
         '# already sent a final-label answer and then leave the stream idle.\n'
         '_FINAL_LABEL_IDLE_TIMEOUT_S = 8.0',
         '# A final label can precede more output; wait for provider completion.\n'
         '_FINAL_LABEL_IDLE_TIMEOUT_S = None'),
    ],
}


def patched_source(relative_path, source):
    for before, after in CHANGES[relative_path]:
        if after in source:
            continue
        count = source.count(before)
        if count != 1:
            raise ValueError(f'{relative_path}: expected one known source block, found {count}')
        source = source.replace(before, after, 1)
    compile(source, relative_path, 'exec')
    return source


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    for relative in CHANGES:
        source = (args.source / relative).read_text(encoding='utf-8')
        target = args.output / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(patched_source(relative, source), encoding='utf-8', newline='\n')
    print(json.dumps({'prepared': list(CHANGES), 'model_timeout': None}))


if __name__ == '__main__':
    main()
