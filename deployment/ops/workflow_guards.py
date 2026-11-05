"""Dify code nodes: HTTP transport completion is not business acceptance."""

HTTP_GUARD = '''import json
def main(status_code: int, body: str) -> dict:
    try: value = json.loads(body)
    except (ValueError, TypeError): value = None
    if not 200 <= status_code < 300:
        detail = value.get("detail", "请求未被接受") if isinstance(value, dict) else "响应不是有效JSON"
        raise ValueError("HTTP " + str(status_code) + ": " + str(detail)[:600])
    if not isinstance(value, dict): raise ValueError("接口缺少结构化回执")
    return {"receipt": json.dumps(value, ensure_ascii=False)}
'''

STAGE_GUARD = HTTP_GUARD + '''
check_http = main
def main(status_code: int, body: str, run_id: str, stage: str) -> dict:
    receipt = check_http(status_code, body)
    value = json.loads(receipt["receipt"])
    if value.get("accepted") is not True:
        raise ValueError("写作阶段未被接受，保留当前任务等待核对")
    if value.get("run_id", run_id) != run_id:
        raise ValueError("写作回执不属于当前任务")
    if value.get("stage", stage) != stage and value.get("status") != "already_advanced":
        raise ValueError("写作回执阶段不一致")
    return receipt
'''
