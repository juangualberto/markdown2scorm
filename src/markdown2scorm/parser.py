"""Parse once: syntax tokens retain reference definitions and global footnotes."""
from collections import Counter
from hashlib import sha256
from pathlib import Path
import re
import unicodedata

from markdown_it import MarkdownIt
from mdit_py_plugins.dollarmath import dollarmath_plugin
from mdit_py_plugins.texmath import texmath_plugin
from mdit_py_plugins.footnote import footnote_plugin

from .models import ConversionError, Course, Document, Node


def slug(text: str) -> str:
    text = unicodedata.normalize('NFC', text).lower().strip()
    return re.sub(r'\s+', '-', re.sub(r'[^\w\s-]', '', text)) or 'seccion'


def latex_source(state, start, end, silent):
    """Preserve standalone TeX layout commands literally, never execute them."""
    line = state.src[state.bMarks[start] + state.tShift[start]:state.eMarks[start]]
    if not re.match(r'^\\(?:newpage|thispagestyle|vspace|begin\{center\}|end\{center\})', line):
        return False
    if silent:
        return True
    token = state.push('latex_source', 'pre', 0)
    token.content = line
    token.map = [start, start + 1]
    state.line = start + 1
    return True


def make_parser() -> MarkdownIt:
    md = MarkdownIt('commonmark', {'html': False, 'linkify': True})
    md.enable(['table', 'strikethrough', 'linkify'])
    md.use(footnote_plugin).use(dollarmath_plugin, double_inline=True)
    md.use(texmath_plugin, delimiters='brackets')
    md.block.ruler.before('paragraph', 'latex_source', latex_source)
    return md


def inline_text(tokens) -> str:
    result = ''
    for t in tokens:
        if t.type in ('text', 'code_inline', 'math_inline', 'math_inline_double'):
            result += t.content
        elif t.type == 'image':
            result += inline_text(t.children or [])
        elif t.type in ('softbreak', 'hardbreak'):
            result += ' '
    return result


def walk_tokens(tokens):
    for token in tokens:
        yield token
        yield from walk_tokens(token.children or [])


def parse_document(path: Path, prefix: str = '') -> Document:
    path = Path(path).resolve()
    source = path.read_text(encoding='utf-8-sig')
    env: dict = {}
    md = make_parser()
    tokens = md.parse(source, env)
    warnings = []
    headings = []
    counts: Counter = Counter()
    heading_at = {}
    for i, token in enumerate(tokens):
        if token.type != 'heading_open' or token.level != 0:
            continue
        inline = tokens[i + 1]
        # Pandoc's .unnumbered annotation is metadata, not heading text.
        if inline.content.endswith(' {.unnumbered}'):
            inline.content = inline.content.removesuffix(' {.unnumbered}')
            inline.children = md.parseInline(inline.content)[0].children
            token.attrSet('class', 'unnumbered')
        title = inline_text(inline.children or [])
        base = slug(title)
        count = counts[base]
        counts[base] += 1
        anchor = base if not count else f'{base}-{count}'
        # A naturally suffixed heading can coincide with a duplicate's slug.
        while anchor in {h['anchor'] for h in headings}:
            counts[base] += 1
            anchor = f'{base}-{counts[base]}'
        token.attrSet('id', anchor)
        record = dict(level=int(token.tag[1]), title=title, anchor=anchor,
                      line=(token.map or [0])[0] + 1)
        headings.append(record)
        heading_at[i] = record
    h1 = [h for h in headings if h['level'] == 1]
    if len(h1) > 1:
        raise ConversionError(f'{path.name}: varios H1 en líneas ' + ', '.join(str(h['line']) for h in h1))
    if h1 and headings[0] != h1[0]:
        raise ConversionError(f'{path.name}: el H1 debe preceder a los demás encabezados')
    title = h1[0]['title'] if h1 else path.stem
    title_anchor = h1[0]['anchor'] if h1 else slug(title)
    if not h1:
        warnings.append(f'{path.name}: falta H1; se utiliza el nombre del archivo')
    roots: list[Node] = []
    stack: list[Node] = []
    intro = Node(prefix + 'introduccion', 'Introducción', 2, 'introduccion', path)
    # Do not compete with a real heading named Introducción.
    while intro.anchor in {h['anchor'] for h in headings}:
        intro.anchor += '-inicio'
    current = intro
    i = 0
    while i < len(tokens):
        record = heading_at.get(i)
        if record:
            level = record['level']
            if level == 1:
                i += 3
                continue
            while stack and stack[-1].level >= level:
                stack.pop()
            expected = stack[-1].level + 1 if stack else 2
            if level > expected:
                warnings.append(f"{path.name}:{record['line']}: salto H{expected-1} → H{level}; jerarquía normalizada")
            key = sha256(record['anchor'].encode()).hexdigest()[:16]
            current = Node(prefix + 'n-' + key, record['title'], level,
                           record['anchor'], path, record['line'])
            (stack[-1].children if stack else roots).append(current)
            stack.append(current)
            i += 3
            continue
        current.tokens.append(tokens[i])
        i += 1
    if intro.tokens or not roots:
        roots.insert(0, intro)
    if any(t.type == 'latex_source' for t in tokens):
        warnings.append(f'{path.name}: órdenes LaTeX de maquetación conservadas como texto literal; no se ejecutan')
    features = dict(Counter(t.type for t in walk_tokens(tokens)))
    return Document(path, title, title_anchor, roots, env, headings, warnings, features)


def parse_course(inputs: list[Path], title: str | None = None) -> Course:
    paths = [Path(p).resolve() for p in inputs]
    if len(set(paths)) != len(paths):
        raise ConversionError('Un mismo Markdown aparece más de una vez')
    documents = [parse_document(p, f'd{i + 1}-' if len(paths) > 1 else '') for i, p in enumerate(paths)]
    roots = documents[0].nodes if len(documents) == 1 else []
    if len(documents) > 1:
        for i, doc in enumerate(documents):
            roots.append(Node(f'doc-{i+1}', doc.title, 1, doc.title_anchor,
                              doc.source, children=doc.nodes))
    return Course(title or (documents[0].title if len(documents) == 1 else 'Colección de documentos'),
                  documents, roots, [w for d in documents for w in d.warnings])
