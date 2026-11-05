"""Run inside the real DeepTutor container; preserve its native turn and history."""
import asyncio
import json
from pathlib import Path
import time
from urllib.parse import quote

import httpx
import websockets


async def main():
    account = json.loads(Path("/migration/admin-login.json").read_text())
    report = json.loads(Path("/migration/dify-live-verification.json").read_text())
    workspace, pid = report["native_workspace_id"], report["project_id"]
    origin = "https://tutor.example.invalid"
    async with httpx.AsyncClient(timeout=30, trust_env=False) as client:
        response = await client.post("http://127.0.0.1:8001/api/auth/login", json=account)
        response.raise_for_status()
        token = response.cookies.get("dt_token")
        assert token
        headers = {"Authorization": "Bearer " + token}
        response = await client.get("http://127.0.0.1:8001/api/settings/llm-options", headers=headers)
        response.raise_for_status()
        options = response.json()
        selection = None
        for item in options.get("options", []):
            if item.get("profile_id") and item.get("model_id"):
                selection = {"profile_id": item["profile_id"], "model_id": item["model_id"]}
                break
        message = (
            "这是当前研究工作台的 Dify 接入验收任务。请实际使用 research_workbench 工具先 context 读取当前项目规范，"
            "再把以下算例写入当前项目的 project/docs/agent-dify-check.md，并通过 deliver 取得真实保存回执。"
            "算例：自由氯为2、结合氯为8；结合相向自由相释放3；请给出变化后的两相数量与总量，"
            "明确这是代数守恒算例，不是实验数据。正文写一小段即可。"
            "本次无需外部检索、代码执行或更改正式稿件。最后只给出算例结论、保存状态和文件位置。"
        )
        payload = {"type": "start_turn", "protocol_version": "2.0", "capability": "chat", "language": "zh",
                   "tools": [], "workspace_id": workspace, "content": message}
        prior_events = Path("/migration/dify-agent-events.json")
        if prior_events.exists():
            previous = json.loads(prior_events.read_text())
            previous_session = next((e.get("session_id") or e.get("metadata", {}).get("session_id")
                                     for e in previous if e.get("session_id") or e.get("metadata", {}).get("session_id")), "")
            if previous_session:
                payload["session_id"] = previous_session
        if selection:
            payload["llm_selection"] = selection
        events, output, session_id, tool_names = [], "", "", []
        started = time.monotonic()
        async with asyncio.timeout(300):
            async with websockets.connect("ws://127.0.0.1:8001/ws?dt_workspace=" + quote(workspace),
                additional_headers={"Cookie": "dt_token=" + token, "Origin": origin}, max_size=20_000_000) as socket:
                await socket.send(json.dumps(payload, ensure_ascii=False))
                async for raw in socket:
                    event = json.loads(raw)
                    events.append(event)
                    kind, meta = event.get("type"), event.get("metadata", {})
                    session_id = meta.get("session_id") or event.get("session_id") or session_id
                    if kind in {"error", "protocol_error"}:
                        raise RuntimeError(str(event.get("content", event))[:600])
                    if kind in {"tool_call", "tool_started", "tool_result", "tool_completed"}:
                        tool_names.append(str(meta.get("tool_name") or meta.get("name") or event.get("tool_name") or event.get("name") or ""))
                    if kind == "content":
                        output += str(event.get("content", ""))
                    if kind == "result":
                        output = meta.get("response") or output
                    if kind == "done":
                        assert meta.get("status") == "completed", meta
                        break
        raw_path = Path("/migration/dify-agent-events.json")
        raw_path.write_text(json.dumps(events, ensure_ascii=False, indent=2))
        response = await client.get(origin + "/research/api/projects/" + pid + "/file?path=docs/agent-dify-check.md", headers=headers)
        response.raise_for_status()
        text = response.text
        assert "5" in text and "10" in text and ("算例" in text or "实验" in text), text
        assert any("research_workbench" in str(event) for event in events), "Native tool was not called"
        result = {"verified": True, "session_id": session_id, "workspace_id": workspace, "project_id": pid,
                  "seconds": round(time.monotonic() - started, 1), "file_path": "project/docs/agent-dify-check.md",
                  "response": output, "native_tool_used": "research_workbench",
                  "session_url": origin + "/chat/" + session_id + "?dt_workspace=" + workspace,
                  "file_content": text}
        Path("/migration/dify-agent-verification.json").write_text(json.dumps(result, ensure_ascii=False, indent=2))
        print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    asyncio.run(main())
