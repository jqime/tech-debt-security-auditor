# Contribuir a CodeAudit Pro

Gracias por tu interés en contribuir. Este documento establece las normas para reportar issues y enviar pull requests.

## Reportar Issues

1. Usa la plantilla de issue en GitHub.
2. Incluye: versión del proyecto, comando ejecutado, mensaje de error completo, sistema operativo.
3. Marca si es bug, feature request o duda.

## Entorno de Desarrollo

```bash
git clone https://github.com/jqime/tech-debt-security-auditor
cd tech-debt-security-auditor

# Dependencias Python
pip install -r requirements.txt

# Herramientas externas (obligatorio para escáneres reales)
pip install semgrep bandit truffleHog weasyprint qrcode[pil]
# Trivy: https://trivy.dev/latest/getting-started/installation/
```

## Convenciones de Código

- **Python 3.10+** — type hints opcionales pero recomendados.
- **Snake case** para archivos, funciones y variables.
- **Shebang** `#!/usr/bin/env python3` en scripts ejecutables.
- **Rutas**: usar `Path(__file__).parent` para obtener la raíz del proyecto.
- **Variables de entorno** para secrets (nunca hardcodear).
- **CLI** con `argparse` y `--help` descriptivo.
- **Idioma**: español para interfaz de usuario; inglés para código técnico.

## Pull Requests

1. Crea una rama desde `main`: `git checkout -b feat/mi-cambio`.
2. Commits convencionales: `feat:`, `fix:`, `refactor:`, `docs:`, `chore:`.
3. Ejecuta la sintaxis: `python3 -c "import py_compile; py_compile.compile('tu_script.py', doraise=True)"`.
4. Verifica que `test_compliance.sh` funciona sin errores.
5. Abre el PR con descripción clara del cambio y screenshots si aplica.

## Estructura del Proyecto

Ver `README.md` para la estructura de directorios.
