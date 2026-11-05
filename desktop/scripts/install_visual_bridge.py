"""Preserve this desktop's MCP screenshots in DeepTutor's model-only channel.

Creates a separate Docker compatibility mount, preserving the upstream source.
Run on the deployment host as its administrator.
"""
from pathlib import Path
import json
import subprocess
import re

root=Path('/srv/deeptutor')
target=root/'compat/mcp_manager.py'
subprocess.run(['docker','cp','deeptutor:/app/deeptutor/services/mcp/manager.py',str(target)],check=True)
source=target.read_text()
if 'class _DesktopImageText' not in source:
    marker='logger = logging.getLogger(__name__)'
    insertion='''class _DesktopImageText(str):
    """Text trace with a separate transient image message for this desktop."""
    def __new__(cls, text, images):
        value = super().__new__(cls, text)
        value.model_message = {"role": "user", "content": [
            {"type": "text", "text": "Screenshot returned by the Windows desktop tool. Use this image as the current visual observation; coordinates are described in the preceding tool result."},
            *images,
        ]}
        return value


'''
    assert marker in source
    source=source.replace(marker,insertion+marker,1)
    old='''            content=text,
            metadata={'''
    new='''            content=str(text),
            model_message=getattr(text, "model_message", None),
            metadata={'''
    assert old in source
    source=source.replace(old,new,1)
    old='''        parts: list[str] = []
        for block in result.content:'''
    new='''        parts: list[str] = []
        desktop_images = []
        for block in result.content:'''
    assert old in source
    source=source.replace(old,new,1)
    old='''            elif isinstance(block, types.ImageContent):
                parts.append("[MCP image omitted]")'''
    new='''            elif isinstance(block, types.ImageContent):
                if (conn.name == "windows-desktop" and len(desktop_images) < 2
                        and block.mimeType in {"image/png", "image/jpeg", "image/webp"}
                        and len(block.data) <= 16 * 1024 * 1024):
                    desktop_images.append({"type": "image_url", "image_url": {
                        "url": f"data:{block.mimeType};base64,{block.data}"
                    }})
                    parts.append("[Windows screenshot attached for visual analysis]")
                else:
                    parts.append("[MCP image omitted]")'''
    assert old in source
    source=source.replace(old,new,1)
    old='''        return "\\n".join(parts) or "(no output)"'''
    new='''        text = "\\n".join(parts) or "(no output)"
        return _DesktopImageText(text, desktop_images) if desktop_images else text'''
    assert old in source
    source=source.replace(old,new,1)
    compile(source,str(target),'exec')
    target.write_text(source)

compose=root/'compose.yaml'
text=compose.read_text()
mount='      - ./compat/mcp_manager.py:/app/deeptutor/services/mcp/manager.py:ro'
if './compat/mcp_manager.py:/app/deeptutor/services/mcp/manager.py:ro' not in text:
    match=re.search(r'(?m)^([ \t]*)-\s+[^\n]*:/migration(?::ro)?[ \t]*$',text)
    assert match, 'Could not locate the existing migration mount'
    mount=match.group(1)+'- ./compat/mcp_manager.py:/app/deeptutor/services/mcp/manager.py:ro'
    text=text[:match.end()]+'\n'+mount+text[match.end():]
    compose.write_text(text)
print(json.dumps({'compatibility_file':str(target),'compose_mount_ready':True,'restarted':False}))
