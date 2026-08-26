#!/usr/bin/env python3
"""
Job Intelligence OS — Updater
Runs scoring, freshness, and updates opportunity records.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

ROLE_KEYWORDS = [
    "AI Automation Specialist",
    "AI Automation Engineer",
    "AI Operations Specialist",
    "AI Ops Specialist",
    "AI Agent Specialist",
    "Agentic AI Specialist",
    "AI Workflow Automation Specialist",
    "AI Solutions Specialist",
    "AI Implementation Specialist",
    "AI Workflow Specialist",
    "Creative Technologist",
    "AI Creative Technologist",
    "Design Automation Specialist",
    "AI Creative Director",
    "AI Product Specialist",
    "AI Product Designer",
    "AI UX Designer",
    "Conversational UX Designer",
    "Marketing Automation Specialist",
    "AI Consultant",
    "Creative Operations Manager",
    "Brand Operations",
    "Digital Transformation Specialist",
    "AI Transformation Specialist",
]

SKILL_KEYWORDS = [
    "automation",
    "workflow",
    "agent",
    "agents",
    "agentic",
    "creative technologist",
    "creative operations",
    "design",
    "figma",
    "adobe",
    "marketing",
    "content",
    "product",
    "UX",
    "UI",
    "orchestration",
    "integration",
    "tooling",
    "no-code",
    "low-code",
    "LLM",
    "chatbot",
    "conversational",
    "brand",
    "strategy",
]

REMOTE_TOKENS = [
    "remote",
    "remoto",
    "remote-first",
    "async",
    "worldwide",
    "anywhere",
    "latam",
    "latin america",
    "usa",
    "united states",
    "canada",
    "europe",
    "europa",
]

AVOID_TOKENS = [
    "ML Engineer",
    "Data Scientist",
    "Backend Engineer",
    "machine learning research",
    "deep learning research",
    "relocation required",
    "on-site only",
    "presencial obrigatório",
    "phd",
    "postdoc",
]


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalize(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def _score_item(item: dict) -> dict:
    text = " ".join([
        item.get("role", ""),
        item.get("company", ""),
        item.get("location", ""),
        item.get("remote_type", ""),
        " ".join(item.get("requirements", []) or []),
        item.get("notes", ""),
        item.get("url", ""),
    ])
    text_n = _normalize(text).lower()
    role = _normalize(item.get("role", "")).lower()

    role_match = any(k.lower() in role for k in ROLE_KEYWORDS)
    semantic_match = any(k in text_n for k in SKILL_KEYWORDS)

    skill_score = 0
    if role_match:
        skill_score += 70
    if semantic_match:
        skill_score += 30
    skill_score = min(skill_score, 100)

    experience_score = 60
    if any(k in text_n for k in ["design", "creative", "marketing", "content", "product", "ux"]):
        experience_score += 20
    if any(k in text_n for k in ["automation", "workflow", "integration", "tooling", "operations"]):
        experience_score += 15
    if any(k in text_n for k in ["agent", "agents", "agentic", "orchestration", "autonomous"]):
        experience_score += 10
    experience_score = min(experience_score, 100)

    ai_score = 0
    if any(k in text_n for k in ["ai automation", "ai agent", "agentic ai", "ai ops", "ai operations", "ai workflow", "workflow automation"]):
        ai_score += 70
    if any(k in text_n for k in ["creative technologist", "creative operations", "ai creative"]):
        ai_score += 30
    ai_score = min(ai_score, 100)

    remote_score = 0
    if any(k in text_n for k in REMOTE_TOKENS):
        remote_score = 90
    if "hybrid" in text_n:
        remote_score = max(remote_score, 50)
    if "on-site" in text_n or "on site" in text_n:
        remote_score = min(remote_score, 20)
    remote_score = min(remote_score, 100)

    compensation_score = 40
    salary = item.get("salary", "")
    currency = (item.get("currency", "") or "").upper()
    if salary:
        compensation_score = 70
        numbers = re.findall(r"\d+(?:\.\d+)?", salary.replace(",", ""))
        if numbers:
            try:
                vals = [float(n) for n in numbers]
                avg = sum(vals) / len(vals)
                if currency == "USD" and avg >= 3000:
                    compensation_score = 100
                elif currency == "EUR" and avg >= 2700:
                    compensation_score = 95
                elif currency in ["USD", "EUR"] and avg > 0:
                    compensation_score = 80
            except Exception:
                pass
    if not salary:
        compensation_score = max(compensation_score, 40)

    location_score = 70
    location = item.get("location", "").lower()
    if any(k in location for k in ["remote", "anywhere", "worldwide", "latam", "united states", "canada", "europe", "europa"]):
        location_score = 100
    if "brasil" in location or "brazil" in location:
        location_score = max(location_score, 70)

    seniority_score = 70
    if any(k in role for k in ["specialist", "designer", "consultant", "coordinator", "lead"]):
        seniority_score = 85
    if any(k in role for k in ["manager", "head", "director", "senior"]):
        seniority_score = 95
    if any(k in role for k in ["junior", "intern", "trainee", "entry"]):
        seniority_score = 40

    strategic_score = 60
    if any(k in text_n for k in ["ai-native", "ai first", "ai-native", "startup", "platform", "agentic"]):
        strategic_score = 90
    if any(k in text_n for k in ["enterprise", "consulting", "agency"]):
        strategic_score = 75

    fit = round(
        skill_score * 0.30
        + experience_score * 0.20
        + ai_score * 0.15
        + remote_score * 0.10
        + compensation_score * 0.10
        + location_score * 0.05
        + seniority_score * 0.05
        + strategic_score * 0.05,
        2,
    )
    fit = int(max(0, min(100, fit)))
    avoid_hits = [t for t in AVOID_TOKENS if t.lower() in text_n]
    fit = max(0, fit - min(len(avoid_hits) * 8, 24))

    if fit >= 90:
        priority = "PRIORIDADE MÁXIMA"
    elif fit >= 80:
        priority = "ALTA"
    elif fit >= 70:
        priority = "BOA"
    elif fit >= 60:
        priority = "SECUNDÁRIA"
    else:
        priority = "DESCARTAR"

    delta_hours = 9999
    published = item.get("published_date", "")
    if published:
        try:
            published_dt = datetime.fromisoformat(published.replace("Z", "+00:00"))
            delta_hours = (datetime.now(timezone.utc) - published_dt).total_seconds() / 3600
        except Exception:
            pass
    if delta_hours < 24:
        freshness = "NOVÍSSIMA"
    elif delta_hours < 72:
        freshness = "RECENTE"
    elif delta_hours < 168:
        freshness = "ATIVA"
    elif delta_hours < 336:
        freshness = "ANTIGA"
    else:
        freshness = "BAIXA PRIORIDADE"

    return {
        "fit_score": fit,
        "priority": priority,
        "freshness": freshness,
        "components": {
            "skills": skill_score,
            "experience": experience_score,
            "ai_automation": ai_score,
            "remote": remote_score,
            "compensation": compensation_score,
            "location": location_score,
            "seniority": seniority_score,
            "strategic": strategic_score,
        },
        "avoid_hits": avoid_hits,
        "gaps_suggested": list({*avoid_hits}),
    }


ROOT = Path(__file__).resolve().parent.parent

def update() -> dict:
    opportunities_path = ROOT / "data" / "opportunities.json"
    scored_path = ROOT / "data" / "scored_opportunities.json"

    if not opportunities_path.exists():
        return {"error": "opportunities.json not found"}

    raw = json.loads(opportunities_path.read_text(encoding="utf-8"))
    results = []

    for item in raw:
        scored = _score_item(item)
        item["fit_score"] = scored["fit_score"]
        item["priority"] = scored["priority"]
        item["freshness"] = scored["freshness"]
        item["scored_at"] = _utcnow()
        item.setdefault("matches", [])
        item.setdefault("gaps", [])
        high_components = [k for k, v in scored.get("components", {}).items() if v >= 70]
        item["matches"] = list({*item.get("matches", []), *high_components})
        item["gaps"] = list({*item.get("gaps", []), *(scored.get("gaps_suggested") or [])})
        results.append(item)

    opportunities_path.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    scored_path.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")

    return {
        "updated": len(results),
        "path": str(scored_path),
        "stats": {
            "priority_max": sum(1 for x in results if x.get("priority") == "PRIORIDADE MÁXIMA"),
            "high": sum(1 for x in results if x.get("priority") == "ALTA"),
            "good": sum(1 for x in results if x.get("priority") == "BOA"),
            "secondary": sum(1 for x in results if x.get("priority") == "SECUNDÁRIA"),
            "discard": sum(1 for x in results if x.get("priority") == "DESCARTAR"),
        }
    }


if __name__ == "__main__":
    print(json.dumps(update(), ensure_ascii=False, indent=2))
