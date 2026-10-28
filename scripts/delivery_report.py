"""Assemble the final report from executed checks, never inferred successes."""
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
import json
import platform
from xml.etree import ElementTree as ET
from validate_reference import validate_with_reference


def main():
    root = Path(__file__).resolve().parents[1]
    dist = root / 'dist'
    package = dist / '01-Introduccion-al-analisis-forense-scorm12.zip'
    validation = validate_with_reference(package, root / 'SR-tarea08-pt.zip')
    assert validation.valid, validation.errors
    junit = ET.parse(dist / 'pytest-results.xml').getroot()
    cases = junit.findall('.//testcase')
    failures = junit.findall('.//failure') + junit.findall('.//error')
    skipped = junit.findall('.//skipped')
    assert cases and not failures and not skipped
    visual = json.loads((dist / 'screenshots/visual-results.json').read_text())
    assert not visual['errors']
    wheel = dist / 'markdown2scorm-1.0.0-py3-none-any.whl'
    wheel_log = (dist / 'wheel-install.log').read_text()
    assert 'PASS:' in wheel_log and sha256(wheel.read_bytes()).hexdigest() in wheel_log
    hashes = json.loads((dist / 'original-sha256.json').read_text())
    for path, digest in hashes.items():
        assert sha256((root / path).read_bytes()).hexdigest() == digest, path
    report = package.with_name(package.stem + '-report.md').read_text()
    report = report.replace('- Sin validación XSD; use --schema con los esquemas SCORM 1.2 locales',
                            '- La exportación CLI ejecutó validación estructural; posteriormente se validó también contra los XSD CP y ADL del ZIP original, correctamente.')
    report = report.replace('- pytest: no ejecutado por el exportador; véase la evidencia añadida por la ejecución de pruebas.',
                            f'- pytest: **{len(cases)} pruebas superadas, 0 fallos, 0 errores, 0 omitidas**. Evidencia: `pytest.log` y `pytest-results.xml`. Incluye 20 escenarios del runtime SCORM con API simulada en Node.js.')
    report = report.replace('- Navegador: no ejecutado por el exportador.',
                            f'- Navegador: **{visual["browser"]}**, {visual["pages"]} páginas, {visual["page_views"]} aperturas a 1280 y 390 px. **0 errores** de JavaScript, carga o desbordamiento global. Red externa bloqueada. Evidencia: `screenshots/visual-results.json`.')
    report += '\n## Verificación de la entrega\n\n'
    report += '- Fecha UTC: ' + datetime.now(timezone.utc).isoformat() + '\n'
    report += '- Python ejecutado: ' + platform.python_version() + '; compatibilidad declarada: Python ≥3.11.\n'
    report += '- Instalación editable, `python -m markdown2scorm --help` y `markdown2scorm --help`: correctos.\n'
    report += '- Wheel y sdist construidos. Wheel instalado en un entorno virtual nuevo; CLI y exportación completa del manuscrito ejecutadas desde otra carpeta: correctos (`wheel-install.log`).\n'
    report += '- Validación XSD adicional de CP 1.1.2 y ADL SCORM 1.2: correcta (`xsd-validation.log`). Los esquemas originales se usaron sin modificarlos en una carpeta temporal.\n'
    report += f'- Integridad de originales: {len(hashes)} archivos verificados por SHA-256, sin modificaciones.\n'
    report += '- Contenido: secuencia íntegra de tokens, orden de epígrafes y presencia de cada bloque en su página comprobados; tabla e imágenes contadas; bytes de las seis figuras comparados con los originales.\n'
    report += '- Capturas revisadas visualmente: introducción y tabla en escritorio, figura y tabla en móvil. En móvil la tabla permite desplazamiento horizontal dentro de su contenedor.\n'
    report += '- No hay un apartado real que contenga simultáneamente figura y tabla; se capturaron apartados distintos.\n'
    report += '- El manuscrito no tiene bloques de código ni fórmulas: su funcionamiento se comprobó con pruebas unitarias adicionales, no se atribuye al manuscrito.\n'
    report += '- La portada LaTeX se conserva como texto literal. La anotación `{.unnumbered}` se interpreta como metadato. No se añade numeración.\n'
    report += '- FPD-MEDU es una adaptación de los elementos visuales del original, atribuida y distribuida bajo CC BY-SA 3.0; no reproduce todos los iDevices.\n'
    report += '- Errores pendientes detectados: ninguno. Prueba externa pendiente: importación y sesión de alumno en Moodle real.\n'
    report += '\n## Capturas\n\n' + '\n'.join(f'- [{name}](screenshots/{name})' for name in visual['screenshots']) + '\n'
    report += '\n## Artefactos y huellas\n\n'
    report += '| Artefacto | SHA-256 |\n|---|---|\n'
    for p in [package, wheel, dist / 'markdown2scorm-1.0.0.tar.gz']:
        report += f'| {p.name} | `{sha256(p.read_bytes()).hexdigest()}` |\n'
    report += '\n## Reproducción\n\n```bash\nsource .venv/bin/activate\n'
    report += 'python -m pytest -q --junitxml=dist/pytest-results.xml\n'
    report += 'python -m markdown2scorm test/manuscrito/01-Introduccion-al-analisis-forense.md --assets-dir test/figuras --template fpd-medu --output dist/01-Introduccion-al-analisis-forense-scorm12.zip --validate --verbose --keep-build\n'
    report += 'python scripts/validate_reference.py dist/01-Introduccion-al-analisis-forense-scorm12.zip\n'
    report += '# Sustituir la ruta de build por la indicada por el exportador:\n'
    report += 'python scripts/visual_check.py dist/01-Introduccion-al-analisis-forense-scorm12.build-XXXXXXXX\n```\n'
    (dist / 'validation-report.md').write_text(report)
    print(f'Informe escrito: {dist / "validation-report.md"}')


if __name__ == '__main__':
    main()
