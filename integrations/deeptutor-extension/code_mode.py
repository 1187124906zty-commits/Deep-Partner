"""An additive mode: the native chat loop plus one scoped coding tool."""
from pydantic import BaseModel, ConfigDict

from deeptutor.agents.chat.agentic_pipeline import AgenticChatPipeline
from deeptutor.core.capability_protocol import CapabilityManifest, TurnCapability
from deeptutor.multi_user.context import get_current_user_or_none
from coder_bridge import CoderCapability


class CodeConfig(BaseModel):
    model_config=ConfigDict(extra='forbid')


class CodeMode(TurnCapability):
    manifest=CapabilityManifest(
        name='code',
        description='沿用当前会话，通过 DeepCode 规划、编程与验证；程序保存到固定项目目录（管理员）',
        stages=['responding'],
        tools_used=['coder_run'],
    )

    async def run(self,context,stream):
        user=get_current_user_or_none()
        if user is None or user.role!='admin':
            from deeptutor.core.capability_protocol import CapabilityPrerequisiteError
            raise CapabilityPrerequisiteError('Code 模式暂仅向管理员开放。')
        # Keep the exact session and scope. Nothing is inserted into ordinary
        # chat/solve/research mode; the loop extension activates only for code.
        context.active_capability='code'
        pipeline=AgenticChatPipeline(language=context.language)
        await pipeline.run(context,stream)


class CodeLoop(CoderCapability):
    pass
