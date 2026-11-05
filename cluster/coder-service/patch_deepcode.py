"""Apply only the already observed Krill Responses wire adaptation."""
from importlib.metadata import distribution
from pathlib import Path

p = Path(distribution('deepcode-hku').locate_file('core/providers/openai_compat.py'))
source = p.read_text('utf-8')
needle = '        instructions, input_items = convert_messages(sanitized_messages)\n'
assert source.count(needle) == 1
extra = '''
        # Local deployment: Krill expects instructions as an input message and
        # rejects response-item status fields on replay (verified in DeepTutor).
        from urllib.parse import urlparse
        if urlparse(self.api_base or "").hostname in {
            "api-slb.kbsfdxc.net", "api.kbsfdxc.com", "api.kbsfdxc.net",
        }:
            input_items = [
                {key: value for key, value in item.items() if key != "status"}
                if isinstance(item, dict) else item for item in input_items
            ]
            if instructions:
                input_items.insert(0, {
                    "type": "message", "role": "developer",
                    "content": [{"type": "input_text", "text": instructions}],
                })
'''
source = source.replace(needle, needle + extra)
compile(source, str(p), 'exec')
p.write_text(source, 'utf-8')
print('Applied observed Krill Responses compatibility')
