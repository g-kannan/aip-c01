"""Turn a slide deck (slides/NN-name/index.html) into a markdown page, one `##` section per slide.

The decks stay the single source of truth. This runs at site build time so that deck text, including the speaker
notes, is searchable and readable as a normal page. It only understands the markup the decks use (cards, flows,
dense tables, bands, terminal lines, speaker-note asides) and falls back to plain paragraphs for anything else.
"""

from __future__ import annotations

import re
from html.parser import HTMLParser

VOID = {"br", "meta", "link", "img", "hr", "input", "source", "wbr"}
SKIP_TAGS = {"script", "style", "nav", "button", "aside", "head", "svg"}
SKIP_CLASSES = {"footer", "deck-controls", "arrow", "stripe", "edit-hotzone", "edit-toggle"}
CARD_CLASSES = {"card", "step", "node", "stat"}
BAND_CLASSES = {"band", "exam-band", "exam-foot"}
INLINE_TAGS = {"span", "strong", "b", "em", "i", "code", "a", "br", "small", "mark", "u", "sub", "sup"}


class Node:
    def __init__(self, tag: str, attrs: dict[str, str], parent: "Node | None" = None):
        self.tag = tag
        self.attrs = attrs
        self.parent = parent
        self.children: list[Node | str] = []
        self.consumed = False  # heading / eyebrow already used by the slide header

    @property
    def classes(self) -> set[str]:
        return set(self.attrs.get("class", "").split())


class _Builder(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.root = Node("root", {})
        self.current = self.root

    def handle_starttag(self, tag, attrs):
        if tag == "p" and self.current.tag == "p":  # an unclosed paragraph ends at the next one
            self.current = self.current.parent or self.root
        node = Node(tag, {k: v or "" for k, v in attrs}, self.current)
        self.current.children.append(node)
        if tag not in VOID:
            self.current = node

    def handle_startendtag(self, tag, attrs):
        node = Node(tag, {k: v or "" for k, v in attrs}, self.current)
        self.current.children.append(node)

    def handle_endtag(self, tag):
        if tag in VOID:
            return
        node = self.current
        while node is not self.root and node.tag != tag:
            node = node.parent or self.root
        if node is not self.root:
            self.current = node.parent or self.root

    def handle_data(self, data):
        self.current.children.append(data)


def parse(html: str) -> Node:
    builder = _Builder()
    builder.feed(html)
    builder.close()
    return builder.root


def _walk(node: Node):
    for child in node.children:
        if isinstance(child, Node):
            yield child
            yield from _walk(child)


def _squash(text: str) -> str:
    return re.sub(r"\s+", " ", text)


def _escape(text: str) -> str:
    return text.replace("<", "&lt;")


def plain(node: Node | str) -> str:
    """Plain text of a node, for headings and labels."""
    if isinstance(node, str):
        return _squash(node)
    if node.tag in SKIP_TAGS:
        return ""
    if node.tag == "br":
        return " "
    return _squash("".join(plain(child) for child in node.children)).strip()


def raw_text(node: Node | str) -> str:
    """Text with its own spacing kept, for code lines."""
    if isinstance(node, str):
        return node
    return "".join(raw_text(child) for child in node.children)


def inline(node: Node | str, in_table: bool = False) -> str:
    if isinstance(node, str):
        return _escape(_squash(node))
    tag = node.tag
    if tag in SKIP_TAGS:
        return ""
    if tag == "br":
        return "<br>" if in_table else " "
    inner = "".join(inline(child, in_table) for child in node.children)
    if tag == "a":
        href = node.attrs.get("href", "")
        text = inner.strip()
        if not text:
            return ""
        return f"[{text}]({href})" if href and not href.startswith(("#", "javascript:")) else text
    wrap = {"strong": "**", "b": "**", "em": "*", "i": "*", "code": "`"}.get(tag)
    if wrap:
        core = inner.strip()
        if not core:
            return inner
        lead = " " if inner[:1].isspace() else ""
        trail = " " if inner[-1:].isspace() else ""
        return f"{lead}{wrap}{core}{wrap}{trail}"
    return inner


def _text(node: Node, in_table: bool = False) -> str:
    return _squash(inline(node, in_table)).strip()


def _is_card(node: Node) -> bool:
    return node.tag == "article" or bool(node.classes & CARD_CLASSES)


def _skipped(node: Node) -> bool:
    return node.consumed or node.tag in SKIP_TAGS or bool(node.classes & SKIP_CLASSES)


def _item(node: Node) -> str:
    """One card, step, or band flattened to a single line: label, bold title, then the body text."""
    label, title, body = [], [], []

    def visit(parent: Node) -> None:
        run: list[str] = []  # inline text and spans, joined as written so punctuation keeps its place

        def end_run() -> None:
            text = _squash("".join(run)).strip()
            run.clear()
            if text:
                body.append(text)

        for child in parent.children:
            if isinstance(child, str):
                run.append(_escape(child))
                continue
            if _skipped(child):
                continue
            classes = child.classes
            if child.tag in INLINE_TAGS and not classes & {"tag", "num", "big", "key", "cmd"}:
                run.append(inline(child))
                continue
            end_run()
            if child.tag == "p" and classes & {"tag", "num"}:
                label.append(f"`{plain(child)}`")
            elif child.tag in {"h2", "h3", "h4"} or "big" in classes:
                title.append(_text(child))
            elif child.tag == "p" and "key" in classes:
                body.append(f"*{_text(child)}*")
            elif child.tag == "p" and "cmd" in classes:
                body.append(f"`{plain(child)}`")
            elif child.tag in {"ul", "ol"}:
                body.append("; ".join(_text(li) for li in child.children if isinstance(li, Node) and li.tag == "li"))
            elif child.tag == "div":
                visit(child)
            else:
                body.append(_text(child))
        end_run()

    visit(node)
    head = " ".join(label)
    if title:
        head = f"{head} **{' '.join(title)}**".strip()
    text = " ".join(part for part in body if part)
    if head and text:
        return f"{head} — {text}"
    return head or text


def _table(table: Node) -> str:
    rows: list[tuple[bool, list[str]]] = []
    for tr in (n for n in _walk(table) if n.tag == "tr"):
        cells = [n for n in tr.children if isinstance(n, Node) and n.tag in {"td", "th"}]
        if cells:
            rows.append((all(c.tag == "th" for c in cells), [_text(c, True).replace("|", "\\|") for c in cells]))
    if not rows:
        return ""
    width = max(len(cells) for _, cells in rows)
    header = rows[0][1]
    body = rows[1:]
    pad = lambda cells: cells + [""] * (width - len(cells))  # noqa: E731
    lines = ["| " + " | ".join(pad(header)) + " |", "| " + " | ".join(["---"] * width) + " |"]
    lines += ["| " + " | ".join(pad(cells)) + " |" for _, cells in body]
    return "\n".join(lines)


def _blocks(node: Node) -> list[str]:
    out: list[str] = []
    cards: list[str] = []
    code: list[str] = []

    def flush() -> None:
        if cards:
            out.append("\n".join(f"- {item}" for item in cards if item))
            cards.clear()
        if code:
            out.append("```text\n" + "\n".join(code) + "\n```")
            code.clear()

    for child in node.children:
        if isinstance(child, str):
            text = _escape(_squash(child)).strip()
            if text:
                flush()
                out.append(text)
            continue
        if _skipped(child):
            continue
        classes = child.classes
        if "ln" in classes:
            if cards:
                flush()
            indent = "  " if "i1" in classes else "    " if "i2" in classes else ""
            code.append(indent + _squash(raw_text(child)).strip())
            continue
        if _is_card(child):
            if code:
                flush()
            cards.append(_item(child))
            continue
        flush()
        tag = child.tag
        if tag in {"h1", "h2"}:
            continue
        if tag in {"h3", "h4"}:
            text = _text(child)
            if text:
                out.append(f"### {text}")
        elif tag in {"ul", "ol"}:
            items = [_text(li) for li in child.children if isinstance(li, Node) and li.tag == "li"]
            out.append("\n".join((f"{n}. {t}" if tag == "ol" else f"- {t}") for n, t in enumerate(items, 1) if t))
        elif tag == "table":
            out.append(_table(child))
        elif classes & BAND_CLASSES:
            out.append("> " + _item(child))
        elif tag == "p" and classes & {"tag", "num"}:
            out.append(f"`{plain(child)}`")
        elif tag == "p" and "big" in classes:
            out.append(f"**{_text(child)}**")
        elif tag == "p" and "key" in classes:
            out.append(f"*{_text(child)}*")
        elif tag == "p" and "cmd" in classes:
            out.append(f"`{plain(child)}`")
        elif tag in {"div", "section", "article", "main", "span", "header"} and any(
            isinstance(c, Node) and c.tag in {"div", "p", "ul", "ol", "table", "h3", "h4", "article", "section"}
            for c in child.children
        ):
            out.extend(_blocks(child))
        else:
            text = _text(child)
            if text:
                out.append(text)
    flush()
    return [block for block in out if block.strip()]


def _slide(section: Node, number: int, deck_link: str) -> str:
    title_node = next((n for n in _walk(section) if n.tag in {"h1", "h2"}), None)
    eyebrow_node = next((n for n in _walk(section) if "eyebrow" in n.classes), None)
    title = plain(title_node) if title_node else ""
    eyebrow = plain(eyebrow_node) if eyebrow_node else ""
    if title_node:
        title_node.consumed = True
    if eyebrow_node:
        eyebrow_node.consumed = True
    # `inline` skips aside nodes (they are not slide content), so read the notes from their children.
    notes = [_squash("".join(inline(c) for c in a.children)).strip() for a in _walk(section) if a.tag == "aside"]

    parts = [f"## {title or eyebrow or f'Slide {number}'}"]
    meta = f"[Open slide {number} in the deck ↗]({deck_link}#{number})"
    parts.append(f"*{eyebrow}* · {meta}" if eyebrow and title else meta)
    parts += _blocks(section)
    for note in (n for n in notes if n):
        parts.append('??? note "Speaker notes"\n\n    ' + note)
    return "\n\n".join(parts)


def deck_to_markdown(html: str, title: str, deck_link: str, summary: str = "") -> str:
    """Return the whole page. `deck_link` is the path from the page to the deck's index.html."""
    root = parse(html)
    sections = [n for n in _walk(root) if n.tag == "section"]
    head = [f"# {title}"]
    intro = f"{summary} · " if summary else ""
    head.append(f"{intro}[Present this deck ↗]({deck_link}). Each slide below is a section; speaker notes are folded under it.")
    slides = [_slide(section, number, deck_link) for number, section in enumerate(sections, 1)]
    return "\n\n".join(head + slides) + "\n"
