"""Workspace runtime service for shared Telegram + web collaboration."""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import hashlib
import hmac
import json
import logging
import uuid
from typing import Any
from urllib.parse import urlparse

from backend.config import settings
from backend.models.schemas import Trip
from backend.storage.supabase_storage import supabase_storage

logger = logging.getLogger(__name__)


class WorkspaceRuntimeService:
    """Workspace-scoped runtime with durable fallback when DB tables are absent."""

    def __init__(self) -> None:
        self._memory_events: dict[str, list[dict[str, Any]]] = {}
        self._memory_state: dict[str, dict[str, Any]] = {}
        self._subscribers: dict[str, set[asyncio.Queue[dict[str, Any]]]] = {}

    def workspace_id_for_telegram(self, chat_id: int | str, thread_id: int | str | None = None) -> str:
        suffix = thread_id if thread_id is not None else "main"
        return f"telegram:{chat_id}:{suffix}"

    async def get_workspace_record(self, workspace_id: str) -> dict[str, Any] | None:
        try:
            result = (
                supabase_storage.client.table("workspaces")
                .select("id,title,trip_id,source,data")
                .eq("id", workspace_id)
                .limit(1)
                .execute()
            )
            if result.data:
                return result.data[0]
        except Exception:
            pass
        return self._memory_state.get(workspace_id)

    async def ensure_workspace(
        self,
        workspace_id: str,
        title: str | None = None,
        trip_id: str | None = None,
    ) -> dict[str, Any]:
        """Ensure workspace row exists; if table is missing, keep in memory."""
        now_iso = datetime.now(timezone.utc).isoformat()
        existing = await self.get_workspace_record(workspace_id)

        existing_data = dict(existing.get("data") or {}) if existing else {}
        payload = {
            "id": workspace_id,
            "title": title or (existing.get("title") if existing else None) or "VacayClaw Workspace",
            "trip_id": trip_id or (existing.get("trip_id") if existing else None) or workspace_id.replace(":", "-"),
            "source": (existing.get("source") if existing else None) or ("telegram" if workspace_id.startswith("telegram:") else "web"),
            "data": {
                **existing_data,
                "created_at": existing_data.get("created_at", now_iso),
                "updated_at": now_iso,
            },
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
        existing = await self.get_workspace_record(workspace_id)
        existing_data = dict(existing.get("data") or {}) if existing else {}
        payload = {
            "id": workspace_id,
            "trip_id": trip_id,
            "title": title or (existing.get("title") if existing else None) or "VacayClaw Workspace",
            "source": (existing.get("source") if existing else None) or ("telegram" if workspace_id.startswith("telegram:") else "web"),
            "data": {
                **existing_data,
                "created_at": existing_data.get("created_at", now_iso),
                "updated_at": now_iso,
            },
        }
        try:
            supabase_storage.client.table("workspaces").upsert(payload).execute()
        except Exception:
            current = self._memory_state.get(workspace_id) or {}
            current.update(payload)
            self._memory_state[workspace_id] = current

    async def restart_workspace(self, workspace_id: str, title: str | None = None) -> dict[str, Any]:
        """Start a fresh trip session without deleting historical rows."""
        now_iso = datetime.now(timezone.utc).isoformat()
        new_trip_id = f"trip_{uuid.uuid4().hex[:12]}"
        existing = await self.get_workspace_record(workspace_id)
        existing_data = dict(existing.get("data") or {}) if existing else {}
        payload = {
            "id": workspace_id,
            "trip_id": new_trip_id,
            "title": title or (existing.get("title") if existing else None) or "VacayClaw Workspace",
            "source": (existing.get("source") if existing else None) or ("telegram" if workspace_id.startswith("telegram:") else "web"),
            "data": {
                **existing_data,
                "created_at": existing_data.get("created_at", now_iso),
                "started_at": now_iso,
                "updated_at": now_iso,
            },
        }
        try:
            supabase_storage.client.table("workspaces").upsert(payload).execute()
            supabase_storage.client.table("workspace_runtime_state").upsert(
                {
                    "workspace_id": workspace_id,
                    "state": {},
                    "updated_at": now_iso,
                }
            ).execute()
        except Exception:
            self._memory_state[workspace_id] = payload
            self._memory_state[f"runtime:{workspace_id}"] = {}
            self._memory_state.pop(f"snapshot:{workspace_id}", None)
        return payload

    async def get_workspace_started_at(self, workspace_id: str) -> str | None:
        existing = await self.get_workspace_record(workspace_id)
        if not existing:
            return None
        data = dict(existing.get("data") or {})
        return data.get("started_at")

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
        started_at = await self.get_workspace_started_at(workspace_id)
        try:
            query = (
                supabase_storage.client.table("conversation_events")
                .select("role,content,metadata,created_at")
                .eq("workspace_id", workspace_id)
                .order("created_at", desc=False)
                .limit(limit)
            )
            if started_at:
                query = query.gte("created_at", started_at)
            result = query.execute()
            if result.data:
                return result.data
        except Exception:
            pass
        events = self._memory_events.get(workspace_id, [])
        if not started_at:
            return events[-limit:]
        return [
            event for event in events[-limit:]
            if str(event.get("created_at") or "") >= started_at
        ]

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
        existing_state = await self.load_runtime_state(workspace_id)
        payload = {
            "workspace_id": workspace_id,
            "state": {
                **existing_state,
                **state,
            },
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        try:
            supabase_storage.client.table("workspace_runtime_state").upsert(payload).execute()
        except Exception:
            self._memory_state[f"runtime:{workspace_id}"] = payload["state"]

    async def clear_langgraph_state(self, workspace_id: str) -> None:
        """Drop persisted LangGraph checkpoints before a new top-level turn.

        Workspace memory, booking context, and pending import candidates live in
        the same runtime blob. Keep those fields intact and only remove the
        graph checkpoint branch so a fresh request does not inherit stale plan
        state from an earlier turn.
        """
        state = await self.load_runtime_state(workspace_id)
        if not state or "langgraph" not in state:
            return

        trimmed_state = dict(state)
        trimmed_state.pop("langgraph", None)

        payload = {
            "workspace_id": workspace_id,
            "state": trimmed_state,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        try:
            supabase_storage.client.table("workspace_runtime_state").upsert(payload).execute()
        except Exception:
            self._memory_state[f"runtime:{workspace_id}"] = trimmed_state

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
        started_at = await self.get_workspace_started_at(workspace_id)
        try:
            query = supabase_storage.client.table("memory_entries").select("memory_key,memory_value").eq("workspace_id", workspace_id)
            if user_id is None:
                query = query.is_("user_id", "null")
            else:
                query = query.eq("user_id", user_id)
            if started_at:
                query = query.gte("updated_at", started_at)
            result = query.execute()
            if result.data:
                return {row["memory_key"]: row["memory_value"] for row in result.data}
        except Exception:
            pass
        return self._memory_state.get(f"memory:{workspace_id}:{user_id or 'workspace'}", {})

    def subscribe(self, workspace_id: str) -> asyncio.Queue[dict[str, Any]]:
        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=8)
        self._subscribers.setdefault(workspace_id, set()).add(queue)
        return queue

    def unsubscribe(self, workspace_id: str, queue: asyncio.Queue[dict[str, Any]]) -> None:
        listeners = self._subscribers.get(workspace_id)
        if not listeners:
            return
        listeners.discard(queue)
        if not listeners:
            self._subscribers.pop(workspace_id, None)

    async def publish_snapshot(self, workspace_id: str, snapshot: dict[str, Any]) -> None:
        payload = {"type": "snapshot", "snapshot": snapshot}
        for queue in list(self._subscribers.get(workspace_id, set())):
            try:
                if queue.full():
                    queue.get_nowait()
                queue.put_nowait(payload)
            except Exception:
                self.unsubscribe(workspace_id, queue)

    def _normalize_media_url(self, url: str | None) -> str | None:
        if not url:
            return url

        parsed = urlparse(url)
        media_index = parsed.path.find("/media/")
        if media_index == -1:
            return url

        media_path = parsed.path[media_index:]
        base = settings.PUBLIC_API_BASE_URL.rstrip("/")
        return f"{base}{media_path}"

    def _normalize_snapshot_media_urls(self, snapshot: dict[str, Any]) -> dict[str, Any]:
        trip = snapshot.get("trip") or {}
        source_videos = trip.get("source_videos") or []
        for video in source_videos:
            if isinstance(video, dict):
                video["preview_url"] = self._normalize_media_url(video.get("preview_url"))

        media_by_place = snapshot.get("media_by_place") or {}
        for media_items in media_by_place.values():
            for media in media_items:
                if isinstance(media, dict):
                    media["url"] = self._normalize_media_url(media.get("url")) or media.get("url")

        return snapshot

    async def build_workspace_snapshot(self, workspace_id: str, trip: Trip) -> dict[str, Any]:
        """Derive a snapshot for web clients from trip + workspace state."""
        state = await self.load_runtime_state(workspace_id)
        memory = await self.list_memory(workspace_id, user_id=None)
        events = await self.list_events(workspace_id, limit=50)

        media_by_place: dict[str, list[dict[str, Any]]] = {}
        video_lookup: dict[str, Any] = {}
        for video in trip.source_videos:
            for key in (video.url, video.preview_url):
                if key:
                    video_lookup[key] = video

        for day in trip.days:
            for poi in day.pois:
                poi_media: list[dict[str, Any]] = []
                for media_url in poi.media_urls:
                    video = video_lookup.get(media_url)
                    if video:
                        playback_url = video.preview_url or video.url
                        poi_media.append(
                            {
                                "title": video.title,
                                "url": playback_url,
                                "source_url": video.url,
                                "platform": video.platform,
                                "autoplay": bool(video.preview_url or video.platform == "youtube"),
                            }
                        )
                    else:
                        poi_media.append(
                            {
                                "title": poi.name,
                                "url": media_url,
                                "source_url": media_url,
                                "platform": "unknown",
                                "autoplay": False,
                            }
                        )
                if poi_media:
                    media_by_place[poi.id] = poi_media

        snapshot = {
            "workspace_id": workspace_id,
            "trip": trip.model_dump(mode="json"),
            "media_by_place": media_by_place,
            "runtime_state": state,
            "workspace_memory": memory,
            "recent_events": events,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        snapshot = self._normalize_snapshot_media_urls(snapshot)
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
        await self.publish_snapshot(workspace_id, snapshot)
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
                return self._normalize_snapshot_media_urls(result.data[0].get("snapshot") or {})
        except Exception:
            pass
        cached = self._memory_state.get(f"snapshot:{workspace_id}")
        if cached is None:
            return None
        return self._normalize_snapshot_media_urls(cached)

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
