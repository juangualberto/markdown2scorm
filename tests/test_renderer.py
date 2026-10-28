from pathlib import Path
from zipfile import ZipFile
from lxml import html
import pytest
from markdown2scorm.exporter import export
from markdown2scorm.models import ConversionError


def get_page(result, index=0):
    return html.fromstring((result.build / list(result.course.walk())[index].href).read_bytes())


def test_markdown_features(convert_md):
    r = convert_md('# T\n\n**fuerte** *suave* ~~tachado~~ & < > ñ\n\n- uno\n  - anidado\n\n1. primero\n2. segundo\n\n> cita\n\n---\n\n| A | B |\n|---|---|\n| 1 | 2 |\n\n`inline`')
    doc = get_page(r)
    for tag in ['strong', 'em', 's', 'ul', 'ol', 'blockquote', 'hr', 'table', 'code']:
        assert doc.xpath('//' + tag)
    assert doc.xpath('//ul/li/ul/li')
    assert '& < > ñ' in doc.text_content()


@pytest.mark.parametrize('language', ['python', 'unknown-language', ''])
def test_code_exact(convert_md, language):
    code = '\n\tif x < 3:\n    print("á & <")\n\n'
    r = convert_md('# T\n\n```' + language + '\n' + code + '```')
    assert get_page(r).xpath('//pre/code')[0].text_content() == code


@pytest.mark.parametrize('formula', [r'$x^2$', '$$x^2$$', r'\(x+1\)', r'\[x+1\]', '$$\n\\frac{1}{2}\n$$'])
def test_math_offline(convert_md, formula):
    r = convert_md('# T\n\n' + formula)
    d = get_page(r)
    assert d.xpath('//math')
    assert not d.xpath('//script[contains(@src,"http")]')
    assert not r.course.warnings


def test_unknown_math_preserved(convert_md):
    r = convert_md('# T\n\n$\\nonexistentcommand{x}$')
    assert r.course.warnings
    assert '\\nonexistentcommand' in get_page(r).text_content()


def test_safe_html_and_urls(convert_md):
    r = convert_md('# <script>alert(1)</script>\n\n<script>bad()</script>\n\n[x](javascript:alert(1))\n\n<img src=x onerror=bad()>')
    d = get_page(r)
    assert len(d.xpath('//script')) == 1
    assert not d.xpath('//*[@onerror]')
    assert not d.xpath('//a[starts-with(@href,"javascript:")]')


def test_cross_page_and_title_links(convert_md):
    r = convert_md('# Título\n\n[inicio](#título) [dos](#dos)\n\n## Dos\n\n[volver](#título) [aquí](#dos)')
    d = get_page(r)
    link = d.xpath('//a[contains(@href,"preview=1")]')[0]
    assert link.get('target') == '_blank'
    assert link.get('rel') == 'noopener noreferrer'
    assert get_page(r, 1).xpath('//a[@href="#dos"]')


def test_global_reference_and_footnotes(convert_md):
    r = convert_md('# T\n\n[link][ref] primera[^n].\n\n## B\n\nSegunda[^n].\n\n[ref]: https://example.com\n[^n]: Nota global.')
    assert r.validation.valid
    assert get_page(r).xpath('//a[@href="https://example.com"]')
    assert 'Nota global.' in get_page(r, 1).text_content()


def test_broken_anchor_fails(convert_md):
    with pytest.raises(ConversionError, match='sin destino'):
        convert_md('# T\n\n[enlace](#ausente)')


def test_multiple_documents(make_md, tmp_path):
    a = make_md('# Uno\n\n[ir](b.md#sección)')
    b = make_md('# Dos\n\n## Sección\n\nTexto', 'b.md')
    r = export([a, b], tmp_path / 'multi.zip', keep_build=True)
    assert len(r.course.nodes) == 2
    assert r.validation.valid
    assert r.course.nodes[1].children[0].title == 'Sección'


def test_remote_image_not_required(convert_md):
    r = convert_md('# T\n\n![Alt](https://example.com/image.png)')
    assert not get_page(r).xpath('//img')
    assert r.course.warnings
    assert r.validation.valid


def test_templates_do_not_change_manifest(make_md, tmp_path):
    md = make_md('# T\n\n## P\n\nText\n\n### C\n\nChild')
    a = export([md], tmp_path / 'a.zip')
    b = export([md], tmp_path / 'b.zip', template='fpd-medu')
    from lxml import etree
    from markdown2scorm.manifest import NS
    with ZipFile(a.output) as az, ZipFile(b.output) as bz:
        aa = etree.fromstring(az.read('imsmanifest.xml')).find('cp:organizations', NS)
        bb = etree.fromstring(bz.read('imsmanifest.xml')).find('cp:organizations', NS)
        assert etree.tostring(aa) == etree.tostring(bb)
