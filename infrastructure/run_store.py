from __future__ import annotations

import json
import threading
import time
import uuid
from datetime import datetime
from typing import Any

from infrastructure.settings import platform_settings

try:
    import redis
except ImportError:  # pragma: no cover - dependency is optional in local fallback mode
    redis = None


class AgentRunStore:
    """Stores agent progress in Redis and transparently falls back to memory."""

    def __init__(self) -> None:
        self._memory: dict[str, dict[str, Any]] = {}
        self._lock = threading.RLock()
        self._redis = None
        if redis is not None and platform_settings.redis_url:
            try:
                client = redis.Redis.from_url(platform_settings.redis_url, decode_responses=True)
                client.ping()
                self._redis = client
            except Exception:
                self._redis = None

    def create(
        self,
        workflow: str,
        user_id: int | None = None,
        organization_id: int | None = None,
        input_payload: dict[str, Any] | None = None,
    ) -> str:
        run_id = uuid.uuid4().hex
        state = {
            "run_id": run_id,
            "workflow": workflow,
            "user_id": user_id,
            "organization_id": organization_id,
            "input": input_payload or {},
            "status": "running",
            "current_node": "",
            "events": [],
            "cancelled": False,
            "created_at": datetime.now().isoformat(),
            "started_epoch": time.time(),
            "updated_at": datetime.now().isoformat(),
        }
        self._write(run_id, state)
        self._persist_create(state)
        return run_id

    def append_event(self, run_id: str, event_type: str, node: str = "", **payload: Any) -> dict[str, Any]:
        with self._lock:
            state = self.get(run_id) or {"run_id": run_id, "events": [], "status": "running"}
            event = {
                "type": event_type,
                "run_id": run_id,
                "node": node,
                "sequence": len(state.get("events", [])) + 1,
                "timestamp": datetime.now().isoformat(),
                **payload,
            }
            state.setdefault("events", []).append(event)
            state["events"] = state["events"][-200:]
            state["current_node"] = node or state.get("current_node", "")
            state["updated_at"] = datetime.now().isoformat()
            if event_type == "run_finished":
                state["status"] = "completed"
                state["result"] = payload.get("result")
                state["latency_ms"] = int((time.time() - float(state.get("started_epoch", time.time()))) * 1000)
            elif event_type == "run_error":
                state["status"] = "failed"
                state["error"] = payload.get("detail", "")
                state["latency_ms"] = int((time.time() - float(state.get("started_epoch", time.time()))) * 1000)
            self._write(run_id, state)
            self._persist_event(state, event)
            return event

    def cancel(self, run_id: str) -> bool:
        state = self.get(run_id)
        if not state:
            return False
        state["cancelled"] = True
        state["status"] = "cancelled"
        state["updated_at"] = datetime.now().isoformat()
        self._write(run_id, state)
        self._persist_status(state)
        return True

    def is_cancelled(self, run_id: str) -> bool:
        return bool((self.get(run_id) or {}).get("cancelled"))

    def get(self, run_id: str) -> dict[str, Any] | None:
        if self._redis is not None:
            raw = self._redis.get(f"agent-run:{run_id}")
            if raw:
                return json.loads(raw)
        with self._lock:
            value = self._memory.get(run_id)
            if value:
                return json.loads(json.dumps(value, ensure_ascii=False))
        return self._load_persisted(run_id)

    def list_recent(self, limit: int = 50) -> list[dict[str, Any]]:
        if self._redis is not None:
            values = []
            for key in self._redis.scan_iter(match="agent-run:*", count=100):
                raw = self._redis.get(key)
                if raw:
                    values.append(json.loads(raw))
            values.sort(key=lambda item: item.get("updated_at", ""), reverse=True)
            return [{key: value for key, value in item.items() if key != "events"} for item in values[:limit]]
        with self._lock:
            values = list(self._memory.values())
        values.sort(key=lambda item: item.get("updated_at", ""), reverse=True)
        return [{key: value for key, value in item.items() if key != "events"} for item in values[:limit]]

    def _write(self, run_id: str, state: dict[str, Any]) -> None:
        if self._redis is not None:
            self._redis.setex(
                f"agent-run:{run_id}",
                platform_settings.agent_event_ttl_seconds,
                json.dumps(state, ensure_ascii=False, default=str),
            )
            return
        with self._lock:
            self._memory[run_id] = state

    @staticmethod
    def _persist_create(state: dict[str, Any]) -> None:
        try:
            from infrastructure.database import AgentRun, platform_database_enabled, platform_session

            if not platform_database_enabled():
                return
            with platform_session() as session:
                session.add(
                    AgentRun(
                        id=state["run_id"],
                        user_id=state.get("user_id"),
                        organization_id=state.get("organization_id"),
                        workflow=state.get("workflow", "agent"),
                        status=state.get("status", "running"),
                        input_json=state.get("input", {}),
                    )
                )
        except Exception:
            # Observability persistence must never break the user-facing model call.
            return

    @staticmethod
    def _persist_event(state: dict[str, Any], event: dict[str, Any]) -> None:
        try:
            from infrastructure.database import AgentRun, AgentRunEvent, platform_database_enabled, platform_session

            if not platform_database_enabled():
                return
            with platform_session() as session:
                run = session.get(AgentRun, state["run_id"])
                if run:
                    run.status = state.get("status", run.status)
                    run.current_node = state.get("current_node", "")
                    if run.status in {"completed", "failed", "cancelled"}:
                        run.finished_at = datetime.now()
                    if run.status == "failed":
                        run.error_text = str(state.get("error", ""))
                    if run.status == "completed":
                        run.output_json = state.get("result") or {}
                    run.latency_ms = int(state.get("latency_ms", 0) or 0)
                session.add(
                    AgentRunEvent(
                        run_id=state["run_id"],
                        sequence=int(event.get("sequence", 0)),
                        event_type=event.get("type", "event"),
                        node=event.get("node", ""),
                        payload={key: value for key, value in event.items() if key not in {"type", "node", "sequence"}},
                    )
                )
        except Exception:
            return

    @staticmethod
    def _persist_status(state: dict[str, Any]) -> None:
        try:
            from infrastructure.database import AgentRun, platform_database_enabled, platform_session

            if not platform_database_enabled():
                return
            with platform_session() as session:
                run = session.get(AgentRun, state["run_id"])
                if run:
                    run.status = state.get("status", run.status)
                    run.finished_at = datetime.now()
        except Exception:
            return

    @staticmethod
    def _load_persisted(run_id: str) -> dict[str, Any] | None:
        """Restore run details from MySQL after Redis expiry or a restart."""
        try:
            from sqlalchemy import select

            from infrastructure.database import AgentRun, AgentRunEvent, platform_database_enabled, platform_session

            if not platform_database_enabled():
                return None
            with platform_session() as session:
                run = session.get(AgentRun, run_id)
                if run is None:
                    return None
                rows = session.scalars(
                    select(AgentRunEvent).where(AgentRunEvent.run_id == run_id).order_by(AgentRunEvent.sequence)
                ).all()
                events = []
                for row in rows:
                    events.append(
                        {
                            "type": row.event_type,
                            "run_id": run_id,
                            "node": row.node,
                            "sequence": row.sequence,
                            "timestamp": row.created_at.isoformat(),
                            **(row.payload or {}),
                        }
                    )
                return {
                    "run_id": run.id,
                    "workflow": run.workflow,
                    "user_id": run.user_id,
                    "organization_id": run.organization_id,
                    "status": run.status,
                    "current_node": run.current_node,
                    "input": run.input_json or {},
                    "result": run.output_json or {},
                    "error": run.error_text,
                    "latency_ms": run.latency_ms,
                    "token_count": run.token_count,
                    "events": events,
                    "cancelled": run.status == "cancelled",
                    "created_at": run.created_at.isoformat(),
                    "updated_at": (run.finished_at or run.created_at).isoformat(),
                }
        except Exception:
            return None


agent_run_store = AgentRunStore()
