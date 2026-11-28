"""MkDocs hooks: bring files that live outside docs/ into the site.

- slides/ is copied as static files, so the standalone decks keep working at /slides/.
- Each deck also becomes a page (decks/<deck>.md), generated from the deck's HTML at build time, one section per
  slide with the speaker notes folded under it. The decks stay the source of truth, and their text is searchable.
- README.md becomes the "Labs and setup" page (labs.md). MkDocs would treat a file named README.md as an index
  page and drop it next to docs/index.md, so the content is generated under another name, with its
  repo-relative links fixed for the site.
- The study guide is gitignored (aws_genai*). It is added only when INCLUDE_STUDY_GUIDE=1, so a build you deploy
  never publishes it by accident.
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

from mkdocs.structure.files import File

sys.path.insert(0, str(Path(__file__).resolve().parent))
from deck_to_markdown import deck_to_markdown  # noqa: E402

STUDY_GUIDE = "aws_genai_study_guide.md"
DECKS_NAV_TITLE = "Slide decks"


def _root(config) -> Path:
    return Path(config.config_file_path).parent


def _include_study_guide(config) -> bool:
    return os.environ.get("INCLUDE_STUDY_GUIDE") == "1" and (_root(config) / STUDY_GUIDE).is_file()


def _deck_dirs(root: Path) -> list[str]:
    return sorted(p.parent.name for p in (root / "slides").glob("*/index.html"))


def _deck_catalog(root: Path) -> dict[str, dict[str, str]]:
    """Title, tasks and one-line summary for each deck, read from the slides/ picker page."""
    index = (root / "slides" / "index.html").read_text(encoding="utf-8")
    pattern = re.compile(
        r'<li><a href="([^/"]+)/index\.html"><span class="n">([^<]*)</span>'
        r'<div class="t">([^<]*)</div><div class="d">([^<]*)</div>'
    )
    catalog = {}
    for deck, label, title, summary in pattern.findall(index):
        tasks = re.sub(r"^Tasks?\s*", "", label.split("/", 1)[1].strip()) if "/" in label else "all"
        catalog[deck] = {"title": title.strip(), "tasks": tasks, "summary": summary.strip()}
    return catalog


def _deck_title(deck: str, catalog: dict) -> str:
    info = catalog.get(deck, {})
    return f"{deck[:2]} · {info.get('title', deck[3:].replace('-', ' ').capitalize())}"


def on_config(config):
    root = _root(config)
    catalog = _deck_catalog(root)
    deck_pages = [{_deck_title(d, catalog): f"decks/{d}.md"} for d in _deck_dirs(root)]
    for position, item in enumerate(config.nav):
        if isinstance(item, dict) and DECKS_NAV_TITLE in item:
            # A bare first entry becomes the section's own page (navigation.indexes).
            config.nav[position] = {DECKS_NAV_TITLE: [item[DECKS_NAV_TITLE]] + deck_pages}
    if _include_study_guide(config):
        config.nav.append({"Study guide": STUDY_GUIDE})
    return config


def on_files(files, config):
    root = _root(config)
    for path in sorted((root / "slides").rglob("*")):
        if path.is_file():
            files.append(File(path.relative_to(root).as_posix(), str(root), config.site_dir, config.use_directory_urls))

    catalog = _deck_catalog(root)
    for deck in _deck_dirs(root):
        html = (root / "slides" / deck / "index.html").read_text(encoding="utf-8")
        info = catalog.get(deck, {})
        summary = info.get("summary", "")
        if info.get("tasks") and info["tasks"] != "all":
            summary = f"{summary} Tasks {info['tasks']}.".strip()
        page = deck_to_markdown(html, _deck_title(deck, catalog), f"../slides/{deck}/index.html", summary)
        files.append(File.generated(config, f"decks/{deck}.md", content=page))

    # The README links to docs/ relative to the repo root; inside the site, docs/ is the root.
    readme = (root / "README.md").read_text(encoding="utf-8").replace("](docs/", "](")
    files.append(File.generated(config, "labs.md", content=readme))

    if _include_study_guide(config):
        files.append(File(STUDY_GUIDE, str(root), config.site_dir, config.use_directory_urls))
    return files
