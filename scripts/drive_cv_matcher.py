#!/usr/bin/env python3
"""
Drive CV Library — matcher + selector.
Read-only helper on top of cv_library_index.json.
"""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
INDEX_PATH = ROOT / "data" / "cv_library_index.json"
PORTFOLIO_BASE = "https://flavio-guedes.github.io/portfolio"

AREA_KEYWORDS = {
    "MARKETING": ["marketing", "social media", "redator", "comunicação", "conteúdo", "content", "criação", "copywriter", "performance", "tráfego", "brand", "midia", "mídia"],
    "PRODUTO": ["product manager", "product owner", "product designer", "product marketing", "product operations", "gestor de projetos", "projeto", "pmm", "analista de produto"],
    "DESIGN": ["designer", "ux", "ui", "art director", "diretor de arte", "creative director", "diretor de criação", "product designer"],
    "IA": ["ia", "ai", "artificial intelligence", "automation", "automação", "machine learning", "llm", "agent", "agente", "ai product", "ai marketing"],
}

ROLE_KEYWORDS = {
    "MARKETING": ["marketing", "comunicação", "social media", "redator", "conteúdo", "content", "criação", "copywriter", "performance", "tráfego", "brand", "midia", "mídia", "coordenador de marketing", "coordenador de comunicação", "analista de marketing", "editor"],
    "PRODUTO": ["product manager", "product owner", "product designer", "product marketing", "product operations", "gestor de projetos", "pmm", "analista de produto", "projeto"],
    "DESIGN": ["designer", "ux", "ui", "art director", "diretor de arte", "creative director", "diretor de criação", "product designer"],
    "IA": ["ia", "ai", "artificial intelligence", "automation", "automação", "machine learning", "llm", "agent", "agente", "ai product", "ai marketing"],
}

ROLE_PRIORITY = {
    "Product Manager": "PRODUTO",
    "Product Owner": "PRODUTO",
    "Product Designer": "PRODUTO",
    "UX": "DESIGN",
    "UI": "DESIGN",
    "Designer": "DESIGN",
    "Art Director": "DESIGN",
    "Diretor de Arte": "DESIGN",
    "Diretor de Criação": "IA",
    "Social Media Manager": "MARKETING",
    "Redator": "MARKETING",
    "Coordenador de Marketing": "MARKETING",
    "Analista de Marketing": "MARKETING",
    "Gestor de Projetos": "PRODUTO",
    "Customer Success": "OUTROS",
    "Account Manager": "OUTROS",
    "Editor": "MARKETING",
    "Analista de Produto": "PRODUTO",
    "Produtor Audiovisual": "PRODUTO",
}

PORTFOLIO_MAP = {
    "MARKETING": f"{PORTFOLIO_BASE}/links.html",
    "PRODUTO": f"{PORTFOLIO_BASE}/links.html",
    "DESIGN": f"{PORTFOLIO_BASE}/links.html",
    "IA": f"{PORTFOLIO_BASE}/links.html",
}


@dataclass
class CVProfile:
    cv_id: str
    name: str
    area: str
    roles: list[str]
    seniority: str
    skills: list[str]
    url: str
    path: str = ""
    score: float = 0.0
    match_reason: str = ""
    alternative_cv: str = ""


def _load_index() -> dict[str, dict]:
    if not INDEX_PATH.exists():
        raise FileNotFoundError(f"Missing CV index: {INDEX_PATH}")
    data = json.loads(INDEX_PATH.read_text(encoding="utf-8"))
    return data.get("items", {})


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip().lower()


def _keyword_hits(text: str, keywords: list[str]) -> int:
    t = _normalize(text)
    return sum(1 for k in keywords if k in t)


def _title_to_area(title: str) -> str:
    t = _normalize(title)
    for role, area in ROLE_PRIORITY.items():
        if role.lower() in t:
            return area
    for area, keywords in AREA_KEYWORDS.items():
        if any(k in t for k in keywords):
            return area
    return "OUTROS"


def score_cv_for_job(cv: dict, job: dict) -> float:
    title = job.get("role") or job.get("title") or ""
    description = job.get("description") or job.get("body") or ""
    company = job.get("company") or ""
    requirements = " ".join(job.get("requirements") or [])
    text = f"{title} {description} {company} {requirements}"
    area = cv.get("area") or "OUTROS"
    keywords = AREA_KEYWORDS.get(area, []) + ROLE_KEYWORDS.get(area, [])
    hits = _keyword_hits(text, keywords)
    max_possible = max(len(keywords), 1)
    raw = (hits * 100.0) / max_possible

    exact_title_bonus = 0.0
    normalized_title = _normalize(title)
    if cv.get("name") and _normalize(cv.get("name", "")) in normalized_title:
        exact_title_bonus += 30.0
    for role in cv.get("roles", []):
        if _normalize(role) in normalized_title:
            exact_title_bonus += 25.0
            break

    bonus = exact_title_bonus
    if cv.get("seniority") == "SENIOR" and any(k in normalized_title for k in ["head", "diretor", "sr.", "senior", "lead"]):
        bonus += 6.0
    if cv.get("seniority") == "PLENO" and any(k in normalized_title for k in ["pleno", "mid", "coordenador", "analista"]):
        bonus += 5.0
    if cv.get("seniority") == "JUNIOR" and any(k in normalized_title for k in ["jr.", "junior", "estagiário", "intern"]):
        bonus += 4.0
    if cv.get("skills") and any(k in _normalize(text) for k in cv.get("skills", [])):
        bonus += 3.0
    return round(min(100.0, raw + bonus), 2)


def select_best_cv(job: dict) -> dict:
    index = _load_index()
    candidates = []
    for cv_id, item in index.items():
        s = score_cv_for_job(item, job)
        item["score"] = s
        candidates.append(item)
    candidates.sort(key=lambda x: (x.get("score", 0), _normalize(x.get("name", ""))), reverse=True)
    best = candidates[0] if candidates else {}
    alt = candidates[1] if len(candidates) > 1 else None
    alt_text = None
    if alt:
        alt_text = {
            "cv_id": alt.get("cv_id"),
            "name": alt.get("name"),
            "area": alt.get("area"),
            "url": alt.get("url"),
            "score": alt.get("score"),
        }
    return {
        "best_cv": {
            "cv_id": best.get("cv_id"),
            "name": best.get("name"),
            "area": best.get("area"),
            "url": best.get("url"),
            "score": best.get("score"),
            "reason": _build_reason(best, job),
        },
        "alternative_cv": alt_text,
        "portfolio_url": PORTFOLIO_MAP.get(best.get("area", ""), f"{PORTFOLIO_BASE}/links.html"),
    }


def _build_reason(cv: dict, job: dict) -> str:
    title = job.get("role") or job.get("title") or ""
    area = cv.get("area") or ""
    reasons = [f"Match principal: área {area}"]
    if title:
        reasons.append(f"Vaga: {title}")
    if cv.get("skills"):
        matched = [s for s in cv.get("skills", []) if s in _normalize(title)]
        if matched:
            reasons.append(f"Skills alinhadas: {', '.join(matched[:5])}")
    return ". ".join(reasons)


if __name__ == "__main__":
    sample = {"role": "Product Manager", "company": "Tech", "location": "São Paulo", "description": "Produto digital, growth, AI product."}
    print(json.dumps(select_best_cv(sample), ensure_ascii=False, indent=2))
