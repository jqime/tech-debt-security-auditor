import os
import shutil
import sys


class ToolMissingError(RuntimeError):
    pass


REQUIRED_TOOLS = {
    "trivy": {
        "desc": "Escáner de vulnerabilidades en dependencias",
        "install": "https://trivy.dev/latest/getting-started/installation/",
        "verify": lambda v: "trivy" in v.lower(),
    },
    "semgrep": {
        "desc": "SAST multi-lenguaje",
        "install": "pip install semgrep  o  https://semgrep.dev/docs/getting-started/",
        "verify": lambda v: "semgrep" in v.lower(),
    },
    "bandit": {
        "desc": "SAST especializado Python",
        "install": "pip install bandit",
        "verify": lambda v: "bandit" in v.lower(),
    },
    "trufflehog": {
        "desc": "Detección de secretos por regex/entropía",
        "install": "pip install truffleHog  o  https://github.com/trufflesecurity/trufflehog",
        "verify": lambda v: "truffle" in v.lower(),
    },
}

OPTIONAL_TOOLS = {
    "lizard": {
        "desc": "Medición de complejidad ciclomática",
        "install": "pip install lizard",
        "verify": lambda v: "lizard" in v.lower(),
    },
    "radon": {
        "desc": "Métricas de código Python (complejidad, duplicación)",
        "install": "pip install radon",
        "verify": lambda v: "radon" in v.lower(),
    },
}


def _check_tool(name: str, info: dict) -> tuple[bool, str]:
    path = shutil.which(name)
    if not path:
        return False, f"{name} no encontrado en PATH. Instalación: {info['install']}"
    return True, f"{name} encontrado en {path}"


def check_tools(raise_on_missing: bool = True) -> dict[str, str]:
    results = {}
    all_ok = True

    print("🔧 Verificando herramientas de auditoría...")
    print()

    for name, info in REQUIRED_TOOLS.items():
        ok, msg = _check_tool(name, info)
        status = "✅" if ok else "❌"
        results[name] = "ok" if ok else f"missing: {info['install']}"
        print(f"  {status} {name:20s} — {info['desc']}")
        if not ok:
            print(f"     {msg}")
            all_ok = False

    print()
    for name, info in OPTIONAL_TOOLS.items():
        ok, msg = _check_tool(name, info)
        status = "✅" if ok else "⚠️"
        results[name] = "ok" if ok else "missing (optional)"
        print(f"  {status} {name:20s} — {info['desc']}")

    print()
    if all_ok:
        print("✅ Todas las herramientas requeridas están disponibles.")
    else:
        print("❌ Faltan herramientas requeridas.")
        if raise_on_missing:
            missing = [n for n, r in results.items() if r.startswith("missing")]
            raise ToolMissingError(
                f"Faltan herramientas: {', '.join(missing)}. "
                "Instálalas antes de ejecutar auditorías."
            )
    return results


if __name__ == "__main__":
    try:
        check_tools(raise_on_missing=False)
    except ToolMissingError as e:
        print(f"\n❌ {e}")
        sys.exit(1)
