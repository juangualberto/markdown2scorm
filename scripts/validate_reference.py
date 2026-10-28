"""Validate using the original schemas without redistributing modified copies."""
from pathlib import Path
from tempfile import TemporaryDirectory
from zipfile import ZipFile
import argparse

from markdown2scorm.validator import validate_package

SCHEMAS = ['imscp_rootv1p1p2.xsd', 'imsmd_rootv1p2p1.xsd',
           'adlcp_rootv1p2.xsd', 'ims_xml.xsd']


def validate_with_reference(package: Path, reference: Path):
    with TemporaryDirectory(prefix='scorm-xsd-') as folder:
        root = Path(folder)
        with ZipFile(reference) as archive:
            for name in SCHEMAS:
                (root / name).write_bytes(archive.read(name))
        schema = root / 'combined.xsd'
        schema.write_text('''<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">
          <xs:import namespace="http://www.imsproject.org/xsd/imscp_rootv1p1p2" schemaLocation="imscp_rootv1p1p2.xsd"/>
          <xs:import namespace="http://www.adlnet.org/xsd/adlcp_rootv1p2" schemaLocation="adlcp_rootv1p2.xsd"/>
        </xs:schema>''')
        return validate_package(package, schema=schema)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('package', type=Path)
    parser.add_argument('--reference', type=Path, default=Path('SR-tarea08-pt.zip'))
    args = parser.parse_args()
    result = validate_with_reference(args.package, args.reference)
    for status, messages in [('OK', result.checks), ('WARNING', result.warnings), ('ERROR', result.errors)]:
        for message in messages:
            print(status + ': ' + message)
    raise SystemExit(0 if result.valid else 1)
