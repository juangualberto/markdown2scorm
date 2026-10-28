from collections import Counter
from hashlib import sha256
from pathlib import Path
import json
import re
import subprocess
import sys
from zipfile import ZipFile

from lxml import etree, html
from markdown2scorm.manifest import NS
from markdown2scorm.parser import make_parser
from markdown2scorm.exporter import export
from .conftest import ROOT


def test_real_manuscript_structure_and_assets(real_export):
    r = real_export
    doc = r.course.documents[0]
    assert doc.title == 'Introducción al análisis forense digital'
    assert Counter(h['level'] for h in doc.headings) == {1: 1, 2: 6, 3: 54}
    assert len(list(r.course.walk())) == 61
    assert len(r.assets) == 6
    assert r.validation.valid
    with ZipFile(r.output) as z:
        manifest = etree.fromstring(z.read('imsmanifest.xml'))
        titles = manifest.xpath('//cp:item/cp:title/text()', namespaces=NS)
        assert titles == ['Introducción'] + [h['title'] for h in doc.headings if h['level'] > 1]
        for asset in r.assets:
            assert z.read(asset.destination) == asset.source.read_bytes()
        for node in r.course.walk():
            page = html.fromstring(z.read(node.href))
            assert page.xpath('//body[@class="theme-fpd-medu"]')
            assert not page.xpath('//nav | //*[@id="siteNav"]')
            # Every inline content block appears on its own assigned page.
            main_text = page.xpath('//main')[0].text_content()
            for token in node.tokens:
                if token.type == 'inline' and not any(t.type == 'image' for t in token.children or []):
                    parser = make_parser()
                    expected = html.fragment_fromstring(parser.renderer.renderInline(token.children or [], parser.options, {}), create_parent='div').text_content()
                    assert re.sub(r'\s+', ' ', expected).strip() in re.sub(r'\s+', ' ', main_text), (node.title, expected[:100])
        all_pages = [html.fromstring(z.read(n.href)) for n in r.course.walk()]
        assert sum(len(p.xpath('//table')) for p in all_pages) == 1
        assert sum(len(p.xpath('//img')) for p in all_pages) == 6


def test_no_content_lost_or_duplicated(real_export):
    doc = real_export.course.documents[0]
    original_tokens = make_parser().parse(doc.source.read_text(), {})
    # Compare all body token content in document order, excluding the heading triples.
    expected = []
    i = 0
    while i < len(original_tokens):
        t = original_tokens[i]
        if t.type == 'heading_open' and t.level == 0:
            i += 3
            continue
        expected.append((t.type, t.content))
        i += 1
    actual = [(t.type, t.content) for n in doc.walk() for t in n.tokens]
    assert actual == expected


def test_original_materials_unchanged():
    hashes = json.loads((ROOT / 'dist/original-sha256.json').read_text())
    for relative, digest in hashes.items():
        assert sha256((ROOT / relative).read_bytes()).hexdigest() == digest


def test_cli_help_and_failure(tmp_path):
    for cmd in [[sys.executable, '-m', 'markdown2scorm'], [str(Path(sys.executable).parent / 'markdown2scorm')]]:
        p = subprocess.run(cmd + ['--help'], capture_output=True, text=True)
        assert p.returncode == 0 and '--assets-dir' in p.stdout
    p = subprocess.run([sys.executable, '-m', 'markdown2scorm', str(tmp_path / 'absent.md')], capture_output=True, text=True)
    assert p.returncode == 1 and 'Traceback' not in p.stderr


def test_export_is_reproducible(make_md, tmp_path):
    path = make_md('# T\n\n## A\n\nContenido')
    a = export([path], tmp_path / 'a.zip')
    b = export([path], tmp_path / 'b.zip')
    assert a.output.read_bytes() == b.output.read_bytes()


def test_failed_export_preserves_previous_output(make_md, tmp_path):
    import pytest
    from markdown2scorm.models import ConversionError
    path = make_md('# T\n\n![image](missing.png)')
    out = tmp_path / 'old.zip'
    out.write_bytes(b'previous')
    with pytest.raises(ConversionError):
        export([path], out)
    assert out.read_bytes() == b'previous'
