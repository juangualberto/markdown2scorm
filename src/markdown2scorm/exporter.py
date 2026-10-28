"""Transactional export API, also usable from a future graphical interface."""
from dataclasses import dataclass
from pathlib import Path
import shutil
import tempfile
from zipfile import ZipFile, ZIP_DEFLATED, ZipInfo

from pygments.formatters import HtmlFormatter
from .assets import Asset, AssetManager
from .manifest import generate_manifest
from .models import ConversionError, Course
from .parser import parse_course
from .renderer import render_course, TEMPLATES
from .report import write_report
from .validator import validate_package, ValidationResult


@dataclass
class ExportResult:
    output: Path
    course: Course
    assets: list[Asset]
    validation: ValidationResult
    template: str
    build: Path | None
    report: Path | None = None


def export(inputs, output, *, template='default', assets_dirs=(), title=None,
           allow_missing_assets=False, keep_build=False, schema=None) -> ExportResult:
    inputs = [Path(p) for p in inputs]
    if not inputs:
        raise ConversionError('Debe proporcionar al menos un Markdown')
    output = Path(output).resolve()
    if output.suffix.lower() != '.zip':
        raise ConversionError('--output debe terminar en .zip')
    course = parse_course(inputs, title)
    output.parent.mkdir(parents=True, exist_ok=True)
    build = Path(tempfile.mkdtemp(prefix=output.stem + '.build-', dir=output.parent))
    temp_zip = None
    success = False
    try:
        assets = AssetManager(build, inputs, assets_dirs, allow_missing_assets)
        render_course(course, assets, build, template)
        course.warnings.extend(assets.warnings)
        theme = build / 'theme'
        theme.mkdir()
        shutil.copyfile(TEMPLATES / 'default/base.css', theme / 'base.css')
        shutil.copyfile(TEMPLATES / template / 'style.css', theme / 'style.css')
        notice = TEMPLATES / template / 'NOTICE.txt'
        if notice.exists():
            shutil.copyfile(notice, theme / 'NOTICE.txt')
        (theme / 'pygments.css').write_text(HtmlFormatter().get_style_defs('.highlight'), encoding='utf-8')
        (build / 'runtime').mkdir()
        shutil.copyfile(Path(__file__).parent / 'runtime/scorm12.js', build / 'runtime/scorm12.js')
        generate_manifest(course, build)
        with tempfile.NamedTemporaryFile(prefix='.scorm-', suffix='.zip', dir=output.parent, delete=False) as tmp:
            temp_zip = Path(tmp.name)
        with ZipFile(temp_zip, 'w', ZIP_DEFLATED) as archive:
            for path in sorted(build.rglob('*')):
                if path.is_file():
                    info = ZipInfo(path.relative_to(build).as_posix(), date_time=(2020, 1, 1, 0, 0, 0))
                    info.compress_type = ZIP_DEFLATED
                    info.external_attr = 0o100644 << 16
                    archive.writestr(info, path.read_bytes())
        validation = validate_package(temp_zip, [n.href for n in course.walk()], Path(schema) if schema else None)
        if not validation.valid:
            raise ConversionError('Paquete inválido:\n' + '\n'.join(validation.errors))
        temp_zip.replace(output)
        success = True
        result = ExportResult(output, course, assets.records, validation, template, build if keep_build else None)
        result.report = output.with_name(output.stem + '-report.md')
        write_report(result, result.report)
        return result
    finally:
        if temp_zip is not None:
            temp_zip.unlink(missing_ok=True)
        if not keep_build or not success:
            shutil.rmtree(build)
