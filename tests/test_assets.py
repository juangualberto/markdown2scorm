from pathlib import Path
from zipfile import ZipFile
import pytest
from markdown2scorm.assets import AssetManager
from markdown2scorm.exporter import export
from markdown2scorm.models import ConversionError


@pytest.mark.parametrize('suffix', ['.png', '.jpg', '.jpeg', '.gif', '.webp', '.pdf', '.zip', '.pkt'])
def test_formats_preserved(tmp_path, make_md, suffix):
    p = tmp_path / ('á con espacio' + suffix)
    p.write_bytes(b'original bytes')
    prefix = '!' if suffix in {'.png', '.jpg', '.jpeg', '.gif', '.webp'} else ''
    doc = make_md(f'# T\n\n{prefix}[alternativo](<{p.name}>)')
    result = export([doc], tmp_path / 'out.zip')
    with ZipFile(result.output) as z:
        assert z.read(result.assets[0].destination) == p.read_bytes()
        assert result.assets[0].destination.endswith(suffix)


def test_missing_is_error(convert_md):
    with pytest.raises(ConversionError, match='no se encuentra.*ausente.png'):
        convert_md('# T\n\n![alt](ausente.png)')


def test_missing_explicit(convert_md):
    r = convert_md('# T\n\n![alt](ausente.png)\n\n[PDF](no.pdf)', allow_missing_assets=True)
    assert r.validation.valid
    assert len(r.course.warnings) == 2
    assert 'Imagen ausente: alt' in (r.build / 'pages/introduccion.html').read_text()


def test_additional_and_ambiguous(tmp_path, make_md):
    doc = make_md('# T\n\n![alt](foo.png)', 'manuscrito/a.md')
    dirs = [tmp_path / x for x in ['a', 'b']]
    for i, d in enumerate(dirs):
        d.mkdir()
        (d / 'foo.png').write_bytes(bytes([i]))
    r = export([doc], tmp_path / 'out.zip', assets_dirs=[dirs[0]])
    assert len(r.assets) == 1
    with pytest.raises(ConversionError, match='ambiguo'):
        export([doc], tmp_path / 'out.zip', assets_dirs=dirs)


def test_relative_precedence_and_collisions(tmp_path, make_md):
    for folder, value in [('a', b'one'), ('b', b'two'), ('c', b'one')]:
        (tmp_path / folder).mkdir()
        (tmp_path / folder / 'same.png').write_bytes(value)
    doc = make_md('# T\n\n![a](a/same.png) ![b](b/same.png) ![c](c/same.png)')
    r = export([doc], tmp_path / 'out.zip', assets_dirs=[tmp_path / 'b'])
    assert len({a.destination for a in r.assets}) == 2


def test_image_inside_link(tmp_path, make_md):
    (tmp_path / 'x.png').write_bytes(b'x')
    doc = make_md('# T\n\n[![alt](x.png)](x.png)')
    r = export([doc], tmp_path / 'out.zip')
    assert {a.kind for a in r.assets} == {'image', 'attachment'}
    assert len({a.destination for a in r.assets}) == 1


def test_path_escape_and_symlink(tmp_path, make_md):
    secret = tmp_path / 'secret.png'
    secret.write_bytes(b'secret')
    doc = make_md('# T\n\n![alt](../secret.png)', 'docs/a.md')
    with pytest.raises(ConversionError, match='fuera'):
        export([doc], tmp_path / 'out.zip', allow_missing_assets=True)
    (doc.parent / 'link.png').symlink_to(secret)
    doc.write_text('# T\n\n![alt](link.png)')
    with pytest.raises(ConversionError, match='fuera'):
        export([doc], tmp_path / 'out.zip')


@pytest.mark.parametrize('reference', ['/etc/passwd', 'file:///etc/passwd', '%2Fetc%2Fpasswd'])
def test_absolute_rejected(tmp_path, make_md, reference):
    doc = make_md('# T')
    manager = AssetManager(tmp_path / 'build', [doc])
    with pytest.raises(ConversionError):
        manager.resolve(reference, doc, 1)


@pytest.mark.parametrize('content', ['<script>alert(1)</script>', '<image href="https://example.com/a.png"/>', '<rect onclick="alert(1)"/>', '<foreignObject/>'])
def test_active_svg_rejected(tmp_path, make_md, content):
    (tmp_path / 'x.svg').write_text('<svg xmlns="http://www.w3.org/2000/svg">' + content + '</svg>')
    doc = make_md('# T\n\n![alt](x.svg)')
    with pytest.raises(ConversionError, match='SVG'):
        export([doc], tmp_path / 'out.zip')


def test_passive_svg_preserved(tmp_path, make_md):
    data = '<svg xmlns="http://www.w3.org/2000/svg"><rect width="10" height="10"/></svg>'
    (tmp_path / 'x.svg').write_text(data)
    doc = make_md('# T\n\n![alt](x.svg)')
    r = export([doc], tmp_path / 'out.zip')
    with ZipFile(r.output) as z:
        assert z.read(r.assets[0].destination).decode() == data
