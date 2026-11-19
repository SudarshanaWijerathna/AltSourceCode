"""Loads tour, destination and policy Markdown (YAML front matter) from the dataset."""

from dataclasses import dataclass
from pathlib import Path

import frontmatter


@dataclass(frozen=True)
class ContentDoc:
    id: str
    type: str
    title: str
    status: str
    path: Path
    meta: dict
    body: str


def load_content(content_dir: Path) -> list[ContentDoc]:
    docs: list[ContentDoc] = []
    for path in sorted(content_dir.rglob("*.md")):
        post = frontmatter.load(path)
        meta = dict(post.metadata)
        docs.append(
            ContentDoc(
                id=str(meta.get("id", path.stem)),
                type=str(meta.get("type", path.parent.name)),
                title=str(meta.get("title", path.stem)),
                status=str(meta.get("status", "draft")),
                path=path,
                meta=meta,
                body=post.content,
            )
        )
    return docs
