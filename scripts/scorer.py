#!/usr/bin/env python3
"""
Job Intelligence OS — Opportunity Scorer
Calculates fit score, freshness, and priority classification.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

try:
    from scripts.opportunity_database import _utcnow
except Exception:
    def _utcnow() -> str:
        return datetime.now(timezone.utc).isoformat()

ROOT = Path(__file__).resolve().parent.parent
PROFILE_PATH = ROOT / "config" / "profile.json"

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


def _load_profile():
    if PROFILE_PATH.exists():
        return json.loads(PROFILE_PATH.read_text(encoding="utf-8"))
    return {}


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def score_opportunity(opportunity: dict) -> dict:
    profile = _load_profile()
    text = " ".join([
        opportunity.get("role", ""),
        opportunity.get("company", ""),
        opportunity.get("location", ""),
        opportunity.get("remote_type", ""),
        opportunity.get("requirements", []) and " ".join(opportunity.get("requirements", [])) or "",
        opportunity.get("notes", ""),
        opportunity.get("url", ""),
    ])
    text_n = _normalize(text).lower()

    role = _normalize(opportunity.get("role", "")).lower()
    role_match = any(k.lower() in role for k in ROLE_KEYWORDS)
    semantic_match = any(k in text_n for k in SKILL_KEYWORDS)

    # Weights from profile if present
    weights = profile.get("fit_score", {})
    skills_weight = weights.get("skills_weight", 0.30)
    experience_weight = weights.get("experience_weight", 0.20)
    ai_weight = weights.get("ai_automation_agents_weight", 0.15)
    remote_weight = weights.get("remote_compatibility_weight", 0.10)
    compensation_weight = weights.get("compensation_weight", 0.10)
    location_weight = weights.get("location_weight", 0.05)
    seniority_weight = weights.get("seniority_weight", 0.05)
    strategic_weight = weights.get("strategic_value_weight", 0.05)

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
    salary = opportunity.get("salary", "")
    currency = (opportunity.get("currency", "") or "").upper()
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
    location = opportunity.get("location", "").lower()
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
        skill_score * skills_weight
        + experience_score * experience_weight
        + ai_score * ai_weight
        + remote_score * remote_weight
        + compensation_score * compensation_weight
        + location_score * location_weight
        + seniority_score * seniority_weight
        + strategic_score * strategic_weight,
        2,
    )
    fit = int(max(0, min(100, fit)))

    # Avoid penalize
    avoid_hits = [t for t in AVOID_TOKENS if t.lower() in text_n]
    gap_penalty = min(len(avoid_hits) * 8, 24)
    fit = max(0, fit - gap_penalty)

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

    freshness = classify_freshness(opportunity.get("published_date", ""))

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
        "gaps_suggested": list({h for h in avoid_hits}),
    }


def classify_freshness(published_date: str) -> str:
    if not published_date:
        return "UNKNOWN"
    try:
        published = datetime.fromisoformat(published_date.replace("Z", "+00:00"))
    except Exception:
        return "UNKNOWN"
    delta_hours = (datetime.now(timezone.utc) - published).total_seconds() / 3600
    if delta_hours < 24:
        return "NOVÍSSIMA"
    if delta_hours < 72:
        return "RECENTE"
    if delta_hours < 168:
        return "ATIVA"
    if delta_hours < 336:
        return "ANTIGA"
    return "BAIXA PRIORIDADE"


if __name__ == "__main__":
    sample = {
        "role": "AI Automation Specialist",
        "company": "Acme",
        "location": "Remote - Worldwide",
        "remote_type": "Remote",
        "salary": "US$4k–6k",
        "currency": "USD",
        "requirements": ["automation", "workflow", "AI"],
        "published_date": _utcnow(),
    }
    print(json.dumps(score_opportunity(sample), ensure_ascii=False, indent=2))
