"""Task 1.3: validate, normalize and shape input before a model sees it."""

from __future__ import annotations

import json
import re
import unicodedata
from datetime import date, datetime

SAMPLE_NOTE = """  Sent from my iPhone
ENGINEER NOTE – visit on 12/03/2025
cust reported alarm E42 on blr, fw 2.0.4 .  Tried   resetting; no joy.
Contact: Kim Lee <kim.lee@example.com>, tel 555-123-4567.
Follow-up booked for March 20, 2025 -- HVAC tech to ck PRV.
--
CONFIDENTIAL: internal use only
"""
ABBREVIATIONS = {"blr": "boiler", "fw": "firmware", "ck": "check", "prv": "pressure relief valve",
                 "cust": "customer", "tel": "telephone"}
BOILERPLATE = re.compile(r"^\s*(sent from my \w+|confidential\b.*|--+|regards,?|thanks,?)\s*$", re.IGNORECASE)
MONTHS = {m: i for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1)}


def normalize_text(text: str) -> str:
    """Unicode NFKC, control characters out, boilerplate lines out, whitespace collapsed."""
    text = unicodedata.normalize("NFKC", text)
    text = "".join(ch for ch in text if ch in "\n\t" or unicodedata.category(ch)[0] != "C")
    text = text.replace("–", "-").replace("—", "-").replace("’", "'")
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in text.splitlines()]
    kept = [line for line in lines if line and not BOILERPLATE.match(line)]
    return re.sub(r"\s+([.,;:])", r"\1", "\n".join(kept))


def expand_abbreviations(text: str, mapping: dict[str, str] = ABBREVIATIONS) -> str:
    pattern = re.compile(r"\b(" + "|".join(map(re.escape, mapping)) + r")\b", re.IGNORECASE)
    return pattern.sub(lambda m: mapping[m.group(1).lower()], text)


def to_iso(day: int, month: int, year: int) -> str | None:
    try:
        return date(year, month, day).isoformat()
    except ValueError:
        return None


def normalize_dates(text: str, day_first: bool = True) -> str:
    """Rewrite common date styles as ISO 8601. Numeric dates like 12/03/2025 are ambiguous, so the
    day/month order is an explicit choice rather than a guess."""
    def numeric(match):
        a, b, year = int(match.group(1)), int(match.group(2)), int(match.group(3))
        day, month = (a, b) if day_first else (b, a)
        return to_iso(day, month, year) or match.group(0)

    def named_dm(match):
        return to_iso(int(match.group(1)), MONTHS[match.group(2)[:3].lower()], int(match.group(3))) or match.group(0)

    def named_md(match):
        return to_iso(int(match.group(2)), MONTHS[match.group(1)[:3].lower()], int(match.group(3))) or match.group(0)

    month = r"(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*"
    text = re.sub(r"\b(\d{1,2})/(\d{1,2})/(\d{4})\b", numeric, text)
    text = re.sub(rf"\b(\d{{1,2}}) {month}\.? (\d{{4}})\b", named_dm, text)
    return re.sub(rf"\b{month} (\d{{1,2}}), (\d{{4}})\b", named_md, text)


def extract_entities(text: str) -> dict[str, list[str]]:
    """Regex extraction: fast, free and exact for well-shaped identifiers. Messy prose needs a model."""
    return {
        "dates": re.findall(r"\b\d{4}-\d{2}-\d{2}\b", text),
        "alarm_ids": sorted(set(re.findall(r"\b[EF]\d{2,3}\b", text))),
        "firmware": re.findall(r"firmware\s+v?(\d+(?:\.\d+){1,2})", text, re.IGNORECASE),
        "emails": re.findall(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+", text),
        "phones": re.findall(r"\b\d{3}-\d{3}-\d{4}\b", text),
    }


def clean(text: str, day_first: bool = True, expand: bool = True) -> str:
    text = normalize_dates(normalize_text(text), day_first)
    return expand_abbreviations(text) if expand else text


SCHEMA = {"id": int, "alarm_id": str, "firmware": str, "visit_date": str, "note": str}


def validate_record(record: dict, schema: dict[str, type] = SCHEMA) -> list[str]:
    problems = []
    for name, kind in schema.items():
        if name not in record or record[name] in (None, ""):
            problems.append(f"{name}: missing")
        elif not isinstance(record[name], kind):
            problems.append(f"{name}: expected {kind.__name__}, got {type(record[name]).__name__}")
    if isinstance(record.get("visit_date"), str):
        try:
            datetime.strptime(record["visit_date"], "%Y-%m-%d")
        except ValueError:
            problems.append("visit_date: not an ISO date (YYYY-MM-DD)")
    if isinstance(record.get("alarm_id"), str) and not re.fullmatch(r"[EF]\d{2,3}", record["alarm_id"]):
        problems.append("alarm_id: does not match E## or F##")
    return problems


def quality_report(records: list[dict]) -> dict:
    """Aggregate counts that a data-quality gate can threshold on before ingestion."""
    bad = {r.get("id", i): validate_record(r) for i, r in enumerate(records)}
    invalid = {key: problems for key, problems in bad.items() if problems}
    notes = [r.get("note", "") for r in records]
    return {
        "records": len(records), "invalid": len(invalid), "valid_rate": round(1 - len(invalid) / len(records), 3) if records else 0,
        "duplicate_notes": len(notes) - len(set(notes)), "problems": invalid,
    }


def format_request(family: str, prompt: str, system: str = "", max_tokens: int = 256) -> dict:
    """The same question in each provider's native InvokeModel body, plus the unified Converse shape."""
    if family == "converse":
        body = {"messages": [{"role": "user", "content": [{"text": prompt}]}],
                "inferenceConfig": {"maxTokens": max_tokens}}
        if system:
            body["system"] = [{"text": system}]
        return body
    if family == "anthropic":
        body = {"anthropic_version": "bedrock-2023-05-31", "max_tokens": max_tokens,
                "messages": [{"role": "user", "content": [{"type": "text", "text": prompt}]}]}
        if system:
            body["system"] = system
        return body
    if family == "nova":
        body = {"schemaVersion": "messages-v1", "messages": [{"role": "user", "content": [{"text": prompt}]}],
                "inferenceConfig": {"max_new_tokens": max_tokens}}
        if system:
            body["system"] = [{"text": system}]
        return body
    if family == "titan":
        return {"inputText": (system + "\n\n" if system else "") + prompt,
                "textGenerationConfig": {"maxTokenCount": max_tokens}}
    if family == "llama":
        return {"prompt": (system + "\n\n" if system else "") + prompt, "max_gen_len": max_tokens}
    raise ValueError(f"Unknown model family: {family}")


FAMILIES = {
    "converse": "Converse (any supported model)", "anthropic": "InvokeModel / Anthropic Claude",
    "nova": "InvokeModel / Amazon Nova", "titan": "InvokeModel / Amazon Titan Text", "llama": "InvokeModel / Meta Llama",
}
EXTRACTION_PROMPT = (
    "Extract fields from the engineer note. Return JSON only, with keys alarm_id, firmware, visit_date "
    "(ISO 8601), and follow_up_date (ISO 8601 or null). Do not invent values.\n\n<note>\n{note}\n</note>"
)


def parse_model_json(text: str) -> dict | None:
    """Pull a JSON object out of model text, tolerating a code fence."""
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        return None
    try:
        value = json.loads(match.group(0))
    except ValueError:
        return None
    return value if isinstance(value, dict) else None
