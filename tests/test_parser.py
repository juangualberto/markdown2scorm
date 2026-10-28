from collections import Counter
import pytest
from markdown2scorm.models import ConversionError
from markdown2scorm.parser import parse_document


def test_intro_parent_child_content(make_md):
    d = parse_document(make_md('# Título\n\nIntro.\n\n## Padre\n\nPropio.\n\n### Hijo\n\nDel hijo.\n\n## Otro\n\nFinal.'))
    assert d.title == 'Título'
    assert [n.title for n in d.nodes] == ['Introducción', 'Padre', 'Otro']
    assert d.nodes[1].children[0].title == 'Hijo'
    assert [t.content for t in d.nodes[1].tokens if t.type == 'inline'] == ['Propio.']
    assert [t.content for t in d.nodes[1].children[0].tokens if t.type == 'inline'] == ['Del hijo.']


@pytest.mark.parametrize('text, count', [('# T\n\nTexto', 1), ('# T', 1), ('Sin encabezados', 1), ('# T\n\n## A\n\n## B', 2)])
def test_edge_documents(make_md, text, count):
    d = parse_document(make_md(text))
    assert len(list(d.walk())) == count


def test_code_headings_ignored(make_md):
    d = parse_document(make_md('# T\n\n```md\n# X\n## falso\n```\n\n    ## tampoco\n\n## Real'))
    assert [h['title'] for h in d.headings] == ['T', 'Real']
    assert any(t.type == 'fence' for t in d.nodes[0].tokens)


def test_duplicate_stable_identifiers(make_md):
    p = make_md('# T\n\n## Árbol\n\nA\n\n## Árbol\n\nB\n\n## Árbol-1\n\nC')
    a, b = parse_document(p), parse_document(p)
    assert [n.identifier for n in a.walk()] == [n.identifier for n in b.walk()]
    assert len({n.anchor for n in a.walk()}) == 3


def test_multiple_h1_diagnostic(make_md):
    with pytest.raises(ConversionError, match='varios H1.*1, 3'):
        parse_document(make_md('# Uno\n\n# Dos'))


def test_setext_and_metadata(make_md):
    d = parse_document(make_md('Título\n======\n\n## Referencias {.unnumbered}\n\nContenido'))
    assert d.title == 'Título'
    assert d.nodes[0].title == 'Referencias'


def test_preamble_preserved(make_md):
    d = parse_document(make_md('\\newpage\n\nPortada\n\n# T\n\nCuerpo\n\n## A'))
    assert [t.content for t in d.nodes[0].tokens if t.content] == ['\\newpage', 'Portada', 'Cuerpo']
    assert d.warnings
