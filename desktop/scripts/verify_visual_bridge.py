"""Synthetic image test; never captures or operates the user's desktop."""
import asyncio
import base64
import importlib.util
import json
import sys
import time
import os
from pathlib import Path
from types import SimpleNamespace
sys.path.insert(0,'/app')

async def main():
    from mcp import types
    import deeptutor.services.mcp.manager
    path=os.environ.get('DEEPTUTOR_VISUAL_TEST_PATH','/app/deeptutor/services/mcp/manager.py')
    module_name='deeptutor.services.mcp.manager'
    spec=importlib.util.spec_from_file_location(module_name,path)
    module=importlib.util.module_from_spec(spec)
    sys.modules[module_name]=module
    spec.loader.exec_module(module)
    # A deterministic synthetic diagram, unrelated to any on-screen user data.
    from PIL import Image,ImageDraw,ImageFont
    import io
    image=Image.new('RGB',(500,260),'white');draw=ImageDraw.Draw(image)
    draw.rectangle((30,30,190,210),fill=(30,90,220))
    draw.ellipse((280,40,450,210),fill=(240,190,0))
    buffer=io.BytesIO();image.save(buffer,format='PNG')
    data=base64.b64encode(buffer.getvalue()).decode()
    result=types.CallToolResult(content=[types.TextContent(type='text',text='Synthetic visual test'),types.ImageContent(type='image',data=data,mimeType='image/png')])
    class FakeSession:
        async def call_tool(self,*args,**kwargs):return result
    conn=SimpleNamespace(session=FakeSession(),name='windows-desktop')
    text=await module.MCPConnectionManager._call_once(conn,'desktop_screenshot',{},10)
    assert hasattr(text,'model_message')
    assert data not in str(text)
    parts=text.model_message['content']
    assert any(p.get('type')=='image_url' for p in parts)
    class FakeManager:
        async def call_tool(self,*args,**kwargs):return text
    adapter=module.MCPToolAdapter.__new__(module.MCPToolAdapter)
    adapter._manager=FakeManager();adapter._owner='_shared';adapter._server_name='windows-desktop';adapter._original_name='desktop_screenshot';adapter._tool_timeout=10
    output=await adapter.execute()
    assert output.model_message==text.model_message
    assert data not in output.content and data not in json.dumps(output.metadata)
    from deeptutor.services.model_selection.runtime import resolve_llm_config_for_selection
    from deeptutor.services.llm.factory import complete_with_config
    llm=resolve_llm_config_for_selection({'profile_id':'llm-profile-agent-setup','model_id':'desktop-terra'})
    start=time.monotonic()
    answer=await complete_with_config(config=llm,prompt='',messages=[{'role':'user','content':[{'type':'text','text':'请只描述图中左侧和右侧各是什么颜色、什么形状。'},*parts[1:]]}],max_tokens=200)
    report={'model':llm.model,'adapter_preserves_private_image':True,'image_omitted_from_public_trace':True,'synthetic_vision_answer':answer,'elapsed_seconds':round(time.monotonic()-start,2),'passed':('蓝' in answer and '黄' in answer)}
    assert report['passed'],answer
    Path('/migration/desktop-vision-verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
    print(json.dumps(report,ensure_ascii=False))

asyncio.run(main())
