"""SCORM 1.2 content packaging, one SCO per node, shared asset dependency."""
from pathlib import Path
from lxml import etree as E

CP = 'http://www.imsproject.org/xsd/imscp_rootv1p1p2'
ADL = 'http://www.adlnet.org/xsd/adlcp_rootv1p2'
XSI = 'http://www.w3.org/2001/XMLSchema-instance'
NS = {'cp': CP, 'adlcp': ADL}


def generate_manifest(course, build: Path):
    def sub(parent, name, text=None, **attrs):
        el = E.SubElement(parent, '{' + CP + '}' + name, **attrs)
        el.text = text
        return el
    root = E.Element('{' + CP + '}manifest', nsmap={None: CP, 'adlcp': ADL, 'xsi': XSI}, identifier='manifest-course')
    metadata = sub(root, 'metadata')
    sub(metadata, 'schema', 'ADL SCORM')
    sub(metadata, 'schemaversion', '1.2')
    orgs = sub(root, 'organizations', default='organization-course')
    org = sub(orgs, 'organization', identifier='organization-course', structure='hierarchical')
    sub(org, 'title', course.title)
    def add_nodes(parent, nodes):
        for node in nodes:
            item = sub(parent, 'item', identifier='item-' + node.identifier,
                       identifierref='res-' + node.identifier, isvisible='true')
            sub(item, 'title', node.title)
            add_nodes(item, node.children)
    add_nodes(org, course.nodes)
    resources = sub(root, 'resources')
    for node in course.walk():
        resource = sub(resources, 'resource', identifier='res-' + node.identifier,
                       type='webcontent', href=node.href)
        resource.set('{' + ADL + '}scormtype', 'sco')
        sub(resource, 'file', href=node.href)
        sub(resource, 'dependency', identifierref='res-shared')
    shared = sub(resources, 'resource', identifier='res-shared', type='webcontent')
    shared.set('{' + ADL + '}scormtype', 'asset')
    pages = {n.href for n in course.walk()}
    for path in sorted(build.rglob('*')):
        relative = path.relative_to(build).as_posix()
        if path.is_file() and relative not in pages and relative != 'imsmanifest.xml':
            sub(shared, 'file', href=relative)
    (build / 'imsmanifest.xml').write_bytes(E.tostring(root, encoding='utf-8', xml_declaration=True, pretty_print=True))
