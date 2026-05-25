#!/usr/bin/env python3
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL", "")

try:
    import requests as requests_lib
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

COLORS = {
    "critical": "#f43f5e",
    "warning": "#fbbf24",
    "good": "#10b981",
}


def _color_from_critical_count(count: int) -> str:
    if count > 0:
        return COLORS["critical"]
    return COLORS["good"]


def send_alert(message: str, color: str = COLORS["critical"]) -> bool:
    if not SLACK_WEBHOOK_URL:
        ts = datetime.now(timezone.utc).isoformat()
        print(f"[SLACK SIM] {ts} | {message} | color: {color}")
        return True

    if not HAS_REQUESTS:
        print("  ⚠️  Biblioteca 'requests' no disponible. Inst\u00e1lala con 'pip install requests'.")
        return False

    payload = {
        "text": message,
        "attachments": [{"color": color, "text": message}],
    }

    try:
        resp = requests_lib.post(SLACK_WEBHOOK_URL, json=payload, timeout=30)
        resp.raise_for_status()
        return True
    except Exception as e:
        print(f"  ⚠️  Error enviando alerta a Slack: {e}")
        return False


def send_findings_summary(secrets_count: int, vulns_count: int, critical_count: int, repo_url: str) -> bool:
    color = _color_from_critical_count(critical_count)
    message = (
        f"\U0001f6e1\ufe0f CodeAudit Pro \u2014 Resumen de Auditor\u00eda\n"
        f"\u2022 Secretos: {secrets_count}\n"
        f"\u2022 Vulnerabilidades: {vulns_count}\n"
        f"\u2022 Cr\u00edticos: {critical_count}\n"
        f"\u2022 Repositorio: {repo_url}"
    )
    return send_alert(message, color)


def send_critical_alert(finding_type: str, description: str, file: str, line: int, repo_url: str) -> bool:
    message = (
        f"\U0001f6a8 SECRETO CR\u00cdTICO DETECTADO\n"
        f"\u2022 Tipo: {finding_type}\n"
        f"\u2022 Descripci\u00f3n: {description}\n"
        f"\u2022 Archivo: {file}:{line}\n"
        f"\u2022 Repositorio: {repo_url}"
    )
    return send_alert(message, COLORS["critical"])


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Env\u00eda alertas a Slack desde CodeAudit Pro")
    parser.add_argument("--summary", action="store_true", help="Enviar resumen de auditor\u00eda desde reports/security-report.json")
    parser.add_argument("--critical", action="store_true", help="Enviar alerta cr\u00edtica (requiere --type, --desc, --file, --line, --repo)")
    parser.add_argument("--type", default="secreto")
    parser.add_argument("--desc", default="")
    parser.add_argument("--file", default="")
    parser.add_argument("--line", type=int, default=0)
    parser.add_argument("--repo", default="")
    parser.add_argument("--message", default="", help="Mensaje libre para send_alert")
    parser.add_argument("--color", default=COLORS["critical"], help="Color del mensaje")
    args = parser.parse_args()

    if args.summary:
        report_path = Path(__file__).parent.parent / "reports" / "security-report.json"
        if not report_path.exists():
            print("\u26a0\ufe0f  No se encontr\u00f3 reports/security-report.json")
            sys.exit(1)
        raw = report_path.read_text(encoding="utf-8").strip()
        if raw.startswith("```"):
            raw = raw.replace("```json", "").replace("```", "").strip()
        try:
            report = json.loads(raw)
        except json.JSONDecodeError:
            report = {}
        secrets = report.get("secrets", [])
        vulns = report.get("vulnerable_dependencies", [])
        critical = sum(1 for v in vulns if v.get("severity", "").upper() in ("CRITICAL", "HIGH"))
        critical += len(secrets)
        ok = send_findings_summary(len(secrets), len(vulns), critical, args.repo)
    elif args.critical:
        ok = send_critical_alert(args.type, args.desc, args.file, args.line, args.repo)
    elif args.message:
        ok = send_alert(args.message, args.color)
    else:
        parser.print_help()
        sys.exit(1)

    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
