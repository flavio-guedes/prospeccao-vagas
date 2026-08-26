#!/usr/bin/env python3
"""
Job Radar — simple local server + batch CLI.
Requires: Python 3.9+, requests, beautifulsoup4
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
BATCH_DIR = DATA_DIR / "batches"
HTML_PATH = ROOT / "dashboard" / "job-radar.html"

try:
    from job_radar import collect_jobs, generate_batches, save_batch_registry, CATEGORIES
except ImportError:
    sys.path.insert(0, str(ROOT / "scripts"))
    from job_radar import collect_jobs, generate_batches, save_batch_registry, CATEGORIES  # type: ignore


def _read_json(path: Path, default: Any) -> Any:
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return default
    return default


def _write_json(path: Path, data: Any) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def api_collect(body: dict) -> dict:
    location = body.get("location") or "Rio de Janeiro"
    keywords = body.get("keywords") or [
        "marketing", "produto", "design", "ux", "ui", "ia", "ai", "automation", "automação"
    ]
    return collect_jobs(keywords=keywords, location=location, max_per_category=220)


def api_batch(body: dict) -> dict:
    batches_input = body.get("batches") or []
    if not batches_input:
        return {"batches": []}
    # rebuild contact lists from rawData stored in memory? We do not persist raw contacts to disk by design.
    # Instead, we accept explicit contact arrays.
    all_contacts = []
    for b in batches_input:
        contacts = []
        for c in b.get("contacts") or []:
            contacts.append(Contact(**{k: c.get(k, "") for k in Contact.__dataclass_fields__.keys()}))
        all_contacts.extend(contacts)
    from collections import defaultdict
    grouped = defaultdict(list)
    for c in all_contacts:
        grouped[c.area].append(c)
    batches = generate_batches(grouped, batch_size=int(body.get("batch_size") or 200))
    save_batch_registry(batches)
    return {"batches": batches}


def api_history() -> list[dict]:
    path = DATA_DIR / "batch_registry.json"
    return _read_json(path, [])


try:
    from http.server import HTTPServer, BaseHTTPRequestHandler
    import urllib.parse

    class JobRadarHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == "/" or self.path == "/index.html":
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                self.wfile.write(HTML_PATH.read_bytes())
                return
            if self.path == "/api/job-radar/history":
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps(api_history(), ensure_ascii=False).encode("utf-8"))
                return
            self.send_response(404)
            self.end_headers()

        def do_POST(self):
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length) or "{}")
            if self.path == "/api/job-radar/collect":
                result = api_collect(body)
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps(result, ensure_ascii=False).encode("utf-8"))
                return
            if self.path == "/api/job-radar/batch":
                result = api_batch(body)
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps(result, ensure_ascii=False).encode("utf-8"))
                return
            self.send_response(404)
            self.end_headers()

        def log_message(self, format, *args):
            return

    def serve(port: int = 7895):
        server = HTTPServer(("127.0.0.1", port), JobRadarHandler)
        print(f"Job Radar rodando em http://127.0.0.1:{port}")
        server.serve_forever()

    if __name__ == "__main__":
        serve()
except Exception:
    # Fallback CLI if server cannot start
    def cli():
        data = api_collect({"location": "Rio de Janeiro"})
        batches = generate_batches(data["results"])
        save_batch_registry(batches)
        print(json.dumps({
            "stats": data["stats"],
            "batches": [{"batch_id": b["batch_id"], "count": b["count"], "path": b["path"]} for b in batches]
        }, ensure_ascii=False, indent=2))

    if __name__ == "__main__":
        cli()
