"""Read-only ZIP validator; never extract untrusted archive paths."""
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
import posixpath
import re
import stat
from urllib.parse import unquote, urlsplit
from zipfile import ZipFile, BadZipFile

from lxml import etree, html
from .manifest import CP, ADL, NS
from .assets import DANGEROUS, check_svg
from .models import ConversionError


@dataclass
class ValidationResult:
    checks: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def valid(self):
        return not self.errors


def local_target(base, reference):
    url = urlsplit(reference)
    path = unquote(url.path)
    if url.scheme in {'http', 'https', 'mailto', 'tel'} or url.netloc:
        return None
    if url.scheme or path.startswith('/') or '\\' in path or '\x00' in path:
        raise ValueError(f'ruta absoluta o protocolo no permitido: {reference}')
    resolved = posixpath.normpath(posixpath.join(posixpath.dirname(base), path)) if path else base
    if resolved == '..' or resolved.startswith('../'):
        raise ValueError(f'ruta fuera del paquete: {reference}')
    return resolved


def validate_package(path: Path, expected_pages=None, schema: Path | None = None) -> ValidationResult:
    result = ValidationResult()
    try:
        with ZipFile(path) as z:
            infos = z.infolist()
            names = [i.filename for i in infos]
            if len(names) != len(set(names)):
                result.errors.append('Nombres duplicados en ZIP')
            if len(names) > 20000 or sum(i.file_size for i in infos) > 512 * 1024 * 1024:
                result.errors.append('ZIP supera los límites de validación (20000 archivos / 512 MiB)')
                return result
            for info in infos:
                name = info.filename
                p = PurePosixPath(name)
                if p.is_absolute() or '..' in p.parts or '\\' in name or ':' in name or stat.S_ISLNK(info.external_attr >> 16):
                    result.errors.append(f'Ruta ZIP insegura: {name}')
                if any(x.startswith('.') or x in {'__pycache__', 'node_modules'} for x in p.parts):
                    result.errors.append(f'Archivo de desarrollo: {name}')
                if p.suffix.lower() in DANGEROUS - {'.html', '.js', '.css'}:
                    result.errors.append(f'Archivo peligroso: {name}')
                if p.suffix.lower() == '.js' and name != 'runtime/scorm12.js':
                    result.errors.append(f'JavaScript inesperado: {name}')
            if result.errors:
                return result
            bad = z.testzip()
            if bad:
                result.errors.append(f'CRC incorrecto: {bad}')
                return result
            result.checks.append('ZIP legible, CRC correctos y rutas de extracción seguras')
            if 'imsmanifest.xml' not in names:
                result.errors.append('Falta imsmanifest.xml en la raíz')
                return result
            xml = z.read('imsmanifest.xml')
            if b'<!DOCTYPE' in xml.upper() or b'<!ENTITY' in xml.upper():
                result.errors.append('DTD o entidades XML no permitidas')
                return result
            root = etree.fromstring(xml, etree.XMLParser(resolve_entities=False, no_network=True))
            if root.tag != '{' + CP + '}manifest' or ADL not in root.nsmap.values():
                result.errors.append('Espacios de nombres distintos de SCORM 1.2')
            if root.findtext('cp:metadata/cp:schema', namespaces=NS) != 'ADL SCORM' or root.findtext('cp:metadata/cp:schemaversion', namespaces=NS) != '1.2':
                result.errors.append('Metadatos SCORM 1.2 ausentes')
            orgs = root.find('cp:organizations', NS)
            if orgs is None or not orgs.findall('cp:organization', NS):
                result.errors.append('Falta organización')
            else:
                organizations = orgs.findall('cp:organization', NS)
                if orgs.get('default') not in {o.get('identifier') for o in organizations}:
                    result.errors.append('Organización por defecto inválida')
                for org in organizations:
                    if not org.findtext('cp:title', namespaces=NS) or not org.findall('cp:item', NS):
                        result.errors.append('Organización sin título o contenidos')
            ids = [e.get('identifier') for e in root.iter() if e.get('identifier') is not None]
            if len(ids) != len(set(ids)) or any(not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_.-]*', i) for i in ids):
                result.errors.append('Identificadores duplicados o no válidos')
            resources = {e.get('identifier'): e for e in root.findall('cp:resources/cp:resource', NS)}
            for el in root.iter():
                ref = el.get('identifierref')
                if ref and ref not in resources:
                    result.errors.append(f'identifierref desconocido: {ref}')
            pages = set()
            declared = set()
            for resource in resources.values():
                kind = resource.get('{' + ADL + '}scormtype')
                if kind not in {'sco', 'asset'} or resource.get('type') != 'webcontent':
                    result.errors.append('Recurso sin scormtype/type válido')
                if kind == 'sco':
                    href = resource.get('href')
                    if not href or not href.endswith('.html'):
                        result.errors.append('SCO sin href HTML válido')
                    else:
                        target = local_target('imsmanifest.xml', href)
                        if target is None or target not in names:
                            result.errors.append(f'HTML de SCO inexistente: {href}')
                        else:
                            pages.add(target)
                            files = {f.get('href') for f in resource.findall('cp:file', NS)}
                            if href not in files:
                                result.errors.append(f'SCO no declara su propio HTML: {href}')
                for f in resource.findall('cp:file', NS):
                    href = f.get('href', '')
                    target = local_target('imsmanifest.xml', href)
                    if not href or target is None or target not in names:
                        result.errors.append(f'Archivo declarado inexistente o externo: {href}')
                    else:
                        declared.add(target)
            if not pages:
                result.errors.append('No existen SCO')
            all_html = {n for n in names if n.endswith('.html')}
            if all_html != pages:
                result.errors.append('Hay páginas HTML no asociadas con SCO')
            if expected_pages is not None and pages != set(expected_pages):
                result.errors.append('No coinciden los HTML esperados con los SCO declarados')
            undeclared = set(names) - declared - {'imsmanifest.xml'}
            if undeclared:
                result.errors.append('Archivos sin declarar: ' + ', '.join(sorted(undeclared)))
            documents = {}
            for name in sorted(pages):
                doc = html.fromstring(z.read(name))
                documents[name] = doc
                ids = doc.xpath('//@id')
                if len(ids) != len(set(ids)):
                    result.errors.append(f'IDs HTML duplicados: {name}')
                if not doc.xpath('//html[@lang]') or not doc.xpath('//title') or not doc.xpath('//main'):
                    result.errors.append(f'HTML sin estructura semántica: {name}')
                scripts = doc.xpath('//script')
                if len(scripts) != 1 or scripts[0].get('src') != '../runtime/scorm12.js' or scripts[0].text:
                    result.errors.append(f'Runtime ausente o scripts inesperados: {name}')
                if doc.xpath('//iframe | //object | //embed'):
                    result.errors.append(f'Contenido activo inesperado: {name}')
                for el in doc.iter():
                    if any(a.lower().startswith('on') for a in el.attrib):
                        result.errors.append(f'Manejador JavaScript embebido: {name}')
                for el in doc.xpath('//*[@src or @href]'):
                    ref = el.get('src') or el.get('href')
                    target = local_target(name, ref)
                    if target is None:
                        if el.tag != 'a':
                            result.errors.append(f'Recurso remoto obligatorio: {name}: {ref}')
                        continue
                    if target not in names:
                        result.errors.append(f'Enlace roto: {name}: {ref}')
            for name, doc in documents.items():
                for ref in doc.xpath('//a/@href'):
                    parsed = urlsplit(ref)
                    target = local_target(name, ref)
                    if target in documents and parsed.fragment:
                        if unquote(parsed.fragment) not in documents[target].xpath('//@id'):
                            result.errors.append(f'Ancla inexistente: {name}: {ref}')
            runtime = Path(__file__).parent / 'runtime/scorm12.js'
            if 'runtime/scorm12.js' not in names or z.read('runtime/scorm12.js') != runtime.read_bytes():
                result.errors.append('El runtime no coincide con la versión probada')
            for name in names:
                if name.endswith('.svg'):
                    check_svg(z.read(name), name)
                if name.endswith('.css'):
                    css = z.read(name).decode('utf-8')
                    if re.search(r'@import|expression\s*\(', css, re.I):
                        result.errors.append(f'CSS activo o importación no permitida: {name}')
                    for reference in re.findall(r'url\(\s*[\'"]?([^\)\'"\s]+)', css, re.I):
                        target = local_target(name, reference)
                        if target is None or target not in names:
                            result.errors.append(f'Recurso CSS inexistente: {name}: {reference}')
            if schema:
                xsd = etree.XMLSchema(etree.parse(str(schema), etree.XMLParser(no_network=True, resolve_entities=False)))
                if not xsd.validate(root):
                    result.errors.append('XSD: ' + str(xsd.error_log))
                else:
                    result.checks.append('Manifiesto validado contra XSD local proporcionado')
            else:
                result.warnings.append('Sin validación XSD; use --schema con los esquemas SCORM 1.2 locales')
            if not result.errors:
                result.checks.extend(['Manifiesto SCORM 1.2: namespaces, metadatos y organización correctos',
                    'Identificadores únicos y referencias SCO resueltas',
                    f'{len(pages)} páginas HTML declaradas y presentes',
                    'Todos los archivos declarados existen; no hay archivos sobrantes',
                    'Imágenes, adjuntos, CSS y enlaces internos resuelven en el paquete',
                    'Runtime SCORM presente y sin scripts adicionales',
                    'Sin rutas absolutas locales ni recursos remotos obligatorios'])
    except (BadZipFile, OSError, etree.LxmlError, ValueError, KeyError, RuntimeError, ConversionError) as exc:
        result.errors.append(f'Validación fallida: {exc}')
    return result
