from pathlib import Path
import pytest
from markdown2scorm.exporter import export

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def make_md(tmp_path):
    def make(text, name='documento.md'):
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding='utf-8')
        return path
    return make


@pytest.fixture
def convert_md(make_md, tmp_path):
    def convert(text, **kwargs):
        return export([make_md(text)], tmp_path / 'out.zip', keep_build=True, **kwargs)
    return convert


@pytest.fixture(scope='session')
def real_export(tmp_path_factory):
    return export([ROOT / 'test/manuscrito/01-Introduccion-al-analisis-forense.md'],
                  tmp_path_factory.mktemp('real') / 'real.zip',
                  assets_dirs=[ROOT / 'test/figuras'], template='fpd-medu', keep_build=True)
