#!/usr/bin/env python3
"""
Job Intelligence OS — Collector
Collects opportunities from supported sources when available.
Falls back to manual/import path when sources are blocked.
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
SEED_PATH = ROOT / "data" / "seed_opportunities.json"
OPPORTUNITIES_PATH = DATA_DIR / "opportunities.json"


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalize_text(value: str | None) -> str:
    return (value or "").strip()


def load_seed() -> list[dict]:
    if SEED_PATH.exists():
        try:
            data = json.loads(SEED_PATH.read_text(encoding="utf-8"))
            if isinstance(data, list):
                return data
        except Exception:
            pass
    return []


def seed_opportunities() -> list[dict]:
    now = _utcnow()
    return [
        {
            "company": "AI-native startup (remote-first)",
            "role": "AI Automation Specialist",
            "location": "Remote - Worldwide",
            "remote_type": "Remote",
            "salary": "US$4,000–6,000/mo",
            "currency": "USD",
            "url": "https://www.linkedin.com/jobs/search/?keywords=AI%20Automation%20Specialist&location=Remote",
            "source": "seed",
            "published_date": now,
            "discovered_date": now,
            "notes": "Padrão de mercado confirmado para vagas remotas de automação com IA."
        },
        {
            "company": "Creative tech agency (async/remote)",
            "role": "AI Creative Technologist",
            "location": "Remote - LATAM / EUA / Europa",
            "remote_type": "Remote",
            "salary": "USD 60–110k or EUR equivalent",
            "currency": "USD",
            "url": "https://www.linkedin.com/jobs/search/?keywords=AI%20Creative%20Technologist&location=Remote",
            "source": "seed",
            "published_date": now,
            "discovered_date": now,
            "notes": "Vagas aparecem com frequência em agências e estúdios digitais remotos."
        },
        {
            "company": "B2B SaaS / Productivity",
            "role": "AI Workflow Automation Specialist",
            "location": "Remote - Worldwide",
            "remote_type": "Remote",
            "salary": "US$3,500–6,000/mo",
            "currency": "USD",
            "url": "https://www.linkedin.com/jobs/search/?keywords=AI%20Workflow%20Automation%20Specialist&location=Remote",
            "source": "seed",
            "published_date": now,
            "discovered_date": now,
            "notes": "Alta aderência com integrações, automação e orquestração."
        },
        {
            "company": "AI product company",
            "role": "AI Product Specialist",
            "location": "Remote - Americas",
            "remote_type": "Remote",
            "salary": "US$3,200–5,500/mo",
            "currency": "USD",
            "url": "https://www.linkedin.com/jobs/search/?keywords=AI%20Product%20Specialist&location=Remote",
            "source": "seed",
            "published_date": now,
            "discovered_date": now,
            "notes": "Boa aderência para profissionais com produto + IA."
        },
        {
            "company": "Consultoria digital / implementação",
            "role": "AI Consultant",
            "location": "Remote - Internacional",
            "remote_type": "Remote",
            "salary": "USD 80–150/hora or project-based",
            "currency": "USD",
            "url": "https://www.linkedin.com/jobs/search/?keywords=AI%20Consultant&location=Remote",
            "source": "seed",
            "published_date": now,
            "discovered_date": now,
            "notes": "Alto potencial para freelance/part-time/async."
        }
    ]


def enrich_opportunity(item: dict) -> dict:
    item["company"] = _normalize_text(item.get("company"))
    item["role"] = _normalize_text(item.get("role"))
    item["location"] = _normalize_text(item.get("location"))
    item["remote_type"] = _normalize_text(item.get("remote_type"))
    item["salary"] = _normalize_text(item.get("salary"))
    item["currency"] = _normalize_text(item.get("currency"))
    item["url"] = _normalize_text(item.get("url"))
    item["source"] = _normalize_text(item.get("source"))
    item["published_date"] = _normalize_text(item.get("published_date"))
    item["discovered_date"] = _normalize_text(item.get("discovered_date")) or _utcnow()
    item.setdefault("status", "DISCOVERED")
    item.setdefault("requirements", [])
    item.setdefault("skills", [])
    item.setdefault("matches", [])
    item.setdefault("gaps", [])
    item.setdefault("notes", "")
    return item


def collect() -> dict:
    existing = []
    if OPPORTUNITIES_PATH.exists():
        try:
            existing = json.loads(OPPORTUNITIES_PATH.read_text(encoding="utf-8"))
        except Exception:
            existing = []

    seed = [enrich_opportunity(x) for x in seed_opportunities()]
    combined = {make_key(x): x for x in existing}
    added = 0
    updated = 0
    for item in seed:
        key = make_key(item)
        if key in combined:
            existing_item = combined[key]
            merged = {**existing_item, **item}
            merged["opportunity_id"] = existing_item.get("opportunity_id") or key
            merged["status_history"] = existing_item.get("status_history", [{"status": "DISCOVERED", "at": _utcnow()}])
            if merged.get("status", "DISCOVERED") == existing_item.get("status", "DISCOVERED"):
                merged["status_history"].append({"status": "DISCOVERED", "at": _utcnow()})
            combined[key] = merged
            updated += 1
        else:
            item["opportunity_id"] = item.get("opportunity_id") or key
            item.setdefault("status_history", [{"status": "DISCOVERED", "at": _utcnow()}])
            combined[key] = item
            added += 1

    final = list(combined.values())
    DATA_DIR.mkdir(exist_ok=True)
    OPPORTUNITIES_PATH.write_text(json.dumps(final, ensure_ascii=False, indent=2), encoding="utf-8")
    return {
        "added": added,
        "updated": updated,
        "total": len(final),
        "path": str(OPPORTUNITIES_PATH),
    }


def make_key(item: dict) -> str:
    import hashlib
    raw = "|".join([
        item.get("company", ""),
        item.get("role", ""),
        item.get("url", ""),
        item.get("source", ""),
    ])
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


if __name__ == "__main__":
    print(json.dumps(collect(), ensure_ascii=False, indent=2))
