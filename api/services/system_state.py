from __future__ import annotations

import json
import tempfile
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any


class ApiStateStore:
    def __init__(self, path: str | Path = "data/processed/api_state.json") -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self._write_state({"activities": [], "ingestion_jobs": []})

    def list_activities(self) -> list[dict[str, Any]]:
        state = self._read_state()
        activities = state.get("activities", [])
        return activities if isinstance(activities, list) else []

    def record_activity(
        self,
        *,
        event_type: str,
        description: str,
        metadata: dict[str, Any] | None = None,
        timestamp: str | None = None,
    ) -> dict[str, Any]:
        state = self._read_state()
        activities = state.setdefault("activities", [])
        event = {
            "id": f"activity-{uuid.uuid4().hex[:12]}",
            "type": event_type,
            "description": description,
            "timestamp": timestamp or datetime.utcnow().isoformat(),
            "metadata": metadata or {},
        }
        activities.insert(0, event)
        state["activities"] = activities[:200]
        self._write_state(state)
        return event

    def list_ingestion_jobs(self) -> list[dict[str, Any]]:
        state = self._read_state()
        jobs = state.get("ingestion_jobs", [])
        return jobs if isinstance(jobs, list) else []

    def save_ingestion_job(self, job: dict[str, Any]) -> dict[str, Any]:
        state = self._read_state()
        jobs = state.setdefault("ingestion_jobs", [])
        existing_index = next((i for i, item in enumerate(jobs) if item.get("id") == job.get("id")), None)
        if existing_index is None:
            jobs.insert(0, job)
        else:
            jobs[existing_index] = job
        state["ingestion_jobs"] = jobs[:200]
        self._write_state(state)
        return job

    def get_ingestion_job(self, job_id: str) -> dict[str, Any] | None:
        for item in self.list_ingestion_jobs():
            if item.get("id") == job_id:
                return item
        return None

    def delete_ingestion_job(self, job_id: str) -> dict[str, Any] | None:
        state = self._read_state()
        jobs = state.get("ingestion_jobs", [])
        if not isinstance(jobs, list):
            return None

        removed: dict[str, Any] | None = None
        kept_jobs: list[dict[str, Any]] = []
        for item in jobs:
            if item.get("id") == job_id and removed is None:
                removed = item
                continue
            kept_jobs.append(item)

        if removed is None:
            return None

        state["ingestion_jobs"] = kept_jobs
        self._write_state(state)
        return removed

    def _read_state(self) -> dict[str, Any]:
        try:
            raw = self.path.read_text(encoding="utf-8")
            parsed = json.loads(raw)
            return parsed if isinstance(parsed, dict) else {}
        except (FileNotFoundError, json.JSONDecodeError):
            return {"activities": [], "ingestion_jobs": []}

    def _write_state(self, state: dict[str, Any]) -> None:
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            delete=False,
            dir=self.path.parent,
            suffix=".json",
        ) as fh:
            json.dump(state, fh, ensure_ascii=False, indent=2)
            temp_path = Path(fh.name)
        temp_path.replace(self.path)
