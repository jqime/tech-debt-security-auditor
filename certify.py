#!/usr/bin/env python3
import hashlib
import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path

PROJECT_DIR = Path(__file__).parent
REPORTS_DIR = PROJECT_DIR / "reports"
HASHES_LOG = REPORTS_DIR / "hashes.log"


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def try_opentimestamps(hash_hex: str) -> str | None:
    try:
        result = subprocess.run(
            ["ots", "stamp"],
            input=hash_hex.encode(),
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode == 0:
            return "ots_stamped"
    except (FileNotFoundError, PermissionError, OSError):
        pass
    print("  ℹ️  OpenTimestamps CLI no instalado. Skipping blockchain anchor.")
    return None


def embed_in_html(report_path: Path, hash_hex: str):
    if not report_path.exists():
        return
    html = report_path.read_text(encoding="utf-8")
    DOMAIN = os.getenv("DOMAIN", "https://codeauditpro.com")
    cert_block = f"""
<!-- CERTIFY BLOCK -->
<div style="background:#131b2e;border:1px solid #6366f1;border-radius:16px;padding:1.5rem;margin:2rem 0" id="certify">
<h3 style="color:#a5b4fc;">🔏 Certificado de integridad</h3>
<p style="color:#94a3b8;font-size:0.85rem;">
Este informe ha sido certificado digitalmente para garantizar su integridad.<br>
<strong>SHA-256:</strong> <code style="background:#1e293b;padding:4px 8px;border-radius:4px;word-break:break-all;color:#cbd5e1">{hash_hex}</code><br>
<strong>Fecha:</strong> {datetime.now().isoformat()}<br>
<strong>Verificar:</strong> <code style="background:#1e293b;padding:4px 8px;border-radius:4px;">sha256sum {report_path.name}</code>
</p>
<div style="margin-top:1rem;padding-top:1rem;border-top:1px solid #1e293b;text-align:center">
<p style="color:#94a3b8;font-size:0.75rem;margin-bottom:0.5rem;">
✅ Auditado y certificado por <strong style="color:#a5b4fc;">CodeAudit Pro</strong>
</p>
<p style="font-size:0.72rem;color:#64748b;">
¿Tu software cumple con la normativa europea NIS2/DORA?<br>
<a href="{DOMAIN}/try-now" style="color:#818cf8;font-weight:600;">→ Escanea tu repositorio gratis en 2 minutos</a>
</p>
</div>
</div>
<!-- END CERTIFY BLOCK -->
"""
    if "<!-- CERTIFY BLOCK -->" in html:
        html = html.split("<!-- CERTIFY BLOCK -->")[0] + cert_block + html.split("<!-- END CERTIFY BLOCK -->")[-1]
    else:
        html = html.replace("</body>", cert_block + "\n</body>")
    report_path.write_text(html, encoding="utf-8")


def generate_qr_code(data: str, output_path: Path):
    try:
        import qrcode
        img = qrcode.make(data)
        img.save(str(output_path))
        print(f"  ✓ Código QR generado: {output_path}")
    except ImportError:
        print("  ℹ️  qrcode no instalado. Salteando QR.")


def certify(report_name: str = "executive-report.html"):
    report_path = REPORTS_DIR / report_name
    if not report_path.exists():
        print(f"❌ No se encuentra {report_path}")
        return False

    print(f"🔏 Certificando {report_name}...")
    hash_hex = sha256_file(report_path)
    print(f"  SHA-256: {hash_hex}")

    embed_in_html(report_path, hash_hex)

    qr_path = REPORTS_DIR / "verify-qr.png"
    verify_url = f"https://github.com/jqime/tech-debt-security-auditor?hash={hash_hex[:12]}"
    generate_qr_code(verify_url, qr_path)

    ots_status = try_opentimestamps(hash_hex)

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    new_entry = f"{datetime.now().isoformat()} | {report_name} | SHA256:{hash_hex} | blockchain:{ots_status or 'none'}\n"
    if HASHES_LOG.exists():
        existing = HASHES_LOG.read_text(encoding="utf-8")
    else:
        existing = ""
    fd, tmp_path = tempfile.mkstemp(dir=str(REPORTS_DIR), prefix=".hashes-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(existing + new_entry)
        os.replace(tmp_path, str(HASHES_LOG))
    except Exception:
        os.unlink(tmp_path)
        raise

    print(f"  ✓ Hash registrado en {HASHES_LOG}")
    print(f"  ✓ Bloque de integridad insertado en {report_path}")
    return True


def verify(report_name: str = "executive-report.html"):
    report_path = REPORTS_DIR / report_name
    if not report_path.exists():
        print(f"❌ No se encuentra {report_path}")
        return False

    current_hash = sha256_file(report_path)
    print(f"🔍 Verificando integridad de {report_name}")
    print(f"  Hash actual: {current_hash}")

    if HASHES_LOG.exists():
        with open(HASHES_LOG, encoding="utf-8") as f:
            for line in f:
                if report_name in line and current_hash in line:
                    print(f"  ✅ Hash coincide con registro en hashes.log")
                    return True
        print(f"  ⚠️  Hash no encontrado en hashes.log")

    return False


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Certificación de integridad de informes")
    parser.add_argument("--certify", help="Nomobre del reporte a certificar (default: executive-report.html)", nargs="?", const="executive-report.html")
    parser.add_argument("--verify", help="Verificar integridad", nargs="?", const="executive-report.html")
    parser.add_argument("--report", default="executive-report.html", help="Ruta del reporte")

    args = parser.parse_args()

    if args.verify:
        verify(args.verify)
    else:
        certify(args.certify or args.report)


if __name__ == "__main__":
    main()
