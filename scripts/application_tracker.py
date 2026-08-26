#!/usr/bin/env python3
"""
Job Intelligence OS — Application Tracker
Tracks application status transitions and history.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
APPLICATIONS_PATH = DATA_DIR / "applications.json"

STATUSES = [
    "PREPARE",
    "READY_FOR_REVIEW",
    "SUBMIT",
    "APPLIED",
    "FOLLOW_UP",
    "INTERVIEW",
    "OFFER",
    "REJECTED",
    "EXPIRED",
    "BLOCKED",
]


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_applications() -> list[dict]:
    if APPLICATIONS_PATH.exists():
        try:
            return json.loads(APPLICATIONS_PATH.read_text(encoding="utf-8"))
        except Exception:
            return []
    return []


def save_applications(applications: list[dict]) -> None:
    DATA_DIR.mkdir(exist_ok=True)
    APPLICATIONS_PATH.write_text(
        json.dumps(applications, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def create_application(opportunity_id: str, resume_version: str, cover_letter: str = "") -> dict:
    applications = load_applications()
    application = {
        "application_id": opportunity_id,
        "opportunity_id": opportunity_id,
        "resume_version": resume_version,
        "cover_letter": cover_letter,
        "status": "PREPARE",
        "status_history": [{"status": "PREPARE", "at": _utcnow()}],
        "created_at": _utcnow(),
        "updated_at": _utcnow(),
    }
    applications.append(application)
    save_applications(applications)
    return application


def transition_status(opportunity_id: str, new_status: str) -> dict | None:
    applications = load_applications()
    for item in applications:
        if item.get("opportunity_id") == opportunity_id:
            if new_status not in STATUSES:
                raise ValueError(f"Invalid status: {new_status}")
            item["status"] = new_status
            item.setdefault("status_history", []).append({"status": new_status, "at": _utcnow()})
            item["updated_at"] = _utcnow()
            save_applications(applications)
            return item
    return None


def stats() -> dict:
    applications = load_applications()
    return {
        "total": len(applications),
        "by_status": {s: sum(1 for a in applications if a.get("status") == s) for s in STATUSES},
        "recent": applications[-20:],
    }


if __name__ == "__main__":
    print(json.dumps(stats(), ensure_ascii=False, indent=2))
