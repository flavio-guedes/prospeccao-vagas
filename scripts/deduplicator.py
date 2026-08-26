#!/usr/bin/env python3
"""
Job Intelligence OS — Deduplicator
Merges duplicate opportunities and preserves source lineage.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
OPPORTUNITIES_PATH = DATA_DIR / "opportunities.json"


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def _key(item: dict) -> str:
    raw = "|".join([
        item.get("company", ""),
        item.get("role", ""),
        item.get("url", ""),
        item.get("source", ""),
    ])
    return _hash(raw)


def dedupe() -> dict:
    if not OPPORTUNITIES_PATH.exists():
        return {"error": "opportunities.json not found"}

    raw = json.loads(OPPORTUNITIES_PATH.read_text(encoding="utf-8"))
    merged: dict[str, dict] = {}
    for item in raw:
        k = _key(item)
        if k in merged:
            existing = merged[k]
            merged[k] = {**existing, **item}
            merged[k]["opportunity_id"] = existing.get("opportunity_id") or k
            merged[k]["status_history"] = existing.get("status_history", [])
            merged[k]["status_history"].append({"status": "MERGED", "at": _utcnow()})
        else:
            item["opportunity_id"] = item.get("opportunity_id") or k
            item.setdefault("status_history", [{"status": "DISCOVERED", "at": _utcnow()}])
            merged[k] = item

    final = list(merged.values())
    OPPORTUNITIES_PATH.write_text(json.dumps(final, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"before": len(raw), "after": len(final), "removed": len(raw) - len(final)}

if __name__ == "__main__":
    print(json.dumps(dedupe(), ensure_ascii=False, indent=2))
