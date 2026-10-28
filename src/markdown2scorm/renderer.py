"""Safe Markdown → HTML; math is compiled to native, offline MathML."""
from copy import deepcopy
from html import escape
from pathlib import Path
from urllib.parse import unquote, urlsplit, quote
import re

from jinja2 import Environment, FileSystemLoader, StrictUndefined, select_autoescape
from latex2mathml.converter import convert
from lxml import etree, html
from markupsafe import Markup
from pygments import highlight
from pygments.formatters import HtmlFormatter
from pygments.lexers import get_lexer_by_name, TextLexer
from pygments.util import ClassNotFound

from .models import ConversionError
from .parser import make_parser, walk_tokens

TEMPLATES = Path(__file__).parent / 'templates'


def code_highlight(code, language, attrs):
    try:
        lexer = get_lexer_by_name(language, stripnl=False, ensurenl=False)
    except ClassNotFound:
        lexer = TextLexer(stripnl=False, ensurenl=False)
    # Pygments normalizes tabs/line endings; source tokens already follow CommonMark.
    rendered = highlight(code, lexer, HtmlFormatter(nowrap=True))
    # The formatter appends a newline even for input without a final newline.
    if not code.endswith('\n') and rendered.endswith('\n'):
        rendered = rendered[:-1]
    return '<pre class="highlight"><code>' + rendered + '</code></pre>\n'


def renderer_for(warnings):
    md = make_parser()
    md.options['highlight'] = code_highlight

    def math_rule(tokens, idx, options, env):
        token = tokens[idx]
        block = 'block' in token.type or 'double' in token.type
        try:
            value = convert(token.content, display='block' if block else 'inline')
            root = etree.fromstring(value.encode())
            # TeX must not create active URL/style attributes or foreign elements.
            for el in root.iter():
                if etree.QName(el).namespace != 'http://www.w3.org/1998/Math/MathML':
                    raise ValueError('elemento MathML no permitido')
                for name in list(el.attrib):
                    if etree.QName(name).localname.lower() in {'href', 'src', 'style'} or name.lower().startswith('on'):
                        raise ValueError('atributo matemático activo')
            if any((el.text or '').startswith('\\') for el in root.iter()):
                raise ValueError('comando LaTeX no reconocido')
            return value
        except Exception as exc:
            warnings.append(f'Fórmula conservada literalmente: {token.content!r}: {exc}')
            return '<code class="math-fallback">' + escape(token.content) + '</code>'

    for name in ['math_inline', 'math_inline_double', 'math_block', 'math_block_label', 'math_block_eqno']:
        md.renderer.rules[name] = math_rule
    md.renderer.rules['latex_source'] = lambda ts, i, opts, env: '<pre class="latex-source">' + escape(ts[i].content) + '</pre>\n'
    md.renderer.rules['table_open'] = lambda *args: '<div class="table-scroll" role="region" aria-label="Tabla" tabindex="0"><table>\n'
    md.renderer.rules['table_close'] = lambda *args: '</table></div>\n'
    return md


def render_course(course, assets, build: Path, template: str):
    template_path = TEMPLATES / template
    if not template_path.is_dir() or '/' in template or '\\' in template:
        raise ConversionError(f'Plantilla desconocida: {template}')
    env = Environment(loader=FileSystemLoader(template_path), autoescape=select_autoescape(), undefined=StrictUndefined)
    page = env.get_template('page.html')
    md = renderer_for(course.warnings)
    docs = {d.source: d for d in course.documents}
    fragments = {}
    anchors = {}
    first_pages = {}
    for doc in course.documents:
        first_pages[doc.source] = next(doc.walk()).href
    for node in course.walk():
        doc = docs[node.source]
        tokens = deepcopy(node.tokens)
        for token in walk_tokens(tokens):
            if token.type not in {'image', 'link_open'}:
                continue
            attr = 'src' if token.type == 'image' else 'href'
            url = token.attrGet(attr) or ''
            parsed = urlsplit(url)
            if parsed.scheme in {'http', 'https', 'mailto', 'tel'} or parsed.netloc:
                if token.type == 'image':
                    course.warnings.append(f'{node.source.name}:{node.line}: imagen remota no descargada: {url}')
                    token.type = 'text'
                    token.tag = ''
                    token.content = '[Imagen remota: ' + token.content + ' — ' + url + ']'
                    token.children = None
                continue
            if parsed.scheme:
                raise ConversionError(f'Protocolo no permitido: {url}')
            if not parsed.path:
                continue
            target_doc = (node.source.parent / unquote(parsed.path)).resolve()
            if target_doc in docs:
                # Mark for rewriting after IDs produced by footnotes are known.
                token.attrSet('data-document', str(list(docs).index(target_doc)))
                token.attrSet(attr, '#' + parsed.fragment)
                continue
            copied = assets.copy(url, node.source, node.line, 'image' if token.type == 'image' else 'attachment')
            if copied is None:
                if token.type == 'image':
                    token.type, token.tag = 'text', ''
                    token.content = '[Imagen ausente: ' + token.content + ']'
                    token.children = None
                else:
                    token.attrs.pop('href', None)
                    token.attrSet('class', 'missing-asset')
            else:
                token.attrSet(attr, copied + ('#' + parsed.fragment if parsed.fragment else ''))
                if token.type == 'link_open':
                    token.attrSet('download', '')
        body = md.renderer.render(tokens, md.options, doc.env)
        fragment = html.fragment_fromstring('<h1 id="' + escape(node.anchor, quote=True) + '">' + escape(node.title) + '</h1>' + body, create_parent='div')
        # Figure semantics for paragraphs consisting solely of an image.
        for p in fragment.xpath('.//p[count(*)=1 and img]'):
            if (p.text or '').strip() or (p[0].tail or '').strip():
                continue
            p.tag = 'figure'
            caption = etree.SubElement(p, 'figcaption')
            caption.text = p[0].get('alt', '')
        fragments[node.href] = fragment
        for el in fragment.xpath('.//*[@id]'):
            key = (node.source, el.get('id'))
            if key in anchors:
                raise ConversionError(f'Identificador HTML duplicado: {key[1]}')
            anchors[key] = node.href
    for doc in course.documents:
        if (doc.source, doc.title_anchor) not in anchors:
            first = fragments[first_pages[doc.source]]
            marker = etree.Element('span', id=doc.title_anchor)
            first.insert(0, marker)
            anchors[(doc.source, doc.title_anchor)] = first_pages[doc.source]
    for node in course.walk():
        fragment = fragments[node.href]
        for a in fragment.xpath('.//a[@href]'):
            href = a.get('href')
            if not href.startswith('#'):
                continue
            document = node.source
            if a.get('data-document') is not None:
                document = list(docs)[int(a.attrib.pop('data-document'))]
            anchor = unquote(href[1:])
            target = anchors.get((document, anchor)) if anchor else first_pages[document]
            if not target:
                raise ConversionError(f'{node.source.name}:{node.line}: enlace interno sin destino: {href}')
            if target != node.href:
                a.set('href', Path(target).name + '?preview=1' + ('#' + quote(anchor) if anchor else ''))
                a.set('target', '_blank')
                a.set('rel', 'noopener noreferrer')
                a.set('title', 'Abrir referencia; para registrar progreso, seleccione el apartado en Moodle')
        content = (fragment.text or '') + ''.join(html.tostring(child, encoding='unicode') for child in fragment)
        output = page.render(course=course, node=node, content=Markup(content), template=template)
        target = build / node.href
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(output, encoding='utf-8')
