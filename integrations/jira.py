#!/usr/bin/env python3
import json
import os
import subprocess
import sys
from pathlib import Path

PROJECT_DIR = Path(__file__).parent.parent
JIRA_URL = os.getenv("JIRA_URL", "")
JIRA_EMAIL = os.getenv("JIRA_EMAIL", "")
JIRA_API_TOKEN = os.getenv("JIRA_API_TOKEN", "")


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


def create_jira_issue(project_key: str, summary: str, description: str, priority: str = "High") -> dict | None:
    if not JIRA_URL or not JIRA_EMAIL or not JIRA_API_TOKEN:
        print(f"  ℹ️  Jira no configurado. Para integrar, define:")
        print(f"      JIRA_URL, JIRA_EMAIL, JIRA_API_TOKEN")
        return None

    import requests
    from requests.auth import HTTPBasicAuth

    url = f"{JIRA_URL.rstrip('/')}/rest/api/2/issue"
    auth = HTTPBasicAuth(JIRA_EMAIL, JIRA_API_TOKEN)
    headers = {"Content-Type": "application/json"}

    payload = {
        "fields": {
            "project": {"key": project_key},
            "summary": summary,
            "description": {
                "type": "doc",
                "version": 1,
                "content": [{"type": "paragraph", "content": [{"type": "text", "text": description}]}],
            },
            "issuetype": {"name": "Bug"},
            "priority": {"name": priority},
        }
    }

    try:
        resp = requests.post(url, json=payload, auth=auth, headers=headers, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        print(f"  ✓ Ticket Jira creado: {data.get('key')} -> {JIRA_URL}/browse/{data.get('key')}")
        return data
    except Exception as e:
        print(f"  ❌ Error creando ticket Jira: {e}")
        return None


def sync_findings(project_key: str = "SEC"):
    report = load_report()
    secrets = report.get("secrets", [])
    deps = report.get("vulnerable_dependencies", [])

    print(f"🔍 Sincronizando hallazgos con Jira ({project_key})...")
    print(f"   Secretos: {len(secrets)}, Dependencias: {len(deps)}")

    tickets = []
    critical_deps = [d for d in deps if d.get("severity", "").upper() in ("CRITICAL", "HIGH")]

    if not secrets and not critical_deps:
        print("   ✅ No hay hallazgos críticos. No se crean tickets.")
        return

    if secrets:
        details = "\n".join(f"  • {s['file']}:{s.get('line','?')} - {s.get('reason','')}" for s in secrets)
        summary = f"CodeAudit: {len(secrets)} secreto(s) hardcodeado(s) detectado(s)"
        desc = f"Secretos expuestos encontrados por auditoría automática:\n\n{details}\n\nRepositorio auditado. Revisar y rotar credenciales inmediatamente."
        ticket = create_jira_issue(project_key, summary, desc, "Critical")
        if ticket:
            tickets.append(ticket)

    if critical_deps:
        details = "\n".join(f"  • {d['name']}@{d.get('version','?')} - {d.get('severity','')}" for d in critical_deps)
        summary = f"CodeAudit: {len(critical_deps)} dependencia(s) crítica(s) con vulnerabilidades"
        desc = f"Dependencias vulnerables encontradas:\n\n{details}\n\nActualizar paquetes y revisar CVEs asociadas."
        ticket = create_jira_issue(project_key, summary, desc, "High")
        if ticket:
            tickets.append(ticket)

    return tickets


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Integración con Jira")
    parser.add_argument("--project", default="SEC", help="Project key en Jira")
    parser.add_argument("--dry-run", action="store_true", help="Solo mostrar comandos simulados")

    args = parser.parse_args()

    if args.dry_run:
        report = load_report()
        s = len(report.get("secrets", []))
        d = len(report.get("vulnerable_dependencies", []))
        print("🔍 Simulación de integración Jira:")
        print(f"   Secretos: {s}")
        print(f"   Dependencias vulnerables: {d}")
        if s > 0:
            print(f"   Comando simulado: curl -X POST -u email:token {JIRA_URL or 'https://tudominio.atlassian.net'}/rest/api/2/issue ...")
        print("   (Define JIRA_URL, JIRA_EMAIL, JIRA_API_TOKEN para integración real)")
    else:
        sync_findings(args.project)


if __name__ == "__main__":
    main()
