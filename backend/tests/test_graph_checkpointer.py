from types import SimpleNamespace

import pytest

import backend.agent.graph as graph


@pytest.mark.asyncio
async def test_configure_graph_checkpointer_uses_async_postgres_saver(monkeypatch: pytest.MonkeyPatch):
    original_app = graph.get_graph_app()
    original_context = graph._checkpointer_context
    calls: dict[str, object] = {}

    class FakeSaver:
        async def setup(self) -> None:
            calls["setup"] = True

    class FakeContext:
        async def __aenter__(self) -> FakeSaver:
            calls["entered"] = True
            return FakeSaver()

        async def __aexit__(self, exc_type, exc_value, traceback) -> None:
            calls["exited"] = True

    class FakeAsyncPostgresSaver:
        @classmethod
        def from_conn_string(cls, conn_string: str) -> FakeContext:
            calls["conn_string"] = conn_string
            return FakeContext()

    monkeypatch.setattr(graph, "AsyncPostgresSaver", FakeAsyncPostgresSaver)
    monkeypatch.setattr(
        graph,
        "_compile_graph",
        lambda checkpointer=None: SimpleNamespace(checkpointer=checkpointer),
    )

    try:
        success = await graph.configure_graph_checkpointer("postgresql://demo")

        assert success is True
        assert calls == {
            "conn_string": "postgresql://demo?sslmode=require&connect_timeout=5",
            "entered": True,
            "setup": True,
        }
        assert isinstance(graph.get_graph_app().checkpointer, FakeSaver)
    finally:
        await graph.close_graph_checkpointer()
        graph._compiled_app = original_app
        graph._checkpointer_context = original_context
