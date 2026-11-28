"""The study site turns each slide deck into a searchable page. These tests guard that conversion."""

import re
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT / "hooks"))
import deck_to_markdown as d2m  # noqa: E402

SAMPLE = """<html><body>
<section id="a"><p class="eyebrow">01 / Demo</p><h2>Pick <span class="accent">one</span>.</h2>
<div class="cards"><div class="card"><p class="tag">TAG</p><h3>First</h3><p class="body">Body with <span class="hl">a span</span>.</p></div>
<div class="card"><h3>Second</h3><p class="body">More text.</p></div></div>
<table class="dense"><tr><th>Option</th><th>Use</th></tr><tr><td>A | B</td><td>x<br>y</td></tr></table>
<div class="term"><p class="ln">top</p><p class="ln i1">nested</p></div>
<div class="band">Use <code>code</code> here.</div>
<div class="footer"><p>Footer text</p><p>01 / 02</p></div>
<aside>Speaker note text.</aside></section>
<section><h1>Cover</h1></section>
</body></html>"""


def convert(html=SAMPLE):
    return d2m.deck_to_markdown(html, "Title", "../slides/x/index.html", "Summary.")


class ConverterTests(unittest.TestCase):
    def test_each_slide_becomes_a_section_with_heading_and_deck_link(self):
        md = convert()
        self.assertIn("# Title", md)
        self.assertIn("## Pick one.", md)
        self.assertIn("## Cover", md)
        self.assertIn("*01 / Demo* · [Open slide 1 in the deck ↗](../slides/x/index.html#1)", md)

    def test_cards_become_a_list_and_spans_keep_punctuation(self):
        md = convert()
        self.assertIn("- `TAG` **First** — Body with a span.", md)
        self.assertIn("- **Second** — More text.", md)

    def test_table_cells_escape_pipes_and_keep_line_breaks(self):
        md = convert()
        self.assertIn("| Option | Use |", md)
        self.assertIn("| A \\| B | x<br>y |", md)

    def test_terminal_lines_become_a_code_block_and_band_a_quote(self):
        md = convert()
        self.assertIn("```text\ntop\n  nested\n```", md)
        self.assertIn("> Use `code` here.", md)

    def test_footer_is_dropped_and_notes_are_folded(self):
        md = convert()
        self.assertNotIn("Footer text", md)
        self.assertIn('??? note "Speaker notes"\n\n    Speaker note text.', md)


class DeckTests(unittest.TestCase):
    decks = sorted((ROOT / "slides").glob("*/index.html"))

    def test_every_deck_is_found(self):
        self.assertGreaterEqual(len(self.decks), 14)

    def test_every_deck_converts_cleanly_and_keeps_its_text(self):
        for path in self.decks:
            with self.subTest(deck=path.parent.name):
                html = path.read_text(encoding="utf-8")
                md = d2m.deck_to_markdown(html, path.parent.name, "../x/index.html")
                sections = [n for n in d2m._walk(d2m.parse(html)) if n.tag == "section"]
                self.assertEqual(md.count("\n## "), len(sections))
                self.assertNotRegex(md, r"</?(div|p|section|article|aside|tr|td|th|span|ul|li)\b")
                self.assertEqual(self.missing_words(html, md), set())

    def test_the_inference_deck_covers_async_invocation(self):
        path = ROOT / "slides" / "01-bedrock-inference" / "index.html"
        md = d2m.deck_to_markdown(path.read_text(encoding="utf-8"), "01", "../x/index.html")
        for needle in ("StartAsyncInvoke", "invocationArn", "InvokeModelWithResponseStream", "Speaker notes"):
            self.assertIn(needle, md)

    @staticmethod
    def missing_words(html, md):
        """Words in slide text (footers, scripts and styles aside) that the page lost."""
        root = d2m.parse(html)
        words = set()

        def visit(node, hidden):
            for child in node.children:
                if isinstance(child, str):
                    if not hidden:
                        words.update(w.lower() for w in re.findall(r"[A-Za-z]{4,}", child))
                    continue
                visit(child, hidden or child.tag in {"script", "style", "head", "nav", "button"}
                      or bool(child.classes & {"footer", "deck-controls", "edit-toggle", "edit-hotzone"}))

        visit(root, False)
        have = {w.lower() for w in re.findall(r"[A-Za-z]{4,}", md)}
        return words - have


if __name__ == "__main__":
    unittest.main()
