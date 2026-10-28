from markdown2scorm.parser import parse_document


def test_all_heading_levels(make_md):
    d = parse_document(make_md('# T\n' + '\n'.join('#' * i + f' Nivel{i}\n\nTexto{i}\n' for i in range(2, 7))))
    node = d.nodes[0]
    for level in range(2, 7):
        assert node.level == level
        assert f'Texto{level}' in [t.content for t in node.tokens]
        if level < 6:
            assert len(node.children) == 1
            node = node.children[0]


def test_skipped_levels_normalized(make_md):
    d = parse_document(make_md('# T\n\n## A\n\n#### B\n\n### C\n\n## D'))
    assert [n.title for n in d.nodes] == ['A', 'D']
    assert [n.title for n in d.nodes[0].children] == ['B', 'C']
    assert len(d.warnings) == 1


def test_top_level_jump(make_md):
    d = parse_document(make_md('# T\n\n#### A\n\n###### B'))
    assert d.nodes[0].title == 'A'
    assert d.nodes[0].children[0].title == 'B'
    assert len(d.warnings) == 2
