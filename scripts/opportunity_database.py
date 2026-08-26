#!/usr/bin/env python3
"""
Job Intelligence OS — Opportunity Database
Manages opportunities, scoring, deduplication, freshness, and status transitions.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
DATA_DIR.mkdir(exist_ok=True)

OPPORTUNITIES_PATH = DATA_DIR / "opportunities.json"
APPLICATIONS_PATH = DATA_DIR / "applications.json"
HISTORY_PATH = DATA_DIR / "history.json"
SOURCES_PATH = DATA_DIR / "sources.json"


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def _default_opportunity() -> dict:
    return {
        "opportunity_id": "",
        "company": "",
        "role": "",
        "location": "",
        "remote_type": "",
        "salary": "",
        "currency": "",
        "url": "",
        "source": "",
        "published_date": "",
        "discovered_date": _utcnow(),
        "fit_score": 0,
        "freshness": "",
        "skills": [],
        "requirements": [],
        "matches": [],
        "gaps": [],
        "strategic_value": "",
        "status": "DISCOVERED",
        "status_history": [{"status": "DISCOVERED", "at": _utcnow()}],
        "notes": "",
    }


class OpportunityDatabase:
    def __init__(self) -> None:
        self.opportunities: list[dict] = []
        self.applications: list[dict] = []
        self.history: list[dict] = []
        self.sources: dict = {}
        self._load()

    def _load(self) -> None:
        for path, attr, default in [
            (OPPORTUNITIES_PATH, "opportunities", []),
            (APPLICATIONS_PATH, "applications", []),
            (HISTORY_PATH, "history", []),
            (SOURCES_PATH, "sources", {}),
        ]:
            if path.exists():
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        setattr(self, attr, json.load(f))
                except Exception:
                    setattr(self, attr, default)

    def save(self) -> None:
        OPPORTUNITIES_PATH.write_text(
            json.dumps(self.opportunities, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        APPLICATIONS_PATH.write_text(
            json.dumps(self.applications, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        HISTORY_PATH.write_text(
            json.dumps(self.history, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        SOURCES_PATH.write_text(
            json.dumps(self.sources, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    def _dedupe_key(self, opportunity: dict) -> str:
        raw = "|".join(
            [
                opportunity.get("company", ""),
                opportunity.get("role", ""),
                opportunity.get("url", ""),
                opportunity.get("source", ""),
            ]
        )
        return _hash(raw)

    def add_or_update(self, opportunity: dict) -> tuple[bool, str]:
        key = self._dedupe_key(opportunity)
        for idx, item in enumerate(self.opportunities):
            if self._dedupe_key(item) == key:
                merged = {**item, **opportunity}
                merged["opportunity_id"] = item.get("opportunity_id") or key
                merged["status_history"] = item.get("status_history", [])
                self.opportunities[idx] = merged
                self._record_history("UPDATED", merged.get("opportunity_id"), key)
                return False, merged.get("opportunity_id", key)

        opportunity["opportunity_id"] = opportunity.get("opportunity_id") or key
        opportunity.setdefault("status_history", [{"status": "DISCOVERED", "at": _utcnow()}])
        opportunity.setdefault("discovered_date", _utcnow())
        self.opportunities.append(opportunity)
        self._record_history("DISCOVERED", opportunity["opportunity_id"], key)
        return True, opportunity["opportunity_id"]

    def set_status(self, opportunity_id: str, status: str) -> None:
        for item in self.opportunities:
            if item.get("opportunity_id") == opportunity_id:
                item["status"] = status
                item.setdefault("status_history", []).append({"status": status, "at": _utcnow()})
                self._record_history("STATUS_CHANGE", opportunity_id, status)
                break

    def get_by_id(self, opportunity_id: str) -> dict | None:
        for item in self.opportunities:
            if item.get("opportunity_id") == opportunity_id:
                return item
        return None

    def search(self, query: str = "", source: str = "", status: str = "", min_fit: int = 0) -> list[dict]:
        result = []
        q = query.lower()
        for item in self.opportunities:
            text = json.dumps(item, ensure_ascii=False).lower()
            if q and q not in text:
                continue
            if source and item.get("source", "").lower() != source.lower():
                continue
            if status and item.get("status", "").lower() != status.lower():
                continue
            if min_fit and item.get("fit_score", 0) < min_fit:
                continue
            result.append(item)
        return result

    def _record_history(self, event: str, target: str, detail: str) -> None:
        self.history.append(
            {
                "event": event,
                "target": str(target),
                "detail": str(detail),
                "at": _utcnow(),
            }
        )
        self.history = self.history[-2000:]

    def stats(self) -> dict:
        opportunities = self.opportunities
        total = len(opportunities)
        high_fit = sum(1 for o in opportunities if o.get("fit_score", 0) >= 80)
        remote = sum(1 for o in opportunities if "remote" in json.dumps(o, ensure_ascii=False).lower())
        today = datetime.now(timezone.utc).date().isoformat()
        new_today = sum(
            1 for o in opportunities if o.get("discovered_date", "").startswith(today)
        )
        return {
            "total": total,
            "high_fit": high_fit,
            "remote": remote,
            "new_today": new_today,
        }


if __name__ == "__main__":
    db = OpportunityDatabase()
    print(json.dumps({"stats": db.stats(), "count": len(db.opportunities)}, ensure_ascii=False))
