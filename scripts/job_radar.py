#!/usr/bin/env python3
"""
Job Radar — coletor público de vagas e e-mails explícitos.
Regra: apenas dados públicos, apenas e-mails explicitamente publicados.
Sem inferência, sem bypass, sem scraping de áreas protegidas.
"""
from __future__ import annotations

import csv
import hashlib
import json
import os
import re
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
BATCH_DIR = DATA_DIR / "batches"
REGISTRY_PATH = DATA_DIR / "job_radar_registry.json"
BATCH_DIR.mkdir(parents=True, exist_ok=True)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; JobRadar/1.0; contact: flavioguedesmkt@gmail.com)",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.7",
}

CATEGORIES = {
    "MARKETING": [
        "marketing", "comunicação", "social media", "conteúdo", "content",
        "copywriter", "criação", "creative", "diretor de arte", "design",
        "performance", "tráfego", "midia", "mídia", "brand", "conteúdo",
    ],
    "PRODUTO": [
        "product manager", " pm ", "product owner", " po ", "product designer",
        "ux", "ui", "product marketing", "product operations", "growth",
        "produto", "pmm",
    ],
    "DESIGN": [
        "designer", "ux", "ui", "product designer", "design lead",
        "art director", "creative director", "diretor de arte",
    ],
    "IA": [
        "ia", "ai", "artificial intelligence", "ai product", "ai agent",
        "automation", "automação", "machine learning", "llm", "gênia",
    ],
}

CONTACT_HINTS = [
    "e-mail", "email", "mail", "contato", "contact", "recrutamento",
    "rh", "talentos", "careers", "apply", "candidatura",
]

EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")
BAD_EMAIL_TOKENS = [
    ".png", ".jpg", ".jpeg", ".gif", ".svg", ".css", ".js", ".json",
    "example.com", "sentry", "webpack", "github.com", "githubusercontent",
    "googleapis", "googleusercontent", "gravatar", "placeholder",
    ".edu.br", ".gov.br", "@2x", "@3x",
]


@dataclass
class Contact:
    email: str
    firstname: str = ""
    lastname: str = ""
    company: str = ""
    role: str = ""
    area: str = ""
    job_url: str = ""
    source: str = ""
    contact_type: str = "email"
    published_date: str = ""
    discovered_at: str = field(default_factory=lambda: _utcnow())

    def to_csv_dict(self) -> dict:
        return {
            "email": self.email,
            "firstname": self.firstname,
            "lastname": self.lastname,
            "company": self.company,
            "role": self.role,
            "area": self.area,
            "job_url": self.job_url,
            "source": self.source,
            "contact_type": self.contact_type,
            "published_date": self.published_date,
        }


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _dedupe_key(contact: Contact) -> str:
    raw = "|".join([
        contact.email.lower().strip(),
        contact.company.lower().strip(),
        contact.role.lower().strip(),
        contact.job_url.lower().strip(),
    ])
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def _classify_area(text: str) -> str:
    t = (text or "").lower()
    for area, keywords in CATEGORIES.items():
        if any(k in t for k in keywords):
            return area
    return "OUTROS"


def _is_explicit_email_context(text: str, email: str) -> bool:
    if any(tok in email.lower() for tok in BAD_EMAIL_TOKENS):
        return False
    t = (text or "").lower()
    return any(h in t for h in CONTACT_HINTS)


def _extract_emails_from_text(text: str, context: str) -> list[str]:
    found = []
    for match in EMAIL_RE.findall(text or ""):
        if _is_explicit_email_context(context, match):
            found.append(match)
    return list(dict.fromkeys(found))


def _request(url: str, *, timeout: int = 25) -> requests.Response | None:
    try:
        return requests.get(url, headers=HEADERS, timeout=timeout, allow_redirects=True)
    except requests.RequestException:
        return None


def _clean(s: str | None) -> str:
    return (s or "").strip()


def _extract_contacts_from_job_page(url: str, area: str, source: str) -> Iterable[Contact]:
    resp = _request(url)
    if not resp or resp.status_code != 200 or "text/html" not in resp.headers.get("Content-Type", ""):
        return []
    soup = BeautifulSoup(resp.text, "html.parser")
    text = soup.get_text(separator=" ")
    emails = _extract_emails_from_text(text, text)
    if not emails:
        return []
    title = _clean(soup.title.get_text()) if soup.title else ""
    company_guess = title.split("–")[0].split("-")[0].strip() if title else source
    role_guess = title
    for email in emails:
        yield Contact(
            email=email,
            company=company_guess,
            role=role_guess,
            area=area or _classify_area(title + " " + text),
            job_url=url,
            source=source,
            published_date=datetime.now(timezone.utc).date().isoformat(),
        )


def _collect_gupy(keyword: str, location: str, area: str) -> Iterable[Contact]:
    url = f"https://www.gupy.io/vagas?q={requests.utils.quote(keyword)}&l={requests.utils.quote(location)}"
    resp = _request(url)
    if not resp or resp.status_code != 200:
        return []
    soup = BeautifulSoup(resp.text, "html.parser")
    links = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if "/vagas/" in href or "/oportunidade/" in href or "/vaga/" in href:
            links.append(urljoin(url, href))
    seen = set()
    for link in list(dict.fromkeys(links))[:25]:
        if link in seen:
            continue
        seen.add(link)
        yield from _extract_contacts_from_job_page(link, area, "gupy")


def _collect_prh(keyword: str, location: str, area: str) -> Iterable[Contact]:
    url = f"https://www.prh.com/vagas?q={requests.utils.quote(keyword)}&l={requests.utils.quote(location)}"
    resp = _request(url)
    if not resp or resp.status_code != 200:
        return []
    soup = BeautifulSoup(resp.text, "html.parser")
    links = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if "vaga" in href or "oportunidade" in href or "career" in href:
            links.append(urljoin(url, href))
    seen = set()
    for link in list(dict.fromkeys(links))[:25]:
        if link in seen:
            continue
        seen.add(link)
        yield from _extract_contacts_from_job_page(link, area, "prh")


def _collect_catho(keyword: str, location: str, area: str) -> Iterable[Contact]:
    url = f"https://www.catho.com.br/vagas?q={requests.utils.quote(keyword)}&l={requests.utils.quote(location)}"
    resp = _request(url)
    if not resp or resp.status_code != 200:
        return []
    soup = BeautifulSoup(resp.text, "html.parser")
    links = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if "/vagas/" in href or "/emprego/" in href:
            links.append(urljoin(url, href))
    seen = set()
    for link in list(dict.fromkeys(links))[:25]:
        if link in seen:
            continue
        seen.add(link)
        yield from _extract_contacts_from_job_page(link, area, "catho")


def _collect_indeed(keyword: str, location: str, area: str) -> Iterable[Contact]:
    url = f"https://www.indeed.com.br/vagas?q={requests.utils.quote(keyword)}&l={requests.utils.quote(location)}"
    resp = _request(url)
    if not resp or resp.status_code != 200:
        return []
    soup = BeautifulSoup(resp.text, "html.parser")
    links = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if "/page/" in href or "/vagas/" in href or "jk=" in href:
            links.append(urljoin(url, href))
    seen = set()
    for link in list(dict.fromkeys(links))[:25]:
        if link in seen:
            continue
        seen.add(link)
        yield from _extract_contacts_from_job_page(link, area, "indeed")


def _rss_trampos(keyword: str, area: str) -> Iterable[Contact]:
    url = f"https://trampos.co/rss?q={requests.utils.quote(keyword)}"
    resp = _request(url)
    if not resp or resp.status_code != 200:
        return []
    soup = BeautifulSoup(resp.text, "xml" if True else "html.parser")
    items = soup.find_all("item") or soup.find_all("entry")
    for item in items[:50]:
        title = _clean(item.find("title").get_text() if item.find("title") else "")
        link = _clean(item.find("link").get_text() if item.find("link") else "")
        if not link:
            continue
        yield from _extract_contacts_from_job_page(link, area, "trampos")


def collect_jobs(
    keywords: list[str],
    location: str = "Rio de Janeiro",
    *,
    max_per_category: int = 220,
    freshness_hours: int = 72,
) -> dict:
    now = datetime.now(timezone.utc)
    cutoff = now.timestamp() - freshness_hours * 3600
    registry = _load_registry()
    results: dict[str, list[Contact]] = {k: [] for k in CATEGORIES.keys()}
    stats = {k: {"found": 0, "with_email": 0, "duplicates_removed": 0} for k in CATEGORIES.keys()}

    collectors = [
        ("gupy", _collect_gupy),
        ("prh", _collect_prh),
        ("catho", _collect_catho),
        ("indeed", _collect_indeed),
    ]
    rss_collectors = [
        ("trampos", _rss_trampos),
    ]

    def _dedupe(contacts: list[Contact], area: str) -> list[Contact]:
        seen = set(registry.get(area, {}).keys())
        out = []
        for c in contacts:
            key = _dedupe_key(c)
            if key in seen:
                stats[area]["duplicates_removed"] += 1
                continue
            seen.add(key)
            out.append(c)
        return out

    for area, keywords_area in [
        ("MARKETING", keywords + ["marketing", "social media", "conteúdo"]),
        ("PRODUTO", keywords + ["product manager", "product owner", "product designer"]),
        ("DESIGN", keywords + ["designer", "UX", "UI", "art director"]),
        ("IA", keywords + ["IA", "AI", "automation", "machine learning"]),
    ]:
        seen_urls = set()
        contacts: list[Contact] = []
        for source, collector in collectors:
            for kw in keywords_area[:4]:
                try:
                    for c in collector(kw, location, area):
                        c.source = source
                        if c.job_url in seen_urls:
                            continue
                        seen_urls.add(c.job_url)
                        contacts.append(c)
                        if len(contacts) >= max_per_category:
                            break
                    if len(contacts) >= max_per_category:
                        break
                except Exception:
                    continue
                time.sleep(0.2)
        for source, collector in rss_collectors:
            for kw in keywords_area[:2]:
                try:
                    for c in collector(kw, area):
                        c.source = source
                        if c.job_url in seen_urls:
                            continue
                        seen_urls.add(c.job_url)
                        contacts.append(c)
                        if len(contacts) >= max_per_category:
                            break
                except Exception:
                    continue
                time.sleep(0.1)

        pre = len(contacts)
        contacts = _dedupe(contacts, area)
        stats[area]["found"] = pre
        stats[area]["with_email"] = sum(1 for c in contacts if c.email)
        stats[area]["duplicates_removed"] += pre - len(contacts)
        results[area] = contacts[:max_per_category]
        _update_registry(area, contacts)

    _save_registry(registry)
    return {"results": results, "stats": stats}


def _load_registry() -> dict:
    if REGISTRY_PATH.exists():
        try:
            return json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def _save_registry(registry: dict) -> None:
    REGISTRY_PATH.write_text(json.dumps(registry, ensure_ascii=False, indent=2), encoding="utf-8")


def _update_registry(area: str, contacts: list[Contact]) -> None:
    registry = _load_registry()
    area_map = registry.setdefault(area, {})
    for c in contacts:
        area_map[_dedupe_key(c)] = {
            "email": c.email,
            "company": c.company,
            "role": c.role,
            "job_url": c.job_url,
            "source": c.source,
            "discovered_at": c.discovered_at,
        }
    _save_registry(registry)


def generate_batches(results: dict[str, list[Contact]], batch_size: int = 200) -> list[dict]:
    batches: list[dict] = []
    batch_index = {k: 1 for k in results.keys()}
    for area, contacts in results.items():
        for i in range(0, len(contacts), batch_size):
            chunk = contacts[i:i + batch_size]
            if not chunk:
                continue
            batch_id = f"{area} #{str(batch_index[area]).zfill(3)}"
            batch_index[area] += 1
            path = BATCH_DIR / f"{area.lower()}_{batch_index[area]-1:03d}.csv"
            with path.open("w", newline="", encoding="utf-8-sig") as f:
                writer = csv.DictWriter(f, fieldnames=[
                    "email", "firstname", "lastname", "company", "role", "area", "job_url", "source", "contact_type", "published_date"
                ])
                writer.writeheader()
                for c in chunk:
                    writer.writerow(c.to_csv_dict())
            batches.append({
                "batch_id": batch_id,
                "area": area,
                "count": len(chunk),
                "path": str(path),
                "contacts": [c.to_csv_dict() for c in chunk],
                "created_at": _utcnow(),
                "status": "ready",
            })
    return batches


def save_batch_registry(batches: list[dict]) -> None:
    reg_path = DATA_DIR / "batch_registry.json"
    existing = []
    if reg_path.exists():
        try:
            existing = json.loads(reg_path.read_text(encoding="utf-8"))
        except Exception:
            existing = []
    existing.extend(batches)
    reg_path.write_text(json.dumps(existing, ensure_ascii=False, indent=2), encoding="utf-8")
