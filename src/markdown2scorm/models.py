"""Tree shared by the manifest and renderer; independent of either output."""
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterator


class ConversionError(ValueError):
    """An actionable authoring or packaging error."""


@dataclass
class Node:
    identifier: str
    title: str
    level: int
    anchor: str
    source: Path
    line: int = 1
    tokens: list[Any] = field(default_factory=list, repr=False)
    children: list['Node'] = field(default_factory=list)

    @property
    def href(self) -> str:
        return f"pages/{self.identifier}.html"

    def walk(self) -> Iterator['Node']:
        yield self
        for child in self.children:
            yield from child.walk()


@dataclass
class Document:
    source: Path
    title: str
    title_anchor: str
    nodes: list[Node]
    env: dict = field(default_factory=dict, repr=False)
    headings: list[dict] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    features: dict[str, int] = field(default_factory=dict)

    def walk(self) -> Iterator[Node]:
        for node in self.nodes:
            yield from node.walk()


@dataclass
class Course:
    title: str
    documents: list[Document]
    nodes: list[Node]
    warnings: list[str] = field(default_factory=list)

    def walk(self) -> Iterator[Node]:
        for node in self.nodes:
            yield from node.walk()
