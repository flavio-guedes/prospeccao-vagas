#!/usr/bin/env python3
"""
Google Drive Career CV Library — indexer.
Read-only. Uses existing OAuth token from ~/.hermes/google_token.json.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
INDEX_PATH = DATA_DIR / "cv_library_index.json"
CV_ROOT_FOLDER = "1KmIpQUNOr9HMSxhu0BKJOzl9x8x9ofeD"
TOKEN_PATH = Path.home() / ".hermes" / "google_token.json"
HEADERS = {"User-Agent": "CareerCVLibrary/1.0"}


def _load_token() -> dict:
    if not TOKEN_PATH.exists():
        raise RuntimeError("Missing Google token at ~/.hermes/google_token.json")
    return json.loads(TOKEN_PATH.read_text(encoding="utf-8"))


def _refresh_access_token(token_data: dict) -> str:
    payload = {
        "client_id": token_data["client_id"],
        "client_secret": token_data["client_secret"],
        "refresh_token": token_data["refresh_token"],
        "grant_type": "refresh_token",
    }
    r = requests.post("https://oauth2.googleapis.com/token", data=payload, timeout=30)
    r.raise_for_status()
    return r.json()["access_token"]


def _drive_request(access_token: str, url: str, params: dict | None = None) -> dict:
    headers = {"Authorization": f"Bearer {access_token}"}
    r = requests.get(url, headers=headers, params=params, timeout=30)
    if r.status_code == 401:
        token = _refresh_access_token(_load_token())
        headers["Authorization"] = f"Bearer {token}"
        r = requests.get(url, headers=headers, params=params, timeout=30)
    r.raise_for_status()
    return r.json()


def _classify_area(name: str, parent: str) -> str:
    text = f"{name} {parent}".lower()
    if any(k in text for k in ["marketing", "social media", "redator", "conteúdo", "content"]):
        return "MARKETING"
    if any(k in text for k in ["product", "produto", "pmm", "gestor de projetos"]):
        return "PRODUTO"
    if any(k in text for k in ["design", "ux", "ui", "product designer"]):
        return "DESIGN"
    if any(k in text for k in ["ia", "ai", "automation", "automação"]):
        return "IA"
    return "OUTROS"


def _seniority_from_name(name: str) -> str:
    text = name.lower()
    if any(k in text for k in ["sr.", "sênior", "senior", "head", "diretor", "lead"]):
        return "SENIOR"
    if any(k in text for k in ["coord.", "coordenador", "pleno", "mid"]):
        return "PLENO"
    if any(k in text for k in ["jr.", "junior", "estagiário", "intern"]):
        return "JUNIOR"
    return "NÃO_ESPECIFICADO"


def _skills_from_name(name: str) -> list[str]:
    text = name.lower()
    keywords = ["marketing", "social media", "produto", "product", "design", "ux", "ui", "ia", "ai", "automation", "automação", "conteúdo", "content", "gestor", "project", "customer success", "account manager"]
    return [k for k in keywords if k in text]


def _roles_from_name(name: str) -> list[str]:
    text = name.lower()
    roles = []
    patterns = [
        ("coordenador de marketing", "Coordenador de Marketing"),
        ("analista de marketing", "Analista de Marketing"),
        ("social media manager", "Social Media Manager"),
        ("product manager", "Product Manager"),
        ("product designer", "Product Designer"),
        ("gestor de projetos", "Gestor de Projetos"),
        ("customer success", "Customer Success"),
        ("account manager", "Account Manager"),
        ("redator", "Redator"),
        ("editor", "Editor"),
        ("diretor de arte", "Diretor de Arte"),
        ("designer", "Designer"),
    ]
    for key, label in patterns:
        if key in text:
            roles.append(label)
    return roles or [name]


def list_folder(access_token: str, folder_id: str) -> list[dict]:
    url = "https://www.googleapis.com/drive/v3/files"
    params = {
        "q": f"'{folder_id}' in parents",
        "fields": "files(id,name,mimeType,modifiedTime,webViewLink,size)",
        "pageSize": 1000,
    }
    data = _drive_request(access_token, url, params)
    return data.get("files", [])


def list_all_cv_files(access_token: str, root_folder: str = CV_ROOT_FOLDER) -> list[dict]:
    token = _refresh_access_token(_load_token())

    def _walk(folder_id: str, parent_path: str = "") -> list[dict]:
        items = list_folder(token, folder_id)
        results: list[dict] = []
        for item in items:
            path = f"{parent_path}/{item['name']}" if parent_path else item["name"]
            if item.get("mimeType") == "application/vnd.google-apps.folder":
                results.extend(_walk(item["id"], path))
            else:
                results.append({**item, "path": path, "parent_id": folder_id})
        return results

    return _walk(root_folder)


def build_index() -> dict[str, dict]:
    token = _refresh_access_token(_load_token())
    files = list_all_cv_files(token)
    index: dict[str, dict] = {}
    for f in files:
        area = _classify_area(f.get("name", ""), f.get("path", ""))
        entry = {
            "cv_id": f["id"],
            "file_id": f["id"],
            "name": f.get("name", ""),
            "type": f.get("mimeType", ""),
            "url": f.get("webViewLink", ""),
            "modified_time": f.get("modifiedTime", ""),
            "size": f.get("size", ""),
            "path": f.get("path", ""),
            "area": area,
            "roles": _roles_from_name(f.get("name", "")),
            "seniority": _seniority_from_name(f.get("name", "")),
            "skills": _skills_from_name(f.get("name", "")),
            "content_text": "",
            "content_source": "metadata_only",
            "keywords": _skills_from_name(f.get("name", "")) + _roles_from_name(f.get("name", "")),
            "portfolio_links": [],
        }
        index[f["id"]] = entry
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    INDEX_PATH.write_text(json.dumps({"updated_at": _utcnow(), "root_folder": CV_ROOT_FOLDER, "items": index}, ensure_ascii=False, indent=2), encoding="utf-8")
    return index


def load_index() -> dict[str, dict]:
    if not INDEX_PATH.exists():
        return build_index()
    data = json.loads(INDEX_PATH.read_text(encoding="utf-8"))
    return data.get("items", {})


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


if __name__ == "__main__":
    print(json.dumps({"count": len(load_index()), "path": str(INDEX_PATH)}, ensure_ascii=False, indent=2))
