from types import SimpleNamespace

from langgraph.checkpoint.base import empty_checkpoint

from backend.services.langgraph_supabase_checkpointer import SupabaseWorkspaceCheckpointer


class _WorkspaceStateTable:
    def __init__(self, state_store):
        self.state_store = state_store
        self.workspace_id = None
        self.mode = "select"
        self.payload = None

    def select(self, *_args, **_kwargs):
        self.mode = "select"
        return self

    def eq(self, column, value):
        assert column == "workspace_id"
        self.workspace_id = value
        return self

    def limit(self, *_args, **_kwargs):
        return self

    def upsert(self, payload):
        self.mode = "upsert"
        self.payload = payload
        return self

    def execute(self):
        if self.mode == "select":
            state = self.state_store.get(self.workspace_id)
            return SimpleNamespace(
                data=[] if state is None else [{"workspace_id": self.workspace_id, "state": state}]
            )
        self.state_store[self.payload["workspace_id"]] = self.payload["state"]
        return SimpleNamespace(data=[self.payload])


class _FakeClient:
    def __init__(self):
        self.state_store = {}

    def table(self, name):
        assert name == "workspace_runtime_state"
        return _WorkspaceStateTable(self.state_store)


def test_supabase_workspace_checkpointer_roundtrip_preserves_pending_writes():
    client = _FakeClient()
    saver = SupabaseWorkspaceCheckpointer(client=client)
    config = {"configurable": {"thread_id": "telegram:-1:main", "checkpoint_ns": ""}}
    checkpoint = empty_checkpoint()
    checkpoint["channel_values"] = {"messages": ["hello"]}

    saved_config = saver.put(config, checkpoint, {"source": "test"}, {})
    saver.put_writes(
        saved_config,
        writes=[("messages", {"value": "draft"})],
        task_id="task-1",
        task_path="travel_editor",
    )

    loaded = saver.get_tuple({"configurable": {"thread_id": "telegram:-1:main", "checkpoint_ns": ""}})

    assert loaded is not None
    assert loaded.checkpoint["id"] == checkpoint["id"]
    assert loaded.checkpoint["channel_values"] == {"messages": ["hello"]}
    assert loaded.metadata["source"] == "test"
    assert loaded.pending_writes == [("task-1", "messages", {"value": "draft"})]


def test_supabase_workspace_checkpointer_preserves_existing_runtime_state():
    client = _FakeClient()
    client.state_store["telegram:-1:main"] = {"booking_context": {"destination": "Sydney"}}
    saver = SupabaseWorkspaceCheckpointer(client=client)

    config = {"configurable": {"thread_id": "telegram:-1:main", "checkpoint_ns": ""}}
    saver.put(config, empty_checkpoint(), {"source": "test"}, {})

    stored_state = client.state_store["telegram:-1:main"]
    assert stored_state["booking_context"] == {"destination": "Sydney"}
    assert "langgraph" in stored_state
