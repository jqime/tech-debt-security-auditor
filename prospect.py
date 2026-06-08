#!/usr/bin/env python3
import csv
import json
import os
import random
import re
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path

DATA_DIR = Path(__file__).parent / "data"
OUTPUT_FILE = DATA_DIR / "leads.csv"
DOMAIN = os.getenv("DOMAIN", "http://localhost:5001")

MOCK_COMPANIES = [
    {"name": "InnovaDev SL", "web": "innovadev.es", "email": "info@innovadev.es", "phone": "+34 91 123 45 01"},
    {"name": "CodeCraft Solutions", "web": "codecraftsol.com", "email": "contact@codecraftsol.com", "phone": "+34 91 123 45 02"},
    {"name": "TechForge Digital", "web": "techforge.es", "email": "hello@techforge.es", "phone": "+34 91 123 45 03"},
    {"name": "WebWise Consulting", "web": "webwise-consulting.com", "email": "info@webwise-consulting.com", "phone": "+34 91 123 45 04"},
    {"name": "DataDriven Systems", "web": "datadrivensys.com", "email": "sales@datadrivensys.com", "phone": "+34 91 123 45 05"},
    {"name": "CloudNativa Tech", "web": "cloudnativa.es", "email": "info@cloudnativa.es", "phone": "+34 91 123 45 06"},
    {"name": "EcomBuilder", "web": "ecombuilder.com", "email": "contact@ecombuilder.com", "phone": "+34 91 123 45 07"},
    {"name": "PyME Digital Solutions", "web": "pymedigital.es", "email": "info@pymedigital.es", "phone": "+34 91 123 45 08"},
    {"name": "SecureCode Labs", "web": "securecodelabs.com", "email": "team@securecodelabs.com", "phone": "+34 91 123 45 09"},
    {"name": "AppGenius Factory", "web": "appgeniusfactory.com", "email": "info@appgeniusfactory.com", "phone": "+34 91 123 45 10"},
    {"name": "DevOps Madrid SL", "web": "devopsmadrid.com", "email": "hello@devopsmadrid.com", "phone": "+34 91 456 78 01"},
    {"name": "FullStack Pro", "web": "fullstackpro.es", "email": "info@fullstackpro.es", "phone": "+34 91 456 78 02"},
    {"name": "CyberShield Tech", "web": "cybershieldtech.com", "email": "contact@cybershieldtech.com", "phone": "+34 91 456 78 03"},
    {"name": "AI Startup Lab", "web": "aistartuplab.com", "email": "info@aistartuplab.com", "phone": "+34 91 456 78 04"},
    {"name": "Microservices Inc", "web": "microservicesinc.com", "email": "sales@microservicesinc.com", "phone": "+34 91 456 78 05"},
]


def generate_mock_leads(city: str, radius_km: int = 50):
    random.seed(hash(city) % (2 ** 31))
    sample = random.sample(MOCK_COMPANIES, min(10, len(MOCK_COMPANIES)))
    for c in sample:
        c["city"] = city
        c["radius_km"] = radius_km
    return sample


def save_leads(leads: list[dict]):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if not leads:
        return
    fieldnames = list(leads[0].keys())
    with open(OUTPUT_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(leads)
    print(f"✓ {len(leads)} leads guardados en {OUTPUT_FILE}")


def print_leads(leads: list[dict]):
    print(f"\n{'='*70}")
    print(f"  LEADS ENCONTRADOS ({len(leads)})")
    print(f"{'='*70}")
    for i, lead in enumerate(leads[:10], 1):
        print(f"\n  {i}. {lead.get('name', lead.get('repo_name', '??'))}")
        print(f"     Web:    {lead['web']}")
        print(f"     Email:  {lead['email']}")
        print(f"     Tel:    {lead['phone']}")


def scrape_github_commits(topic: str = "fintech", max_repos: int = 5) -> list[dict]:
    """Scrapea commits públicos de GitHub para extraer emails de desarrolladores."""
    leads = []
    GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")
    headers = ["Accept: application/vnd.github.v3+json"]
    if GITHUB_TOKEN:
        headers.append(f"Authorization: token {GITHUB_TOKEN}")

    print(f"🔍 Buscando repositorios sobre '{topic}' en GitHub...")
    search_url = f"https://api.github.com/search/repositories?q={topic}+in:topics+language:python&sort=stars&per_page={max_repos}"
    try:
        import urllib.request
        req = urllib.request.Request(search_url, headers={
            "Accept": "application/vnd.github.v3+json",
            **({"Authorization": f"token {GITHUB_TOKEN}"} if GITHUB_TOKEN else {}),
        })
        resp = urllib.request.urlopen(req, timeout=30)
        repos = json.loads(resp.read().decode()).get("items", [])

        for repo in repos[:max_repos]:
            repo_name = repo["full_name"]
            repo_url = repo["clone_url"]
            description = repo.get("description", "") or ""
            stars = repo.get("stargazers_count", 0)
            lang = repo.get("language", "Unknown")

            print(f"   📦 {repo_name} ({stars}⭐, {lang})")

            # Try to get commit authors
            commits_url = f"https://api.github.com/repos/{repo_name}/commits?per_page=10"
            try:
                req2 = urllib.request.Request(commits_url, headers={
                    "Accept": "application/vnd.github.v3+json",
                    **({"Authorization": f"token {GITHUB_TOKEN}"} if GITHUB_TOKEN else {}),
                })
                resp2 = urllib.request.urlopen(req2, timeout=15)
                commits = json.loads(resp2.read().decode())
                for commit in commits:
                    author = commit.get("commit", {}).get("author", {})
                    name = author.get("name", "")
                    email = author.get("email", "")
                    if email and "@" in email and not email.endswith("@github.com") and not email.endswith("@users.noreply.github.com"):
                        if not any(l["email"] == email for l in leads):
                            company = repo_name.split("/")[0]
                            leads.append({
                                "name": name,
                                "web": f"https://github.com/{repo_name.split('/')[0]}",
                                "email": email,
                                "phone": "",
                                "city": "",
                                "radius_km": 0,
                                "repo_url": repo_url,
                                "repo_name": repo_name,
                                "description": description[:120],
                                "stars": stars,
                                "topic": topic,
                                "source": "github_commits",
                                "created_at": datetime.now().isoformat(),
                            })
                            print(f"      → Lead: {name} <{email}>")
            except Exception as e:
                print(f"      ⚠️  Error obteniendo commits: {e}")

        print(f"   ✅ {len(leads)} leads extraídos de GitHub")
    except ImportError:
        print("   ⚠️  urllib no disponible")
    except Exception as e:
        print(f"   ⚠️  Error scraping GitHub: {e}")

    return leads


def inject_into_drip(leads: list[dict]):
    """Inyecta leads directamente en la secuencia de email marketing."""
    if not leads:
        return
    print(f"\n📧 Inyectando {len(leads)} leads en campaña de goteo regulatorio...")
    for lead in leads:
        repo_url = lead.get("repo_url", lead.get("web", ""))
        email = lead["email"]
        demo_data = {
            "repo_name": lead.get("repo_name", repo_url.split("/")[-1] if "/" in repo_url else "código"),
            "score": 45,
            "fine": "10.000.000",
            "hidden_count": 12,
            "n_criticos": 3,
            "sector": f"las empresas de {lead.get('topic', 'tecnología')}",
            "price": 299,
            "findings_summary": f"3 críticos y varios hallazgos totales (demo simulada)",
        }
        try:
            from email_sequences import send_sequence
            send_sequence(email, demo_data)
            print(f"   ✅ Secuencia iniciada para {email}")
        except Exception as e:
            print(f"   ⚠️  Error inyectando {email}: {e}")


def _parse_known_args():
    """Extrae flags comunes incluso si están intercalados."""
    args = {"topic": "python", "limit": 5, "drip": False, "mode": "city"}
    i = 1
    while i < len(sys.argv):
        a = sys.argv[i]
        if a in ("--github", "--topic") and i + 1 < len(sys.argv):
            args["topic"] = sys.argv[i + 1]
            args["mode"] = "github"
            i += 2
        elif a == "--limit" and i + 1 < len(sys.argv):
            args["limit"] = int(sys.argv[i + 1])
            i += 2
        elif a == "--drip":
            args["drip"] = True
            i += 1
        else:
            args.setdefault("positional", []).append(a)
            i += 1
    return args


def main():
    args = _parse_known_args()
    do_drip = args["drip"]

    if args["mode"] == "github":
        topic = args["topic"]
        limit = args["limit"]
        print(f"🔍 Buscando hasta {limit} repos sobre '{topic}' en GitHub...")
        leads = scrape_github_commits(topic, max_repos=limit)
        if leads:
            # Save to DB leads table
            try:
                from app.db import get_db
                db = get_db()
                for lead in leads:
                    db.execute(
                        "INSERT INTO leads (nombre, email, repo_url, mensaje, converted) VALUES (?, ?, ?, ?, 0)",
                        (lead["name"], lead["email"], lead.get("repo_url", ""),
                         f"GitHub prospect - {lead.get('topic', '')} - {lead.get('repo_name', '')}"),
                    )
                db.commit()
                db.close()
            except Exception:
                pass
            # Save CSV
            save_leads(leads)
            print_leads(leads)
            # Optional: inject into drip campaign
            if do_drip:
                inject_into_drip(leads)
        return

    city = args.get("positional", [None])[0] if args.get("positional") else None
    if not city:
        print("Uso: python3 prospect.py <CIUDAD|--topic <topic>> [--limit N] [--drip]")
        print("Ej:  python3 prospect.py --topic fintech --limit 20 --drip")
        print("Ej:  python3 prospect.py Madrid 50")
        sys.exit(1)
    radius = int(args.get("positional", [None, "50"])[1]) if len(args.get("positional", [])) > 1 else 50

    api_key = os.getenv("GOOGLE_MAPS_API_KEY")

    if api_key:
        print(f"🔍 Buscando empresas tecnológicas en {city} (radio {radius} km)...")
        try:
            import googlemaps
            gmaps = googlemaps.Client(key=api_key)
            places = gmaps.places_nearby(
                location=city,
                radius=radius * 1000,
                keyword="software empresa tecnología",
                language="es"
            )
            leads = []
            for place in places.get("results", []):
                leads.append({
                    "name": place.get("name"),
                    "web": place.get("website", f"https://{place.get('name', 'unknown').replace(' ', '').lower()}.es"),
                    "email": f"info@{place.get('name', 'unknown').replace(' ', '').lower()}.es",
                    "phone": place.get("formatted_phone_number", ""),
                    "city": city,
                    "radius_km": radius,
                })
            if not leads:
                print("ℹ️  No se encontraron resultados con API real. Usando datos simulados...")
                leads = generate_mock_leads(city, radius)
        except Exception as e:
            print(f"⚠️  Error con API Google Maps ({e}). Usando datos simulados...")
            leads = generate_mock_leads(city, radius)
    else:
        print(f"ℹ️  No hay GOOGLE_MAPS_API_KEY. Generando datos simulados para {city}...")
        print("   (Define la variable de entorno para usar datos reales)")
        leads = generate_mock_leads(city, radius)

    save_leads(leads)
    print_leads(leads)
    print(f"\n📁 CSV completo disponible en: {OUTPUT_FILE}")
    if do_drip:
        inject_into_drip(leads)


if __name__ == "__main__":
    main()
