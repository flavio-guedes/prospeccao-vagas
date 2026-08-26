#!/usr/bin/env python3
"""
Career OS Pipeline — Job Radar + CV Library + Gmail preparation + Follow-up + Learning.
Read-only preparation layer. Does not send e-mails automatically.
"""
from __future__ import annotations

import csv
import json
import re
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
INDEX_PATH = DATA_DIR / "cv_library_index.json"
SENDS_PATH = DATA_DIR / "send_registry.json"
LEARNING_PATH = DATA_DIR / "learning_stats.json"
FOLLOWUPS_PATH = DATA_DIR / "followups.json"

PORTFOLIO_BASE = "https://flavio-guedes.github.io/portfolio"


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _date(days: int) -> str:
    return (datetime.now(timezone.utc) + timedelta(days=days)).date().isoformat()


def _load_json(path: Path, default: Any) -> Any:
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return default
    return default


def _save_json(path: Path, data: Any) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _load_cv_index() -> dict[str, dict]:
    if not INDEX_PATH.exists():
        return {}
    data = _load_json(INDEX_PATH, {})
    return data.get("items", {})


@dataclass
class SendRecord:
    send_id: str
    date: str = field(default_factory=_utcnow)
    recipient: str = ""
    company: str = ""
    job: str = ""
    cv_id: str = ""
    cv_name: str = ""
    portfolio_url: str = ""
    subject: str = ""
    message: str = ""
    source: str = ""
    status: str = "draft"
    followup_d3: str = ""
    followup_d7: str = ""
    outcome: str = ""
    responded: bool = False


def _generate_message(contact: dict, job: dict, cv: dict, portfolio_url: str) -> str:
    company = contact.get("company") or job.get("company") or ""
    role = contact.get("role") or job.get("role") or ""
    area = contact.get("area") or cv.get("area") or ""
    portfolio = portfolio_url or f"{PORTFOLIO_BASE}/links.html"
    cv_name = cv.get("name", "")
    context_parts = []
    if company:
        context_parts.append(f"na {company}")
    if role:
        context_parts.append(f"para a posição {role}")
    context = " ".join(context_parts) if context_parts else "para a oportunidade"
    text = (
        f"Olá, estou interessado em {context}. "
        f"Tenho perfil alinhado a {area.lower()} e utilizei o CV {cv_name}. "
        f"Veja também meu portfólio: {portfolio}. "
        f"Aguardo o próximo passo."
    )
    return text


def select_best_cv(job: dict) -> dict:
    try:
        from drive_cv_matcher import select_best_cv as _select_best_cv
        return _select_best_cv(job)
    except Exception:
        return {
            "best_cv": {"cv_id": None, "name": None, "area": None, "url": None, "score": None, "reason": "Índice indisponível."},
            "alternative_cv": None,
            "portfolio_url": f"{PORTFOLIO_BASE}/links.html",
        }


def enrich_contacts(contacts: list[dict], job: dict) -> list[dict]:
    enriched = []
    for c in contacts:
        match = select_best_cv(job)
        best = match.get("best_cv") or {}
        portfolio = match.get("portfolio_url") or f"{PORTFOLIO_BASE}/links.html"
        item = {
            **c,
            "cv_id": best.get("cv_id"),
            "cv_name": best.get("name"),
            "cv_score": best.get("score"),
            "cv_reason": best.get("reason"),
            "portfolio_url": portfolio,
            "personalized_message": _generate_message(c, job, best, portfolio),
        }
        enriched.append(item)
    return enriched


def prepare_send_batch(contacts: list[dict]) -> dict:
    registry = _load_json(SENDS_PATH, [])
    now_ts = datetime.now(timezone.utc)
    records = []
    for idx, c in enumerate(contacts, 1):
        rec = SendRecord(
            send_id=f"{now_ts.strftime('%Y%m%d%H%M%S')}-{idx:03d}",
            recipient=c.get("email", ""),
            company=c.get("company", ""),
            job=c.get("role", ""),
            cv_id=c.get("cv_id", ""),
            cv_name=c.get("cv_name", ""),
            portfolio_url=c.get("portfolio_url", ""),
            subject=f"Candidatura — {c.get('role') or 'Oportunidade'}",
            message=c.get("personalized_message", ""),
            source=c.get("source", ""),
            status="prepared",
            followup_d3=_date(3),
            followup_d7=_date(7),
        )
        records.append(asdict(rec))
    registry.extend(records)
    _save_json(SENDS_PATH, registry)
    return {"prepared": len(records), "records": records}


def export_gmail_batch(records: list[dict], path: Path | None = None) -> Path:
    if path is None:
        path = DATA_DIR / f"gmail_batch_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.csv"
    fieldnames = ["email", "firstname", "lastname", "company", "role", "area", "job_url", "subject", "message", "cv_name", "portfolio_url", "followup_d3", "followup_d7"]
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in records:
            writer.writerow({
                "email": r.get("recipient", ""),
                "firstname": "",
                "lastname": "",
                "company": r.get("company", ""),
                "role": r.get("job", ""),
                "area": "",
                "job_url": r.get("job_url", ""),
                "subject": r.get("subject", ""),
                "message": r.get("message", ""),
                "cv_name": r.get("cv_name", ""),
                "portfolio_url": r.get("portfolio_url", ""),
                "followup_d3": r.get("followup_d3", ""),
                "followup_d7": r.get("followup_d7", ""),
            })
    return path


def record_outcome(send_id: str, outcome: str, responded: bool = False, notes: str = "") -> dict:
    registry = _load_json(SENDS_PATH, [])
    for item in registry:
        if item.get("send_id") == send_id:
            item["outcome"] = outcome
            item["responded"] = bool(responded)
            item["outcome_notes"] = notes
            item["outcome_at"] = _utcnow()
            _save_json(SENDS_PATH, registry)
            _update_learning(item)
            return item
    return {}


def _update_learning(record: dict) -> None:
    stats = _load_json(LEARNING_PATH, {"by_cv": {}, "by_area": {}, "by_job_type": {}})
    cv_name = record.get("cv_name") or "UNKNOWN"
    area = (record.get("company") or "UNKNOWN")
    job_type = record.get("job") or "UNKNOWN"
    responded = bool(record.get("responded"))

    def _bump(bucket: dict, key: str) -> None:
        bucket.setdefault(key, {"sent": 0, "responded": 0})
        bucket[key]["sent"] += 1
        if responded:
            bucket[key]["responded"] += 1

    _bump(stats["by_cv"], cv_name)
    _bump(stats["by_area"], area)
    _bump(stats["by_job_type"], job_type)
    _save_json(LEARNING_PATH, stats)


def learning_summary() -> dict:
    stats = _load_json(LEARNING_PATH, {"by_cv": {}, "by_area": {}, "by_job_type": {}})
    registry = _load_json(SENDS_PATH, [])
    return {
        "stats": stats,
        "total_sends": len(registry),
        "responded": sum(1 for r in registry if r.get("responded")),
    }


def followup_summary() -> dict:
    registry = _load_json(SENDS_PATH, [])
    today = datetime.now(timezone.utc).date().isoformat()
    due_d3 = [r for r in registry if r.get("followup_d3") == today and not r.get("responded") and r.get("status") != "followup_sent_d3"]
    due_d7 = [r for r in registry if r.get("followup_d7") == today and not r.get("responded") and r.get("status") not in ("followup_sent_d3", "followup_sent_d7")]
    return {
        "due_d3": due_d3,
        "due_d7": due_d7,
    }


if __name__ == "__main__":
    print(json.dumps({
        "learning": learning_summary(),
        "followups": followup_summary(),
    }, ensure_ascii=False, indent=2))
