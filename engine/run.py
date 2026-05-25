#!/usr/bin/env python3
import argparse
import json
import os
import subprocess
import sys
import uuid
from datetime import datetime
from pathlib import Path


PROJECT_DIR = Path(__file__).parent.parent

from engine.health_check import check_tools, ToolMissingError
check_tools(raise_on_missing=True)


def write_status(audit_id: str, step: str, status: str, data: dict = None):
    status_dir = PROJECT_DIR / "data" / "audit_status"
    status_dir.mkdir(parents=True, exist_ok=True)
    status_file = status_dir / f"{audit_id}.json"
    entry = {"step": step, "status": status, "updated_at": datetime.utcnow().isoformat() + "Z"}
    if data:
        entry["data"] = data
    status_file.write_text(json.dumps(entry, ensure_ascii=False), encoding="utf-8")


def run_cmd(cmd, timeout=180):
    try:
        r = subprocess.run(cmd, shell=True, text=True, capture_output=True, timeout=timeout)
        return r.returncode, r.stdout, r.stderr
    except subprocess.TimeoutExpired:
        return -1, "", "Timeout"


def run_trivy(repo_path):
    cmd = f"trivy filesystem --format json --quiet '{repo_path}'"
    code, out, err = run_cmd(cmd, timeout=300)
    if code != 0 or not out.strip():
        return []
    try:
        data = json.loads(out)
        results = data.get("Results", [])
        vulns = []
        for r in results:
            for v in r.get("Vulnerabilities", []):
                vulns.append({
                    "name": v.get("PkgName", v.get("VulnerabilityID", "")),
                    "version": v.get("InstalledVersion", ""),
                    "severity": v.get("Severity", "UNKNOWN"),
                    "title": v.get("Title", ""),
                    "cve": v.get("VulnerabilityID", ""),
                    "source": "trivy",
                })
        return vulns
    except (json.JSONDecodeError, KeyError):
        return []


def run_semgrep(repo_path):
    cmd = f"semgrep --config auto --json --quiet '{repo_path}' 2>/dev/null"
    code, out, err = run_cmd(cmd, timeout=300)
    if code not in (0, 1) or not out.strip():
        return [], []
    try:
        data = json.loads(out)
        findings = []
        for r in data.get("results", []):
            findings.append({
                "file": r.get("path", ""),
                "line": r.get("start", {}).get("line", 0),
                "reason": r.get("extra", {}).get("message", ""),
                "severity": r.get("extra", {}).get("severity", "WARNING"),
                "rule": r.get("check_id", ""),
                "source": "semgrep",
            })
        secrets = [f for f in findings if any(k in f.get("rule","").lower() for k in ("secret","credential","password","token","key","api"))]
        vulns = [f for f in findings if f not in secrets]
        return secrets, vulns
    except (json.JSONDecodeError, KeyError):
        return [], []


def run_bandit(repo_path):
    cmd = f"bandit -r --format json --quiet '{repo_path}' 2>/dev/null"
    code, out, err = run_cmd(cmd, timeout=120)
    if code not in (0, 1) or not out.strip():
        return []
    try:
        data = json.loads(out)
        findings = []
        for r in data.get("results", []):
            findings.append({
                "file": r.get("filename", ""),
                "line": r.get("line_number", 0),
                "reason": r.get("issue_text", ""),
                "severity": r.get("issue_severity", "MEDIUM"),
                "rule": r.get("test_id", ""),
                "source": "bandit",
            })
        return findings
    except (json.JSONDecodeError, KeyError):
        return []


def run_trufflehog(repo_path):
    cmd = f"trufflehog --json --regex --entropy=False file://'{repo_path}' 2>/dev/null"
    code, out, err = run_cmd(cmd, timeout=120)
    if code not in (0, 1) or not out.strip():
        return []
    findings = []
    for line in out.strip().split("\n"):
        line = line.strip()
        if not line:
            continue
        try:
            d = json.loads(line)
            findings.append({
                "file": d.get("path", ""),
                "line": d.get("line_number", 0) or d.get("line", 0),
                "reason": d.get("reason", "Potential secret found"),
                "severity": d.get("severity", "HIGH"),
                "source": "trufflehog",
            })
        except json.JSONDecodeError:
            pass
    return findings


def run_lizard(repo_path):
    cmd = f"lizard --languages python,javascript,typescript,java,go,cpp --xml '{repo_path}' 2>/dev/null"
    code, out, err = run_cmd(cmd, timeout=120)
    if code != 0 or not out.strip():
        return None
    import re
    complexities = re.findall(r'NLOC\s+(\d+).*?CCN\s+(\d+)', out)
    if complexities:
        try:
            nloc_vals = [int(c[0]) for c in complexities]
            ccn_vals = [int(c[1]) for c in complexities]
            avg_ccn = round(sum(ccn_vals) / len(ccn_vals), 1) if ccn_vals else 0
            total_nloc = sum(nloc_vals)
            return {"average_complexity": avg_ccn, "total_lines": total_nloc}
        except (ValueError, IndexError):
            pass

    cmd2 = f"radon cc '{repo_path}' -s 2>/dev/null"
    code2, out2, err2 = run_cmd(cmd2, timeout=60)
    if code2 == 0 and out2.strip():
        import re
        grades = re.findall(r'\((\w)\)', out2)
        score = sum({"A": 1, "B": 2, "C": 3, "D": 4, "F": 5}.get(g, 3) for g in grades) / max(len(grades), 1)
        avg = scores.get("average_complexity", 2.0) if False else round(score, 1)
        return {"average_complexity": avg, "total_lines": 0}
    return None


def run_radon_dup(repo_path):
    cmd = f"radon raw '{repo_path}' -s 2>/dev/null"
    code, out, err = run_cmd(cmd, timeout=60)
    if code != 0 or not out.strip():
        return None
    import re
    sloc = re.findall(r'LOC:\s+(\d+)', out)
    return {"duplicated_lines": int(sloc[0]) * 0.15 if sloc else 0}


def main():
    parser = argparse.ArgumentParser(description="CodeAudit Pro — Motor de auditoría")
    parser.add_argument("repo_path", nargs="?", default=".", help="Ruta del repositorio a auditar")
    parser.add_argument("model", nargs="?", default="opencode/deepseek-v4-flash-free", help="Modelo opencode")
    parser.add_argument("--audit-id", default=str(uuid.uuid4())[:8], help="ID único para esta auditoría")
    args = parser.parse_args()

    repo_path = args.repo_path
    audit_id = args.audit_id

    print(f"🚀 Auditoría #{audit_id} — {repo_path}")
    print(f"   Progreso: http://localhost:5000/audit-status/{audit_id}")
    os.makedirs("reports", exist_ok=True)

    write_status(audit_id, "init", "running", {"repo": repo_path, "message": "Iniciando auditoría..."})

    secrets = []
    vulns = []
    bandit_findings = []

    write_status(audit_id, "secrets", "running", {"message": "Escaneando secretos (truffleHog + Semgrep)..."})
    print("🔒 [1/5] Escaneando secretos (truffleHog + Semgrep)...")
    th_secrets = run_trufflehog(repo_path)
    print(f"   truffleHog: {len(th_secrets)} hallazgos")
    sm_secrets, sm_vulns = run_semgrep(repo_path)
    print(f"   Semgrep: {len(sm_secrets)} secretos, {len(sm_vulns)} vulnerabilidades")
    secrets.extend(th_secrets)
    secrets.extend(sm_secrets)
    write_status(audit_id, "secrets", "done", {"secrets_found": len(secrets)})

    write_status(audit_id, "sast", "running", {"message": "Escaneando SAST Python (bandit)..."})
    print("🔐 [2/5] Escaneando SAST Python (bandit)...")
    bandit_findings = run_bandit(repo_path)
    print(f"   bandit: {len(bandit_findings)} hallazgos")
    for b in bandit_findings:
        if b.get("severity", "").upper() in ("HIGH", "MEDIUM"):
            vulns.append(b)
    write_status(audit_id, "sast", "done", {"sast_findings": len(bandit_findings)})

    write_status(audit_id, "deps", "running", {"message": "Escaneando dependencias (Trivy)..."})
    print("📦 [3/5] Escaneando dependencias (Trivy)...")
    trivy_vulns = run_trivy(repo_path)
    print(f"   Trivy: {len(trivy_vulns)} vulnerabilidades")
    vulns.extend(trivy_vulns)
    vulns.extend(sm_vulns)
    write_status(audit_id, "deps", "done", {"vulns_found": len(trivy_vulns)})

    # Deduplicate by (file, line, rule)
    seen = set()
    deduped_vulns = []
    for v in vulns:
        key = (v.get("file", ""), v.get("line", 0), v.get("rule", v.get("cve", "")))
        if key not in seen:
            seen.add(key)
            deduped_vulns.append(v)

    write_status(audit_id, "debt", "running", {"message": "Midiendo deuda técnica..."})
    print("📊 [4/5] Midiendo deuda técnica (lizard/radon)...")
    debt = run_lizard(repo_path) or {}
    dup = run_radon_dup(repo_path) or {}
    debt.update(dup)
    write_status(audit_id, "debt", "done", {"complexity": debt.get("average_complexity", "N/A")})

    # Save security report
    write_status(audit_id, "save", "running", {"message": "Guardando resultados..."})
    sec_report = {
        "secrets": secrets,
        "vulnerable_dependencies": [v for v in deduped_vulns if v.get("source") == "trivy"],
        "sast_findings": deduped_vulns,
        "tools_used": ["trivy", "semgrep", "bandit", "trufflehog"],
        "summary": {
            "total_secrets": len(secrets),
            "total_vulnerabilities": len(deduped_vulns),
            "critical_count": sum(1 for v in deduped_vulns if v.get("severity","").upper() in ("CRITICAL","HIGH")),
            "scan_date": subprocess.run(["date","-u","+%Y-%m-%dT%H:%M:%SZ"], capture_output=True, text=True).stdout.strip(),
        },
    }
    sec_file = "reports/security-report.json"
    with open(sec_file, "w", encoding="utf-8") as f:
        json.dump(sec_report, f, indent=2, ensure_ascii=False)
    print(f"✓ {sec_file} guardado ({len(secrets)} secretos, {len(deduped_vulns)} hallazgos)")

    debt_file = "reports/debt-report.json"
    if not debt.get("average_complexity"):
        debt["average_complexity"] = "N/A"
    if not debt.get("duplicated_lines"):
        debt["duplicated_lines"] = 0
    debt["summary"] = {
        "average_complexity": debt["average_complexity"],
        "duplicated_lines": debt["duplicated_lines"],
    }
    with open(debt_file, "w", encoding="utf-8") as f:
        json.dump(debt, f, indent=2, ensure_ascii=False)
    print(f"✓ {debt_file} guardado (complejidad: {debt['average_complexity']})")

    write_status(audit_id, "report", "running", {"message": "Generando informe visual..."})
    print("🎨 [5/5] Generando informe visual...")
    code, out, err = run_cmd("python3 engine/generate_report.py")
    if code == 0:
        print("✓ Informe generado: reports/executive-report.html")
    else:
        print(f"⚠️ Error en generación de informe: {err[:200]}")
        write_status(audit_id, "report", "error", {"error": err[:200]})
        return

    write_status(audit_id, "complete", "done", {
        "secrets": len(secrets),
        "vulnerabilities": len(deduped_vulns),
        "complexity": debt.get("average_complexity", "N/A"),
        "report": "reports/executive-report.html",
    })

    print("\n🎉 Auditoría completada.")
    print(f"   Secretos: {len(secrets)}")
    print(f"   Vulnerabilidades: {len(deduped_vulns)}")
    print(f"   Complejidad promedio: {debt['average_complexity']}")


if __name__ == "__main__":
    main()
