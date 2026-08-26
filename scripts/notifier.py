#!/usr/bin/env python3
"""
Job Intelligence OS — macOS Notifier
Sends native macOS notifications for high-fit opportunities and important events.
"""
from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
SCORED_PATH = DATA_DIR / "scored_opportunities.json"
CONFIG_PATH = ROOT / "config" / "profile.json"


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_config() -> dict:
    if CONFIG_PATH.exists():
        try:
            return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def _load_opportunities() -> list[dict]:
    if SCORED_PATH.exists():
        try:
            return json.loads(SCORED_PATH.read_text(encoding="utf-8"))
        except Exception:
            return []
    return []


def notify(title: str, subtitle: str, message: str) -> bool:
    script = f'display notification "{message}" with title "{title}" subtitle "{subtitle}"'
    try:
        result = subprocess.run(["osascript", "-e", script], check=True, capture_output=True, text=True)
        return True
    except Exception:
        return False


def run() -> dict:
    config = _load_config()
    notif_cfg = config.get("notification", {})
    if not notif_cfg.get("macos", False):
        return {"notifications_enabled": False}

    opportunities = _load_opportunities()
    alerts = []
    high_threshold = notif_cfg.get("fit_high_threshold", 90)
    strategic_threshold = notif_cfg.get("fit_strategic_threshold", 80)

    for item in opportunities:
        fit = item.get("fit_score", 0)
        priority = item.get("priority", "")
        status = item.get("status", "DISCOVERED")
        role = item.get("role", "")
        company = item.get("company", "")
        salary = item.get("salary", "")
        currency = item.get("currency", "")
        remote = item.get("remote_type", "")
        url = item.get("url", "")

        if fit >= high_threshold or (fit >= strategic_threshold and priority in ["PRIORIDADE MÁXIMA", "ALTA"]):
            title = "HERMES — NOVA OPORTUNIDADE"
            subtitle = f"{role} — {company}"
            message = f"Remote: {remote} | Salary: {currency} {salary} | FIT: {fit}"
            ok = notify(title, subtitle, message)
            alerts.append({
                "opportunity_id": item.get("opportunity_id"),
                "role": role,
                "company": company,
                "fit_score": fit,
                "notified": ok,
            })

    return {
        "notifications_enabled": True,
        "thresholds": {
            "high": high_threshold,
            "strategic": strategic_threshold,
        },
        "alerts_sent": len(alerts),
        "alerts": alerts,
    }


if __name__ == "__main__":
    print(json.dumps(run(), ensure_ascii=False, indent=2))
