"""Workspace runtime service for shared Telegram + web collaboration."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import hmac
import json
import logging
from typing import Any

from backend.config import settings
from backend.models.schemas import Trip
from backend.storage.supabase_storage import supabase_storage

logger = logging.getLogger(__name__)


class WorkspaceRuntimeService:
    """Workspace-scoped runtime with durable fallback when DB tables are absent."""

    def __init__(self) -> None:
        self._memory_events: dict[str, list[dict[str, Any]]] = {}
        self._memory_state: dict[str, dict[str, Any]] = {}

    def workspace_id_for_telegram(self, chat_id: int | str, thread_id: int | str | None = None) -> str:
        suffix = thread_id if thread_id is not None else "main"
        return f"telegram:{chat_id}:{suffix}"

    async def ensure_workspace(
        self,
        workspace_id: str,
        title: str | None = None,
        trip_id: str | None = None,
    ) -> dict[str, Any]:
        """Ensure workspace row exists; if table is missing, keep in memory."""
        now_iso = datetime.now(timezone.utc).isoformat()
        payload = {
            "id": workspace_id,
            "title": title or "VacayClaw Workspace",
            "trip_id": trip_id or workspace_id.replace(":", "-"),
            "source": "telegram" if workspace_id.startswith("telegram:") else "web",
            "data": {"created_at": now_iso, "updated_at": now_iso},
        }
        try:
            supabase_storage.client.table("workspaces").upsert(payload).execute()
        except Exception as exc:
            logger.info("Workspace table unavailable; using in-memory fallback: %s", exc)
            self._memory_state.setdefault(workspace_id, payload)
        return payload

    async def bind_workspace_to_trip(self, workspace_id: str, trip_id: str, title: str | None = None) -> None:
        """Update workspace binding once a real trip exists."""
        now_iso = datetime.now(timezone.utc).isoformat()
        payload = {
            "id": workspace_id,
            "trip_id": trip_id,
            "title": title or "VacayClaw Workspace",
            "source": "telegram" if workspace_id.startswith("telegram:") else "web",
            "data": {"updated_at": now_iso},
        }
        try:
            supabase_storage.client.table("workspaces").upsert(payload).execute()
        except Exception:
            current = self._memory_state.get(workspace_id) or {}
            current.update(payload)
            self._memory_state[workspace_id] = current

    async def get_workspace_trip_id(self, workspace_id: str) -> str:
        try:
            result = (
                supabase_storage.client.table("workspaces")
                .select("trip_id")
                .eq("id", workspace_id)
                .limit(1)
                .execute()
            )
            if result.data and result.data[0].get("trip_id"):
                return result.data[0]["trip_id"]
        except Exception:
            pass

        entry = self._memory_state.get(workspace_id)
        if entry and entry.get("trip_id"):
            return entry["trip_id"]

        ensured = await self.ensure_workspace(workspace_id)
        return ensured["trip_id"]

    async def append_event(self, workspace_id: str, role: str, content: str, metadata: dict[str, Any] | None = None) -> None:
        event = {
            "workspace_id": workspace_id,
            "role": role,
            "content": content,
            "metadata": metadata or {},
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        try:
            supabase_storage.client.table("conversation_events").insert(event).execute()
        except Exception:
            self._memory_events.setdefault(workspace_id, []).append(event)

    async def list_events(self, workspace_id: str, limit: int = 30) -> list[dict[str, Any]]:
        try:
            result = (
                supabase_storage.client.table("conversation_events")
                .select("role,content,metadata,created_at")
                .eq("workspace_id", workspace_id)
                .order("created_at", desc=False)
                .limit(limit)
                .execute()
            )
            if result.data:
                return result.data
        except Exception:
            pass
        return self._memory_events.get(workspace_id, [])[-limit:]

    async def load_runtime_state(self, workspace_id: str) -> dict[str, Any]:
        try:
            result = (
                supabase_storage.client.table("workspace_runtime_state")
                .select("state")
                .eq("workspace_id", workspace_id)
                .limit(1)
                .execute()
            )
            if result.data:
                return result.data[0].get("state") or {}
        except Exception:
            pass
        return self._memory_state.get(f"runtime:{workspace_id}", {})

    async def save_runtime_state(self, workspace_id: str, state: dict[str, Any]) -> None:
        payload = {
            "workspace_id": workspace_id,
            "state": state,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        try:
            supabase_storage.client.table("workspace_runtime_state").upsert(payload).execute()
        except Exception:
            self._memory_state[f"runtime:{workspace_id}"] = state

    async def upsert_memory(self, workspace_id: str, user_id: str | None, key: str, value: Any) -> None:
        payload = {
            "workspace_id": workspace_id,
            "user_id": user_id,
            "memory_key": key,
            "memory_value": value,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        try:
            supabase_storage.client.table("memory_entries").upsert(payload).execute()
        except Exception:
            bucket = self._memory_state.setdefault(f"memory:{workspace_id}:{user_id or 'workspace'}", {})
            bucket[key] = value

    async def list_memory(self, workspace_id: str, user_id: str | None = None) -> dict[str, Any]:
        try:
            query = supabase_storage.client.table("memory_entries").select("memory_key,memory_value").eq("workspace_id", workspace_id)
            if user_id is None:
                query = query.is_("user_id", "null")
            else:
                query = query.eq("user_id", user_id)
            result = query.execute()
            if result.data:
                return {row["memory_key"]: row["memory_value"] for row in result.data}
        except Exception:
            pass
        return self._memory_state.get(f"memory:{workspace_id}:{user_id or 'workspace'}", {})

    async def build_workspace_snapshot(self, workspace_id: str, trip: Trip) -> dict[str, Any]:
        """Derive a snapshot for web clients from trip + workspace state."""
        state = await self.load_runtime_state(workspace_id)
        memory = await self.list_memory(workspace_id, user_id=None)
        events = await self.list_events(workspace_id, limit=50)

        media_by_place: dict[str, list[dict[str, Any]]] = {}
        for video in trip.source_videos:
            for day in trip.days:
                for poi in day.pois:
                    if poi.name.lower().split()[0] in video.title.lower():
                        media_by_place.setdefault(poi.id, []).append(
                            {
                                "title": video.title,
                                "url": video.url,
                                "platform": video.platform,
                                "autoplay": True,
                            }
                        )

        snapshot = {
            "workspace_id": workspace_id,
            "trip": trip.model_dump(mode="json"),
            "media_by_place": media_by_place,
            "runtime_state": state,
            "workspace_memory": memory,
            "recent_events": events,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        try:
            supabase_storage.client.table("workspace_snapshots").upsert(
                {
                    "workspace_id": workspace_id,
                    "snapshot": snapshot,
                    "updated_at": snapshot["updated_at"],
                }
            ).execute()
        except Exception:
            self._memory_state[f"snapshot:{workspace_id}"] = snapshot
        return snapshot

    async def get_workspace_snapshot(self, workspace_id: str) -> dict[str, Any] | None:
        try:
            result = (
                supabase_storage.client.table("workspace_snapshots")
                .select("snapshot")
                .eq("workspace_id", workspace_id)
                .limit(1)
                .execute()
            )
            if result.data:
                return result.data[0].get("snapshot")
        except Exception:
            pass
        return self._memory_state.get(f"snapshot:{workspace_id}")

    def make_share_token(self, workspace_id: str, ttl_seconds: int = 60 * 60 * 24) -> str:
        """Create a signed handoff token (no full auth, but scoped and expiring)."""
        exp = int(datetime.now(tz=timezone.utc).timestamp()) + ttl_seconds
        body = json.dumps({"workspace_id": workspace_id, "exp": exp}, separators=(",", ":")).encode()
        secret = (settings.SECRET_KEY or "vacayclaw-dev-secret").encode()
        sig = hmac.new(secret, body, hashlib.sha256).hexdigest()
        return f"{body.hex()}.{sig}"

    def verify_share_token(self, token: str) -> str | None:
        try:
            payload_hex, sig = token.split(".", 1)
            body = bytes.fromhex(payload_hex)
            secret = (settings.SECRET_KEY or "vacayclaw-dev-secret").encode()
            expected = hmac.new(secret, body, hashlib.sha256).hexdigest()
            if not hmac.compare_digest(expected, sig):
                return None
            data = json.loads(body.decode())
            if int(data.get("exp", 0)) < int(datetime.now(tz=timezone.utc).timestamp()):
                return None
            return str(data["workspace_id"])
        except Exception:
            return None


workspace_runtime = WorkspaceRuntimeService()
