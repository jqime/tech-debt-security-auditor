#!/usr/bin/env python3
import csv
import os
import random
import sys
from pathlib import Path

DATA_DIR = Path(__file__).parent / "data"
OUTPUT_FILE = DATA_DIR / "leads.csv"

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
    with open(OUTPUT_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["name", "web", "email", "phone", "city", "radius_km"])
        writer.writeheader()
        writer.writerows(leads)
    print(f"✓ {len(leads)} leads guardados en {OUTPUT_FILE}")


def print_leads(leads: list[dict]):
    print(f"\n{'='*70}")
    print(f"  LEADS ENCONTRADOS ({len(leads)})")
    print(f"{'='*70}")
    for i, lead in enumerate(leads[:5], 1):
        print(f"\n  {i}. {lead['name']}")
        print(f"     Web:    {lead['web']}")
        print(f"     Email:  {lead['email']}")
        print(f"     Tel:    {lead['phone']}")


def main():
    if len(sys.argv) < 2:
        print("Uso: python3 prospect.py <CIUDAD> [radio_km]")
        print("Ej:  python3 prospect.py Madrid")
        sys.exit(1)

    city = sys.argv[1]
    radius = int(sys.argv[2]) if len(sys.argv) > 2 else 50

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


if __name__ == "__main__":
    main()
