"""Human-readable evidence; no assumed Moodle or pytest success."""
from collections import Counter
from pathlib import Path


def tree_lines(nodes, prefix=''):
    lines = []
    for i, node in enumerate(nodes):
        last = i == len(nodes) - 1
        lines.append(prefix + ('└── ' if last else '├── ') + node.title)
        lines.extend(tree_lines(node.children, prefix + ('    ' if last else '│   ')))
    return lines


def write_report(result, path: Path):
    course, assets, validation = result.course, result.assets, result.validation
    nodes = list(course.walk())
    headings = [h for d in course.documents for h in d.headings]
    levels = Counter(h['level'] for h in headings)
    images = [a for a in assets if a.kind == 'image']
    attachments = [a for a in assets if a.kind == 'attachment']
    features = Counter()
    for d in course.documents:
        features.update(d.features)
    rows = [
        '# Informe de validación', '',
        '- Markdown: ' + ', '.join(str(d.source) for d in course.documents),
        f'- Título: {course.title}',
        f'- Encabezados: {len(headings)}; ' + ', '.join(f'H{k}: {v}' for k, v in sorted(levels.items())),
        f'- Nodos SCORM / SCO: {len(nodes)}', f'- Páginas HTML: {len(nodes)}',
        f'- Imágenes encontradas: {features["image"]}',
        f'- Referencias de imágenes incluidas: {len(images)}; archivos únicos: {len({a.destination for a in images})}',
        f'- Adjuntos incorporados: {len({a.destination for a in attachments})}',
        f'- Tablas: {features["table_open"]}; bloques de código: {features["fence"] + features["code_block"]}',
        f'- ZIP: {result.output}', f'- Plantilla: {result.template}', '',
        '## Imágenes y adjuntos', '', '| Tipo | Referencia | Origen | Destino |', '|---|---|---|---|']
    for a in assets:
        values = [a.kind, a.reference, str(a.source), a.destination]
        rows.append('| ' + ' | '.join(v.replace('|', '\\|') for v in values) + ' |')
    rows += ['', '## Comprobaciones', '']
    rows += ['- CORRECTO: ' + check for check in validation.checks]
    rows += ['', '## Advertencias', '']
    rows += ['- ' + warning for warning in course.warnings + validation.warnings] or ['- Ninguna.']
    rows += ['', '## Errores pendientes', '']
    rows += ['- ' + error for error in validation.errors] or ['- Ningún error estructural detectado.']
    rows += ['', '## Pruebas externas', '',
             '- pytest: no ejecutado por el exportador; véase la evidencia añadida por la ejecución de pruebas.',
             '- Navegador: no ejecutado por el exportador.',
             '- Moodle: no se ha realizado una importación en un LMS real. La validación estructural no la sustituye.',
             '', '## Árbol de contenidos', '', '```text', course.title]
    rows += tree_lines(course.nodes) + ['```', '']
    path.write_text('\n'.join(rows), encoding='utf-8')
