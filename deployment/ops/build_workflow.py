"""Initial bootstrap DSL before MCP registration; maintain live graphs with optimize_workflow.py."""
import json
from pathlib import Path


def workflow(base="https://tutor.example.invalid/research/dify"):
    nodes = []
    def node(identifier, kind, title, x, **fields):
        nodes.append({"id": identifier, "type": "custom", "width": 244, "height": 100,
                      "position": {"x": x, "y": 100}, "positionAbsolute": {"x": x, "y": 100},
                      "sourcePosition": "right", "targetPosition": "left", "selected": False,
                      "data": {"type": kind, "title": title, "desc": "", **fields}})
    node("start", "start", "接收会话成果票据", 30, variables=[
        {"variable": key, "label": key, "type": "text-input", "required": True, "max_length": 200, "options": []}
        for key in ["run_id", "ticket"]])
    for identifier, action, method, title, x in [
        ("prepare", "context", "get", "核对当前项目与技能规范", 340),
        ("commit", "commit", "post", "写回成果、回读并记录回执", 650),
    ]:
        node(identifier, "http-request", title, x, method=method,
             url=base + "/internal/runs/{{#start.run_id#}}/" + action,
             authorization={"type": "no-auth"}, headers="X-Run-Ticket:{{#start.ticket#}}",
             params="", body={"type": "none", "data": []},
             timeout={"connect": 10, "read": 90, "write": 30},
             retry_config={"retry_enabled": False, "max_retries": 0, "retry_interval": 1000})
    node("end", "end", "返回实际保存回执", 960, outputs=[
        {"variable": "receipt", "value_selector": ["commit", "body"], "value_type": "string"},
        {"variable": "status_code", "value_selector": ["commit", "status_code"], "value_type": "number"}])
    edges = []
    for a, b in zip(nodes, nodes[1:]):
        edges.append({"id": a["id"] + "-" + b["id"], "source": a["id"], "target": b["id"],
                      "sourceHandle": "source", "targetHandle": "target", "type": "custom", "zIndex": 0,
                      "data": {"sourceType": a["data"]["type"], "targetType": b["data"]["type"],
                               "isInIteration": False, "isInLoop": False}})
    return {
        "version": "0.7.0", "kind": "app", "dependencies": [],
        "app": {"name": "研究工作台 · 技能成果交付", "description": "沿用 DeepTutor 会话和当前工作台技能，校验项目、保留版本、回读后返回成果回执。",
                "mode": "workflow", "icon": "📚", "icon_background": "#E5F0E8", "use_icon_as_answer_icon": False},
        "workflow": {"conversation_variables": [], "environment_variables": [],
                     "features": {"file_upload": {"enabled": False}, "retriever_resource": {"enabled": False},
                                  "sensitive_word_avoidance": {"enabled": False}, "speech_to_text": {"enabled": False},
                                  "text_to_speech": {"enabled": False}, "suggested_questions": [],
                                  "suggested_questions_after_answer": {"enabled": False}, "opening_statement": ""},
                     "graph": {"nodes": nodes, "edges": edges, "viewport": {"x": 0, "y": 0, "zoom": 0.8}}},
    }


if __name__ == "__main__":
    output = Path(__file__).resolve().parents[1] / "research-delivery.dsl.json"
    output.write_text(json.dumps(workflow(), ensure_ascii=False, indent=2) + "\n", encoding="utf8")
    print(output)

