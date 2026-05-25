#!/usr/bin/env python3
"""
Generación automática de PRs para corregir vulnerabilidades de
dependencias y creación de Issues para secretos expuestos.
"""

import json
import os
import sys
import time
import urllib.error
import urllib.request
import urllib.parse

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
HEADERS = {
    "Accept": "application/vnd.github.v3+json",
}
if GITHUB_TOKEN:
    HEADERS["Authorization"] = f"Bearer {GITHUB_TOKEN}"

API_BASE = "https://api.github.com"


# ---------------------------------------------------------------------------
# helpers de red
# ---------------------------------------------------------------------------

def _gh_get(url, headers=None):
    h = {**HEADERS, **(headers or {})}
    if HAS_REQUESTS:
        r = requests.get(url, headers=h, timeout=30)
        r.raise_for_status()
        return r.json()
    req = urllib.request.Request(url, headers=h, method="GET")
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode())


def _gh_put(url, payload, headers=None):
    h = {**HEADERS, **(headers or {})}
    data = json.dumps(payload).encode()
    if HAS_REQUESTS:
        r = requests.put(url, headers=h, data=data, timeout=30)
        r.raise_for_status()
        return r.json()
    req = urllib.request.Request(url, data=data, headers=h, method="PUT")
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode())


def _gh_post(url, payload, headers=None):
    h = {**HEADERS, **(headers or {})}
    data = json.dumps(payload).encode()
    if HAS_REQUESTS:
        r = requests.post(url, headers=h, data=data, timeout=30)
        r.raise_for_status()
        return r.json()
    req = urllib.request.Request(url, data=data, headers=h, method="POST")
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode())


def _gh(url, method="GET", payload=None):
    if method == "GET":
        return _gh_get(url)
    if method == "PUT":
        return _gh_put(url, payload)
    return _gh_post(url, payload)


# ---------------------------------------------------------------------------
# utilidades
# ---------------------------------------------------------------------------

def parse_repo_url(url: str) -> tuple[str, str]:
    """Extrae owner y repo de una URL de GitHub."""
    url = url.rstrip("/")
    if url.endswith(".git"):
        url = url[:-4]
    parts = url.rstrip("/").split("/")
    owner, repo = parts[-2], parts[-1]
    return owner, repo


def _simular(msg: str):
    print(f"[SIMULACIÓN] {msg}")


def _timestamp() -> str:
    return str(int(time.time()))


# ---------------------------------------------------------------------------
# corrección de dependencias
# ---------------------------------------------------------------------------

def _paquete_a_ruta(pkg_file: str) -> str:
    """Devuelve la ruta canónica del manifiesto según el gestor."""
    return pkg_file  # confiamos en lo que nos pasa Trivy


def _leer_manifiesto(owner, repo, ruta):
    """Obtiene el contenido (decodificado) de un archivo del repo."""
    url = f"{API_BASE}/repos/{owner}/{repo}/contents/{urllib.parse.quote(ruta, safe='')}"
    resp = _gh(url)
    import base64
    return base64.b64decode(resp["content"]).decode("utf-8"), resp["sha"]


def _actualizar_version(lines, nombre, nueva_version):
    """Reemplaza la constraint de *nombre* por *nueva_version* en el manifiesto."""
    res = []
    tocado = False
    for line in lines:
        stripped = line.strip()
        # package.json: "name": "version"
        if stripped.startswith(f'"{nombre}"'):
            parts = line.split(":")
            if len(parts) >= 2:
                indent = line[:len(line) - len(line.lstrip())]
                res.append(f'{indent}"{nombre}": "{nueva_version}",\n')
                tocado = True
                continue
        # requirements.txt: name==version  / name>=version
        if stripped.lower().startswith(nombre.lower()) and ("==" in stripped or ">=" in stripped):
            delim = "==" if "==" in stripped else ">="
            pre = line[: len(line) - len(stripped)]
            res.append(f"{pre}{nombre}{delim}{nueva_version}\n")
            tocado = True
            continue
        res.append(line)
    if not tocado:
        res.append(f"\n# TODO: agregar manualmente {nombre}=={nueva_version}\n")
    return "".join(res)


def fix_dependency_vuln(vuln: dict, repo_url: str) -> bool:
    """Crea un PR automático corrigiendo una vulnerabilidad de dependencia."""
    if vuln.get("source") != "trivy":
        return False

    owner, repo = parse_repo_url(repo_url)
    name = vuln.get("name", "dep")
    version = vuln.get("fixedVersion", vuln.get("version", "desconocida"))
    cve = vuln.get("cve", "CVE-XXXX-XXXX")
    severity = vuln.get("severity", "unknown")
    desc = vuln.get("description", "Sin descripción")
    pkg_path = vuln.get("pkgPath", "package.json")

    branch_name = f"fix/{name.lower().replace('#', '')}-{_timestamp()}"
    title = f"fix: [Auto] Actualizar {name} a {version} para corregir {cve}"
    body = (
        f"## Vulnerabilidad detectada\n\n"
        f"- **Dependencia:** {name}\n"
        f"- **Versión fija:** {version}\n"
        f"- **CVE:** [{cve}](https://nvd.nist.gov/vuln/detail/{cve})\n"
        f"- **Severidad:** {severity}\n"
        f"- **Descripción:** {desc}\n\n"
        f"---\n"
        f"*Generado automáticamente por CodeAudit Pro*"
    )

    if not GITHUB_TOKEN:
        _simular(f"Crear rama '{branch_name}' en {owner}/{repo}")
        _simular(f"Actualizar '{pkg_path}' con {name} → {version}")
        _simular(f"Crear PR: {title}")
        print(body)
        return True

    try:
        # 1. leer el manifiesto
        contenido, sha = _leer_manifiesto(owner, repo, pkg_path)
        lines = contenido.splitlines(keepends=True)
        nuevo = _actualizar_version(lines, name, version)

        # 2. obtener la referencia de la rama por defecto
        repo_info = _gh(f"{API_BASE}/repos/{owner}/{repo}")
        default_branch = repo_info.get("default_branch", "main")
        ref_info = _gh(f"{API_BASE}/repos/{owner}/{repo}/git/ref/heads/{default_branch}")

        # 3. crear la rama
        _gh(
            f"{API_BASE}/repos/{owner}/{repo}/git/refs",
            method="POST",
            payload={"ref": f"refs/heads/{branch_name}", "sha": ref_info["object"]["sha"]},
        )

        # 4. commit con el archivo actualizado
        import base64
        nuevo_b64 = base64.b64encode(nuevo.encode()).decode()
        _gh(
            f"{API_BASE}/repos/{owner}/{repo}/contents/{urllib.parse.quote(pkg_path, safe='')}",
            method="PUT",
            payload={
                "message": title,
                "content": nuevo_b64,
                "sha": sha,
                "branch": branch_name,
            },
        )

        # 5. crear el PR
        pr = _gh(
            f"{API_BASE}/repos/{owner}/{repo}/pulls",
            method="POST",
            payload={
                "title": title,
                "head": branch_name,
                "base": default_branch,
                "body": body,
            },
        )
        print(f"PR creado: {pr.get('html_url', 'desconocido')}")
        return True
    except Exception as exc:
        print(f"ERROR al corregir {name}: {exc}", file=sys.stderr)
        return False


# ---------------------------------------------------------------------------
# Issues de secretos
# ---------------------------------------------------------------------------

def create_secret_issue(secret: dict, repo_url: str) -> bool:
    """Crea un GitHub Issue para un secreto expuesto."""
    owner, repo = parse_repo_url(repo_url)
    archivo = secret.get("file", "desconocido")
    linea = secret.get("line", "?")
    kind = secret.get("type", secret.get("kind", "secreto"))

    title = f"\U0001f511 Secreto expuesto en {archivo}:{linea}"
    body = (
        f"## Secreto expuesto\n\n"
        f"Se ha detectado un **{kind}** en el archivo `{archivo}` línea **{linea}**.\n\n"
        f"### Acciones requeridas\n\n"
        f"1. **Rotar el secreto** inmediatamente (generar uno nuevo y reemplazarlo).\n"
        f"2. **Revocar la clave comprometida** en el proveedor correspondiente.\n"
        f"3. Revisar logs y accesos recientes para detectar usos no autorizados.\n"
        f"4. Ejecutar una nueva auditoría para confirmar que no hay más secretos expuestos.\n\n"
        f"---\n"
        f"*Generado automáticamente por CodeAudit Pro*"
    )

    if not GITHUB_TOKEN:
        _simular(f"Crear Issue en {owner}/{repo}: {title}")
        print(body)
        return True

    try:
        issue = _gh(
            f"{API_BASE}/repos/{owner}/{repo}/issues",
            method="POST",
            payload={
                "title": title,
                "body": body,
                "labels": ["security", "secret", "auto-generated"],
            },
        )
        print(f"Issue creado: {issue.get('html_url', 'desconocido')}")
        return True
    except Exception as exc:
        print(f"ERROR al crear issue para {archivo}:{linea}: {exc}", file=sys.stderr)
        return False


# ---------------------------------------------------------------------------
# orquestador
# ---------------------------------------------------------------------------

def remediate_all(repo_url: str, security_report: dict = None) -> dict:
    """Corrige vulnerabilidades y crea Issues para secretos."""
    if security_report is None:
        try:
            with open("reports/security-report.json") as f:
                security_report = json.load(f)
        except Exception as e:
            print(f"ERROR: no se pudo leer reports/security-report.json: {e}", file=sys.stderr)
            return {"pr_count": 0, "issue_count": 0, "pr_urls": [], "issue_urls": [], "errors": [str(e)]}

    resultado = {"pr_count": 0, "issue_count": 0, "pr_urls": [], "issue_urls": [], "errors": []}

    for vuln in security_report.get("vulnerable_dependencies", []):
        ok = fix_dependency_vuln(vuln, repo_url)
        if ok:
            resultado["pr_count"] += 1
        else:
            resultado["errors"].append(f"Fallo al procesar dependencia {vuln.get('name')}")

    for sec in security_report.get("secrets", []):
        ok = create_secret_issue(sec, repo_url)
        if ok:
            resultado["issue_count"] += 1
        else:
            resultado["errors"].append(f"Fallo al procesar secreto en {sec.get('file')}:{sec.get('line')}")

    return resultado


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Corrección automática de vulnerabilidades y creación de Issues."
    )
    parser.add_argument("--repo", required=True, help="URL del repositorio de GitHub")
    parser.add_argument("--report", default=None, help="Ruta al reporte de seguridad (JSON)")
    parser.add_argument("--dry-run", action="store_true", help="Simular sin realizar cambios")
    args = parser.parse_args()

    global GITHUB_TOKEN
    if args.dry_run or not GITHUB_TOKEN:
        os.environ.pop("GITHUB_TOKEN", None)
        GITHUB_TOKEN = ""

    if args.report:
        try:
            with open(args.report) as f:
                report = json.load(f)
        except Exception as e:
            print(f"ERROR: no se pudo leer {args.report}: {e}", file=sys.stderr)
            sys.exit(1)
    else:
        report = None

    res = remediate_all(args.repo, report)
    print("\n--- Resumen ---")
    print(f"  PRs creados:      {res['pr_count']}")
    print(f"  Issues creados:   {res['issue_count']}")
    print(f"  URLs de PRs:      {res['pr_urls']}")
    print(f"  URLs de Issues:   {res['issue_urls']}")
    if res["errors"]:
        for err in res["errors"]:
            print(f"  Error: {err}", file=sys.stderr)


if __name__ == "__main__":
    main()
