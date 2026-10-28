"""Resolve only authorized local files, preserving bytes and extensions."""
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
import re
from urllib.parse import unquote, urlsplit

from lxml import etree
from .models import ConversionError

DANGEROUS = {'.exe', '.com', '.bat', '.cmd', '.ps1', '.sh', '.py', '.pyc', '.dll',
             '.so', '.js', '.mjs', '.html', '.htm', '.xhtml', '.php', '.jar', '.msi', '.css'}
IMAGES = {'.png', '.jpg', '.jpeg', '.gif', '.svg', '.webp'}


@dataclass
class Asset:
    source: Path
    destination: str
    reference: str
    kind: str
    document: Path
    line: int


def check_svg(data: bytes, name: str):
    if b'<!DOCTYPE' in data.upper() or b'<!ENTITY' in data.upper():
        raise ConversionError(f'SVG inseguro: {name}: DTD o entidades')
    try:
        root = etree.fromstring(data, etree.XMLParser(resolve_entities=False, no_network=True))
    except etree.XMLSyntaxError as exc:
        raise ConversionError(f'SVG inválido: {name}: {exc}') from exc
    for el in root.iter():
        if not isinstance(el.tag, str):
            continue
        if etree.QName(el).localname.lower() in {'script', 'foreignobject', 'iframe', 'style', 'animate', 'set', 'animatetransform'}:
            raise ConversionError(f'SVG activo no permitido: {name}')
        for attr, value in el.attrib.items():
            local = etree.QName(attr).localname.lower()
            urls = re.findall(r'url\(\s*[\'"]?([^\)\'"\s]+)', value, re.I)
            if local.startswith('on') or local == 'style' or any(not u.startswith('#') for u in urls):
                raise ConversionError(f'SVG activo no permitido: {name}')
            if local in {'href', 'src'} and not value.startswith('#'):
                raise ConversionError(f'SVG con recurso externo no permitido: {name}')


class AssetManager:
    def __init__(self, build: Path, sources: list[Path], search_dirs=(), allow_missing=False):
        self.build = build
        self.search_dirs = [Path(p).resolve() for p in search_dirs]
        for p in self.search_dirs:
            if not p.is_dir():
                raise ConversionError(f'No existe el directorio de recursos: {p}')
        self.roots = [Path(p).resolve().parent for p in sources] + self.search_dirs
        self.allow_missing = allow_missing
        self.records: list[Asset] = []
        self.warnings: list[str] = []

    def authorized(self, path):
        return any(path.is_relative_to(root) for root in self.roots)

    def resolve(self, reference: str, source: Path, line: int) -> Path | None:
        url = urlsplit(reference)
        relative = unquote(url.path)
        if url.scheme or url.netloc or relative.startswith('/') or '\\' in relative or '\x00' in relative:
            raise ConversionError(f'{source.name}:{line}: ruta local no permitida: {reference}')
        candidate = (source.parent / relative).resolve()
        if candidate.is_file():
            if not self.authorized(candidate):
                raise ConversionError(f'{source.name}:{line}: recurso fuera de directorios autorizados: {reference}; use --assets-dir')
            return candidate
        if not self.authorized(candidate):
            raise ConversionError(f'{source.name}:{line}: ruta fuera de directorios autorizados: {reference}')
        matches = set()
        for directory in self.search_dirs:
            for p in [directory / relative, directory / Path(relative).name]:
                resolved = p.resolve()
                if p.is_file():
                    if not self.authorized(resolved):
                        raise ConversionError(f'Enlace simbólico fuera de directorios autorizados: {reference}')
                    matches.add(resolved)
        if len(matches) > 1:
            raise ConversionError(f'{source.name}:{line}: recurso ambiguo {reference}: ' + ', '.join(map(str, sorted(matches))))
        if matches:
            return matches.pop()
        message = f'{source.name}:{line}: no se encuentra el recurso local {reference}'
        if not self.allow_missing:
            raise ConversionError(message)
        self.warnings.append(message + ' (permitido explícitamente)')
        return None

    def copy(self, reference: str, source: Path, line: int, kind: str) -> str | None:
        path = self.resolve(reference, source, line)
        if path is None:
            return None
        suffix = path.suffix
        if suffix.lower() in DANGEROUS or path.name.startswith('.'):
            raise ConversionError(f'Archivo activo o de desarrollo no permitido: {reference}')
        if kind == 'image' and suffix.lower() not in IMAGES:
            raise ConversionError(f'Formato de imagen no soportado: {reference}')
        data = path.read_bytes()
        if suffix.lower() == '.svg':
            check_svg(data, reference)
        destination = f'assets/{sha256(data).hexdigest()}{suffix}'
        target = self.build / destination
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists():
            target.write_bytes(data)
        self.records.append(Asset(path, destination, reference, kind, source, line))
        return '../' + destination
