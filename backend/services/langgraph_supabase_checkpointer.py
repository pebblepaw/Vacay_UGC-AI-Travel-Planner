"""Durable LangGraph checkpointer backed by Supabase REST tables.

This avoids direct Postgres socket requirements on local networks that can use
Supabase HTTPS APIs but cannot reach the database host on port 5432.
"""

from __future__ import annotations

from base64 import b64decode, b64encode
from contextlib import AbstractAsyncContextManager, AbstractContextManager
from copy import deepcopy
from datetime import datetime, timezone
import random
from threading import Lock
from typing import Any, AsyncIterator, Iterator, Sequence

from langgraph.checkpoint.base import (
    WRITES_IDX_MAP,
    BaseCheckpointSaver,
    Checkpoint,
    CheckpointMetadata,
    CheckpointTuple,
    ChannelVersions,
    get_checkpoint_id,
    get_checkpoint_metadata,
)
from langchain_core.runnables import RunnableConfig

from backend.storage.supabase_storage import supabase_storage


class SupabaseWorkspaceCheckpointer(
    BaseCheckpointSaver[str], AbstractContextManager, AbstractAsyncContextManager
):
    """Persist LangGraph checkpoints inside ``workspace_runtime_state``."""

    def __init__(self, client: Any | None = None) -> None:
        super().__init__()
        self._client = client or supabase_storage.client
        self._lock = Lock()

    def __enter__(self) -> "SupabaseWorkspaceCheckpointer":
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> bool | None:
        return None

    async def __aenter__(self) -> "SupabaseWorkspaceCheckpointer":
        return self

    async def __aexit__(self, exc_type, exc_value, traceback) -> bool | None:
        return None

    def _encode_typed(self, value: Any) -> dict[str, str]:
        type_name, blob = self.serde.dumps_typed(value)
        return {
            "type": type_name,
            "payload": b64encode(blob).decode("ascii"),
        }

    def _decode_typed(self, value: dict[str, str]) -> Any:
        return self.serde.loads_typed(
            (
                value["type"],
                b64decode(value["payload"].encode("ascii")),
            )
        )

    def _load_runtime_state(self, thread_id: str) -> dict[str, Any]:
        result = (
            self._client.table("workspace_runtime_state")
            .select("state")
            .eq("workspace_id", thread_id)
            .limit(1)
            .execute()
        )
        if result.data:
            return deepcopy(result.data[0].get("state") or {})
        return {}

    def _persist_runtime_state(self, thread_id: str, state: dict[str, Any]) -> None:
        self._client.table("workspace_runtime_state").upsert(
            {
                "workspace_id": thread_id,
                "state": state,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
        ).execute()

    def _checkpoint_entry(
        self,
        thread_id: str,
        checkpoint_ns: str,
        checkpoint_id: str | None = None,
    ) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], str | None]:
        state = self._load_runtime_state(thread_id)
        langgraph_state = state.setdefault("langgraph", {})
        checkpoints = langgraph_state.setdefault("checkpoints", {})
        namespace = checkpoints.setdefault(checkpoint_ns, {})
        if checkpoint_id is None and namespace:
            checkpoint_id = max(namespace.keys())
        entry = namespace.get(checkpoint_id or "")
        return state, namespace, entry or {}, checkpoint_id

    def _build_tuple(
        self,
        thread_id: str,
        checkpoint_ns: str,
        checkpoint_id: str,
        entry: dict[str, Any],
    ) -> CheckpointTuple:
        checkpoint: Checkpoint = self._decode_typed(entry["checkpoint"])
        metadata: CheckpointMetadata = self._decode_typed(entry["metadata"])
        pending_writes = [
            (
                item["task_id"],
                item["channel"],
                self._decode_typed(item["value"]),
            )
            for item in sorted(
                entry.get("pending_writes", []),
                key=lambda item: (item.get("index", 0), item.get("task_id", "")),
            )
        ]
        parent_checkpoint_id = entry.get("parent_checkpoint_id")
        return CheckpointTuple(
            config={
                "configurable": {
                    "thread_id": thread_id,
                    "checkpoint_ns": checkpoint_ns,
                    "checkpoint_id": checkpoint_id,
                }
            },
            checkpoint=checkpoint,
            metadata=metadata,
            parent_config=(
                {
                    "configurable": {
                        "thread_id": thread_id,
                        "checkpoint_ns": checkpoint_ns,
                        "checkpoint_id": parent_checkpoint_id,
                    }
                }
                if parent_checkpoint_id
                else None
            ),
            pending_writes=pending_writes,
        )

    def get_tuple(self, config: RunnableConfig) -> CheckpointTuple | None:
        thread_id = config["configurable"]["thread_id"]
        checkpoint_ns = config["configurable"].get("checkpoint_ns", "")
        requested_checkpoint_id = get_checkpoint_id(config)
        with self._lock:
            _, _, entry, checkpoint_id = self._checkpoint_entry(
                thread_id,
                checkpoint_ns,
                requested_checkpoint_id,
            )
        if not checkpoint_id or not entry:
            return None
        return self._build_tuple(thread_id, checkpoint_ns, checkpoint_id, entry)

    def list(
        self,
        config: RunnableConfig | None,
        *,
        filter: dict[str, Any] | None = None,
        before: RunnableConfig | None = None,
        limit: int | None = None,
    ) -> Iterator[CheckpointTuple]:
        if config is None:
            return

        thread_id = config["configurable"]["thread_id"]
        checkpoint_ns = config["configurable"].get("checkpoint_ns", "")
        before_checkpoint_id = get_checkpoint_id(before) if before else None
        with self._lock:
            state = self._load_runtime_state(thread_id)
        namespace = (
            state.get("langgraph", {})
            .get("checkpoints", {})
            .get(checkpoint_ns, {})
        )
        remaining = limit
        for checkpoint_id, entry in sorted(namespace.items(), reverse=True):
            if before_checkpoint_id and checkpoint_id >= before_checkpoint_id:
                continue
            checkpoint_tuple = self._build_tuple(thread_id, checkpoint_ns, checkpoint_id, entry)
            if filter and not all(
                checkpoint_tuple.metadata.get(key) == value for key, value in filter.items()
            ):
                continue
            yield checkpoint_tuple
            if remaining is not None:
                remaining -= 1
                if remaining <= 0:
                    break

    def put(
        self,
        config: RunnableConfig,
        checkpoint: Checkpoint,
        metadata: CheckpointMetadata,
        new_versions: ChannelVersions,
    ) -> RunnableConfig:
        del new_versions
        thread_id = config["configurable"]["thread_id"]
        checkpoint_ns = config["configurable"].get("checkpoint_ns", "")
        checkpoint_id = checkpoint["id"]

        with self._lock:
            state = self._load_runtime_state(thread_id)
            langgraph_state = state.setdefault("langgraph", {})
            namespaces = langgraph_state.setdefault("checkpoints", {})
            namespace = namespaces.setdefault(checkpoint_ns, {})
            existing = namespace.get(checkpoint_id, {})
            namespace[checkpoint_id] = {
                "checkpoint": self._encode_typed(checkpoint),
                "metadata": self._encode_typed(get_checkpoint_metadata(config, metadata)),
                "parent_checkpoint_id": config["configurable"].get("checkpoint_id"),
                "pending_writes": existing.get("pending_writes", []),
            }
            self._persist_runtime_state(thread_id, state)

        return {
            "configurable": {
                "thread_id": thread_id,
                "checkpoint_ns": checkpoint_ns,
                "checkpoint_id": checkpoint_id,
            }
        }

    def put_writes(
        self,
        config: RunnableConfig,
        writes: Sequence[tuple[str, Any]],
        task_id: str,
        task_path: str = "",
    ) -> None:
        thread_id = config["configurable"]["thread_id"]
        checkpoint_ns = config["configurable"].get("checkpoint_ns", "")
        checkpoint_id = config["configurable"]["checkpoint_id"]

        with self._lock:
            state = self._load_runtime_state(thread_id)
            langgraph_state = state.setdefault("langgraph", {})
            namespaces = langgraph_state.setdefault("checkpoints", {})
            namespace = namespaces.setdefault(checkpoint_ns, {})
            entry = namespace.setdefault(
                checkpoint_id,
                {
                    "checkpoint": self._encode_typed({}),
                    "metadata": self._encode_typed({}),
                    "parent_checkpoint_id": None,
                    "pending_writes": [],
                },
            )
            existing = {
                (item["task_id"], item["index"]): item
                for item in entry.get("pending_writes", [])
            }
            for idx, (channel, value) in enumerate(writes):
                write_index = WRITES_IDX_MAP.get(channel, idx)
                if write_index >= 0 or (task_id, write_index) not in existing:
                    existing[(task_id, write_index)] = {
                        "task_id": task_id,
                        "channel": channel,
                        "value": self._encode_typed(value),
                        "task_path": task_path,
                        "index": write_index,
                    }
            entry["pending_writes"] = list(existing.values())
            namespace[checkpoint_id] = entry
            self._persist_runtime_state(thread_id, state)

    def delete_thread(self, thread_id: str) -> None:
        with self._lock:
            state = self._load_runtime_state(thread_id)
            if "langgraph" in state:
                state.pop("langgraph", None)
                self._persist_runtime_state(thread_id, state)

    async def aget_tuple(self, config: RunnableConfig) -> CheckpointTuple | None:
        return self.get_tuple(config)

    async def alist(
        self,
        config: RunnableConfig | None,
        *,
        filter: dict[str, Any] | None = None,
        before: RunnableConfig | None = None,
        limit: int | None = None,
    ) -> AsyncIterator[CheckpointTuple]:
        for item in self.list(config, filter=filter, before=before, limit=limit):
            yield item

    async def aput(
        self,
        config: RunnableConfig,
        checkpoint: Checkpoint,
        metadata: CheckpointMetadata,
        new_versions: ChannelVersions,
    ) -> RunnableConfig:
        return self.put(config, checkpoint, metadata, new_versions)

    async def aput_writes(
        self,
        config: RunnableConfig,
        writes: Sequence[tuple[str, Any]],
        task_id: str,
        task_path: str = "",
    ) -> None:
        self.put_writes(config, writes, task_id, task_path)

    async def adelete_thread(self, thread_id: str) -> None:
        self.delete_thread(thread_id)

    def get_next_version(self, current: str | None, channel: None) -> str:
        del channel
        if current is None:
            current_v = 0
        elif isinstance(current, int):
            current_v = current
        else:
            current_v = int(str(current).split(".")[0])
        next_v = current_v + 1
        next_h = random.random()
        return f"{next_v:032}.{next_h:016}"
