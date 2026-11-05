import pytest

from conftest import IMAGE, QA


@pytest.mark.asyncio
async def test_figure_chat_exact_history_and_changed_image_key(live):
    for path in [IMAGE, "results/independent-no-conversation.png"]:
        native = await live.get("/figure/chat", params={"path": path})
        actual = await live.invoke("workbench_figure_chat", project_id=QA, path=path)
        assert actual["data"] == native
        assert isinstance(native["messages"], list)


@pytest.mark.asyncio
async def test_figure_chat_missing_message_and_unassociated_session_are_errors(live):
    await live.error("workbench_figure_chat", "message", project_id=QA, path=IMAGE, action="send")
    await live.error("workbench_figure_chat", "session_id", project_id=QA, path=IMAGE, action="session")
    native = await live.response("GET", "/figure/session", params={"path": IMAGE, "session_id": "independent-unassociated"})
    assert native.status_code == 403
    await live.error("workbench_figure_chat", "403", project_id=QA, path=IMAGE, action="session", session_id="independent-unassociated")
