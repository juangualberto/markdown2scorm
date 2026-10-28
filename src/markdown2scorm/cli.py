"""Spanish command line with actionable diagnostics and failure exit codes."""
import argparse
import logging
from pathlib import Path

from .exporter import export
from .models import ConversionError
from .validator import validate_package


def main(argv=None):
    parser = argparse.ArgumentParser(description='Convierte Markdown en SCORM 1.2 autónomo para Moodle.',
        epilog='Ejemplo: markdown2scorm test/manuscrito/01-Introduccion-al-analisis-forense.md '
               '--assets-dir test/figuras --template fpd-medu --output dist/tema01.zip --validate')
    parser.add_argument('input', nargs='+', type=Path, help='Uno o varios Markdown; con --check, un ZIP')
    parser.add_argument('--output', type=Path, default=Path('salida.zip'), help='ZIP de salida (predeterminado: salida.zip)')
    parser.add_argument('--template', default='default', help='Nombre de plantilla: default o fpd-medu')
    parser.add_argument('--assets-dir', action='append', type=Path, default=[], help='Directorio autorizado de recursos; repetible')
    parser.add_argument('--title', help='Título alternativo de la organización')
    parser.add_argument('--verbose', action='store_true', help='Mostrar diagnóstico detallado')
    parser.add_argument('--validate', action='store_true', help='Mostrar comprobaciones (la integridad se valida siempre)')
    parser.add_argument('--keep-build', action='store_true', help='Conservar HTML intermedios junto al ZIP')
    parser.add_argument('--allow-missing-assets', action='store_true', help='Sustituir recursos ausentes por texto y advertir')
    parser.add_argument('--check', action='store_true', help='Validar un ZIP existente sin convertir Markdown')
    parser.add_argument('--schema', type=Path, help='XSD local SCORM 1.2 para validación adicional')
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO, format='%(levelname)s: %(message)s')
    logging.getLogger('markdown_it').setLevel(logging.WARNING)
    try:
        if args.check:
            if len(args.input) != 1:
                parser.error('--check requiere un único ZIP')
            validation = validate_package(args.input[0], schema=args.schema)
        else:
            result = export(args.input, args.output, template=args.template, assets_dirs=args.assets_dir,
                            title=args.title, allow_missing_assets=args.allow_missing_assets,
                            keep_build=args.keep_build, schema=args.schema)
            logging.info('ZIP generado: %s (%d SCO)', result.output, len(list(result.course.walk())))
            logging.info('Informe: %s', result.report)
            if result.build:
                logging.info('HTML intermedios: %s', result.build)
            for warning in result.course.warnings:
                logging.warning(warning)
            if args.verbose:
                for asset in result.assets:
                    logging.debug('%s → %s', asset.source, asset.destination)
            validation = result.validation
        if args.validate or args.check or args.verbose:
            for check in validation.checks:
                logging.info('CORRECTO: %s', check)
        for warning in validation.warnings:
            logging.warning(warning)
        for error in validation.errors:
            logging.error(error)
        return 0 if validation.valid else 1
    except (ConversionError, OSError, UnicodeError) as exc:
        logging.error('%s', exc)
        return 1
