#!/usr/bin/env python3
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_DIR = Path(__file__).parent.parent
SIEM_WEBHOOK_URL = os.getenv("SIEM_WEBHOOK_URL", "")
SIEM_TOKEN = os.getenv("SIEM_TOKEN", "")
SIEM_TYPE = os.getenv("SIEM_TYPE", "generic").lower()

try:
    import requests as requests_lib
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False


def _auth_header() -> dict:
    if not SIEM_TOKEN:
        return {}
    if SIEM_TYPE == "splunk":
        return {"Authorization": f"Splunk {SIEM_TOKEN}"}
    return {"Authorization": f"Bearer {SIEM_TOKEN}"}


def _cef_fields(finding: dict, source: str) -> dict:
    return {
        "timestamp": finding.get("timestamp", datetime.now(timezone.utc).isoformat()),
        "source": source,
        "type": finding.get("type", "unknown"),
        "severity": finding.get("severity", "INFO"),
        "file": finding.get("file", ""),
        "line": finding.get("line", 0),
        "description": finding.get("description", finding.get("reason", "")),
        "repo_url": finding.get("repo_url", ""),
    }


def send_finding(finding: dict, source: str = "codeaudit") -> bool:
    payload = _cef_fields(finding, source)
    severity = payload["severity"].upper()

    if not SIEM_WEBHOOK_URL:
        ts = payload["timestamp"]
        desc = payload["description"]
        loc = f"{payload['file']}:{payload['line']}" if payload.get("file") else "?"
        repo = payload.get("repo_url", "")
        print(f"[SIEM SIM] {ts} | {severity} | {source} | {desc} | {loc} | repo: {repo}")
        return True

    if not HAS_REQUESTS:
        print("  ⚠️  Biblioteca 'requests' no disponible. Instálala con 'pip install requests'.")
        return False

    headers = {
        "Content-Type": "application/json",
        **_auth_header(),
    }

    try:
        resp = requests_lib.post(SIEM_WEBHOOK_URL, json=payload, headers=headers, timeout=30)
        resp.raise_for_status()
        return True
    except Exception as e:
        print(f"  ⚠️  Error enviando hallazgo a SIEM: {e}")
        return False


def send_batch(findings: list[dict], source: str = "codeaudit") -> tuple[int, int]:
    success = 0
    fail = 0
    for f in findings:
        if send_finding(f, source):
            success += 1
        else:
            fail += 1
    return success, fail


def load_report() -> dict:
    path = PROJECT_DIR / "reports" / "security-report.json"
    if not path.exists():
        return {"secrets": [], "vulnerable_dependencies": []}
    raw = path.read_text(encoding="utf-8").strip()
    if raw.startswith("```"):
        raw = raw.replace("```json", "").replace("```", "").strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {"secrets": [], "vulnerable_dependencies": []}


def main():
    report = load_report()
    secrets = report.get("secrets", [])
    deps = report.get("vulnerable_dependencies", [])

    hallazgos = []
    for s in secrets:
        hallazgos.append({
            "timestamp": s.get("timestamp"),
            "type": "secret",
            "severity": "CRITICAL",
            "file": s.get("file", ""),
            "line": s.get("line", 0),
            "description": s.get("reason", "Secreto detectado"),
            "repo_url": s.get("repo_url", ""),
        })
    for d in deps:
        sev = d.get("severity", "").upper()
        if sev in ("CRITICAL", "HIGH"):
            hallazgos.append({
                "timestamp": d.get("timestamp"),
                "type": "vulnerable_dependency",
                "severity": sev,
                "file": d.get("file", ""),
                "line": d.get("line", 0),
                "description": f"{d.get('name', '?')}@{d.get('version', '?')} - {d.get('advisory', '')}",
                "repo_url": d.get("repo_url", ""),
            })

    if not hallazgos:
        print("✅ No se encontraron hallazgos críticos o de alta gravedad.")
        return

    print(f"📡 Enviando {len(hallazgos)} hallazgo(s) al SIEM ({SIEM_TYPE})...")
    ok, fail = send_batch(hallazgos)
    print(f"   Enviados: {ok}  |  Fallos: {fail}")

    if fail > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
