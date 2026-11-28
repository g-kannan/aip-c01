"""Task 1.5 / 5.2: how chunking decides what a retriever can return, and what a context window can hold.

Sizes are counted in words so the demo needs no tokenizer. One token is roughly 0.75 words; for English
text, `approx_tokens` uses 4 characters per token.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass

SAMPLE_DOCUMENT = """# AcmeHeat boiler service manual

## Alarm E42: low water pressure
When alarm E42 appears, the boiler has detected pressure below 0.8 bar. Check the pressure gauge on the front panel. If the needle is below 0.8 bar, open the filling loop valve slowly until the gauge reads 1.5 bar, then close the valve and press the reset button for three seconds. The alarm should clear within one minute and the boiler restarts on its own.

Exception: on units running firmware older than 2.1, never use the filling loop or the reset button. These units must be inspected by a certified engineer, because a stuck sensor can report low pressure incorrectly and refilling can cause dangerous overpressure.

## Alarm E17: flame failure
When alarm E17 appears, the burner did not light. Check that the gas supply is open and that other gas appliances work. Press the reset button once. If E17 returns within an hour, switch the boiler off and call the support line.

## Alarm E09: frozen condensate pipe
When alarm E09 appears in cold weather, the condensate pipe may be frozen. Pour warm, not boiling, water over the exposed pipe and press the reset button once the pipe is clear.
"""


def approx_tokens(text: str) -> int:
    return max(1, math.ceil(len(text) / 4))


@dataclass(frozen=True)
class Chunk:
    index: int
    text: str
    parent: int | None = None  # index of the parent chunk, for hierarchical chunking


def words(text: str) -> list[str]:
    return text.split()


def fixed_chunks(text: str, size: int, overlap_pct: int = 0) -> list[Chunk]:
    """Slide a window of `size` words, stepping by size minus the overlap."""
    if size < 5:
        raise ValueError("Chunk size must be at least 5 words.")
    if not 0 <= overlap_pct < 100:
        raise ValueError("Overlap must be 0 to 99 percent.")
    tokens = words(text)
    step = max(1, size - size * overlap_pct // 100)
    chunks = []
    for start in range(0, len(tokens), step):
        chunks.append(Chunk(len(chunks), " ".join(tokens[start:start + size])))
        if start + size >= len(tokens):
            break
    return chunks


def sentence_chunks(text: str, size: int) -> list[Chunk]:
    """Pack whole sentences until the next one would exceed `size` words. Never cuts mid-sentence."""
    if size < 5:
        raise ValueError("Chunk size must be at least 5 words.")
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+|\n+", text) if s.strip()]
    chunks, current = [], []
    for sentence in sentences:
        if current and len(words(" ".join(current + [sentence]))) > size:
            chunks.append(Chunk(len(chunks), " ".join(current)))
            current = []
        current.append(sentence)
    if current:
        chunks.append(Chunk(len(chunks), " ".join(current)))
    return chunks


def hierarchical_chunks(text: str, parent_size: int, child_size: int, overlap_pct: int = 0) -> tuple[list[Chunk], list[Chunk]]:
    """Return (parents, children). Children are small and searched; each points to the parent it came from."""
    if child_size >= parent_size:
        raise ValueError("The child size must be smaller than the parent size.")
    parents = fixed_chunks(text, parent_size)
    children: list[Chunk] = []
    for parent in parents:
        for child in fixed_chunks(parent.text, child_size, overlap_pct):
            children.append(Chunk(len(children), child.text, parent=parent.index))
    return parents, children


def tokenize(text: str) -> list[str]:
    return re.findall(r"[a-z0-9.]+", text.lower())


def rank(query: str, chunks: list[Chunk], k: int = 3) -> list[tuple[Chunk, float]]:
    """A small BM25-style keyword ranking, standing in for the vector search of a real retriever."""
    docs = [tokenize(c.text) for c in chunks]
    n = len(docs)
    avg = sum(map(len, docs)) / n if n else 0
    df = Counter(term for doc in docs for term in set(doc))
    scored = []
    for chunk, doc in zip(chunks, docs):
        counts = Counter(doc)
        score = 0.0
        for term in set(tokenize(query)):
            if term in counts:
                idf = math.log(1 + (n - df[term] + 0.5) / (df[term] + 0.5))
                tf = counts[term]
                score += idf * tf * 2.2 / (tf + 1.2 * (0.25 + 0.75 * len(doc) / (avg or 1)))
        scored.append((chunk, round(score, 3)))
    return sorted(scored, key=lambda pair: -pair[1])[:k]


def fit_to_window(chunks: list[str], budget_tokens: int) -> tuple[list[str], list[str]]:
    """Keep chunks in order while they fit. Returns (kept, dropped). Context overflow drops or truncates."""
    kept, used = [], 0
    for index, text in enumerate(chunks):
        cost = approx_tokens(text)
        if used + cost > budget_tokens:
            return kept, chunks[index:]
        kept.append(text)
        used += cost
    return kept, []


def contains_all(text: str, needles: tuple[str, ...]) -> bool:
    return all(needle.lower() in text.lower() for needle in needles)


# One ChunkingConfiguration per strategy, as sent to bedrock-agent CreateDataSource. The tests validate these
# against the botocore model; docs/chunking-configuration.md explains the fields and when to choose each.
CHUNKING_CONFIGS: dict[str, dict] = {
    "FIXED_SIZE": {"chunkingStrategy": "FIXED_SIZE",
                   "fixedSizeChunkingConfiguration": {"maxTokens": 300, "overlapPercentage": 20}},
    "HIERARCHICAL": {"chunkingStrategy": "HIERARCHICAL",
                     "hierarchicalChunkingConfiguration": {"levelConfigurations": [{"maxTokens": 1500}, {"maxTokens": 300}],
                                                           "overlapTokens": 60}},
    "SEMANTIC": {"chunkingStrategy": "SEMANTIC",
                 "semanticChunkingConfiguration": {"maxTokens": 300, "bufferSize": 1, "breakpointPercentileThreshold": 95}},
    "NONE": {"chunkingStrategy": "NONE"},
}
