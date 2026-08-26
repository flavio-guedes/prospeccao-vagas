#!/usr/bin/env python3
"""
Job Intelligence OS — Local recurring runner
Executes collection, scoring, deduplication, database, notifications.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.collector import collect
from scripts.deduplicator import dedupe
from scripts.updater import update
from scripts.opportunity_database import OpportunityDatabase
from scripts.notifier import run as run_notifier


def main() -> dict:
    report = {
        "collector": None,
        "deduplicator": None,
        "updater": None,
        "notifier": None,
        "database": None,
    }

    try:
        report["collector"] = collect()
    except Exception as e:
        report["collector"] = {"error": str(e)}

    try:
        report["deduplicator"] = dedupe()
    except Exception as e:
        report["deduplicator"] = {"error": str(e)}

    try:
        report["updater"] = update()
    except Exception as e:
        report["updater"] = {"error": str(e)}

    try:
        db = OpportunityDatabase()
        report["database"] = db.stats()
    except Exception as e:
        report["database"] = {"error": str(e)}

    try:
        report["notifier"] = run_notifier()
    except Exception as e:
        report["notifier"] = {"error": str(e)}

    return report


if __name__ == "__main__":
    result = main()
    print(json.dumps(result, ensure_ascii=False, indent=2))
