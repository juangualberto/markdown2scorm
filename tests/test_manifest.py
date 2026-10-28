from pathlib import Path
import stat
from zipfile import ZipFile, ZipInfo
from lxml import etree
import pytest
from markdown2scorm.manifest import NS, CP, ADL
from markdown2scorm.validator import validate_package


def test_manifest_hierarchy(convert_md):
    r = convert_md('# T\n\nIntro\n\n## Padre\n\nPropio\n\n### Hijo\n\nHijo')
    with ZipFile(r.output) as z:
        root = etree.fromstring(z.read('imsmanifest.xml'))
        items = root.findall('.//cp:item', NS)
        assert len(items) == 3
        parent = items[1]
        assert parent.find('cp:item', NS) is items[2]
        assert all(i.get('identifierref') for i in items)
        res = root.findall('cp:resources/cp:resource', NS)
        assert sum(e.get('{' + ADL + '}scormtype') == 'sco' for e in res) == 3
        assert root.nsmap[None] == CP
        assert not any(n.startswith('/') for n in z.namelist())


def mutate_package(result, tmp_path, mutate):
    with ZipFile(result.output) as z:
        files = {n: z.read(n) for n in z.namelist()}
    mutate(files)
    output = tmp_path / 'broken.zip'
    with ZipFile(output, 'w') as z:
        for n, data in files.items():
            z.writestr(n, data)
    return output


@pytest.mark.parametrize('kind', ['manifest', 'xml', 'namespace', 'version', 'ref', 'id', 'runtime', 'image', 'traversal', 'absolute', 'undeclared', 'anchor', 'css', 'empty_html'])
def test_validator_rejects_broken_packages(convert_md, tmp_path, kind):
    r = convert_md('# T\n\nTexto')
    def mutate(files):
        page = 'pages/introduccion.html'
        if kind == 'manifest': del files['imsmanifest.xml']
        elif kind == 'xml': files['imsmanifest.xml'] = b'<broken'
        elif kind == 'namespace': files['imsmanifest.xml'] = files['imsmanifest.xml'].replace(CP.encode(), b'urn:wrong')
        elif kind == 'version': files['imsmanifest.xml'] = files['imsmanifest.xml'].replace(b'>1.2<', b'>2004<')
        elif kind == 'ref': files['imsmanifest.xml'] = files['imsmanifest.xml'].replace(b'identifierref="res-introduccion"', b'identifierref="bad"')
        elif kind == 'id': files['imsmanifest.xml'] = files['imsmanifest.xml'].replace(b'identifier="res-shared"', b'identifier="res-introduccion"')
        elif kind == 'runtime': files['runtime/scorm12.js'] = b'alert(1)'
        elif kind == 'image': files[page] = files[page].replace(b'</main>', b'<img src="../missing.png"></main>')
        elif kind == 'traversal': files['../outside.txt'] = b'danger'
        elif kind == 'absolute': files[page] = files[page].replace(b'</main>', b'<a href="/home/developer/a">x</a></main>')
        elif kind == 'undeclared': files['surprise.txt'] = b'unused'
        elif kind == 'anchor': files[page] = files[page].replace(b'</main>', b'<a href="#missing">x</a></main>')
        elif kind == 'css': files['theme/style.css'] += b'body{background:url(missing.png)}'
        elif kind == 'empty_html': files[page] = b''
    v = validate_package(mutate_package(r, tmp_path, mutate))
    assert not v.valid, kind


def test_invalid_zip(tmp_path):
    p = tmp_path / 'bad.zip'
    p.write_bytes(b'not a zip')
    assert not validate_package(p).valid


def test_expected_pages(convert_md):
    r = convert_md('# T')
    assert not validate_package(r.output, ['pages/missing.html']).valid


def test_symlink_archive(tmp_path):
    p = tmp_path / 'link.zip'
    with ZipFile(p, 'w') as z:
        info = ZipInfo('link')
        info.create_system = 3
        info.external_attr = (stat.S_IFLNK | 0o777) << 16
        z.writestr(info, '/etc/passwd')
    assert not validate_package(p).valid


def test_reference_xsd(real_export):
    from scripts.validate_reference import validate_with_reference
    from .conftest import ROOT
    result = validate_with_reference(real_export.output, ROOT / 'SR-tarea08-pt.zip')
    assert result.valid, result.errors
    assert any('XSD' in c for c in result.checks)
