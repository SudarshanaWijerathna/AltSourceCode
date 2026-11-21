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


def load_all_content(settings=None) -> list[ContentDoc]:
    """The dataset's content (read in place) plus pages an Approver has published.

    Published AI-written pages live in settings.mira_published_dir, never in the dataset folder.
    """
    from mira.config import get_settings

    s = settings or get_settings()
    docs = load_content(s.content_dir)
    if s.mira_published_dir.exists():
        docs += load_content(s.mira_published_dir)
    return docs


def source_path(path: Path) -> str:
    """Path shown as a page's source: repo-relative, or 'published/<file>' for pages outside the repo."""
    from mira.config import REPO_ROOT

    try:
        return path.resolve().relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return f"published/{path.name}"
