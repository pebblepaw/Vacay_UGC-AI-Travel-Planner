from backend.services.workspace_runtime import workspace_runtime


def test_workspace_id_for_telegram_topic():
    workspace_id = workspace_runtime.workspace_id_for_telegram(chat_id=-10012345, thread_id=77)
    assert workspace_id == "telegram:-10012345:77"


def test_share_token_roundtrip():
    workspace_id = "telegram:-100111:main"
    token = workspace_runtime.make_share_token(workspace_id, ttl_seconds=300)
    verified = workspace_runtime.verify_share_token(token)
    assert verified == workspace_id
