"""Task 3.1 / 3.2: layered safety checks that run without a model, plus ApplyGuardrail helpers.

These local rules are teaching examples. They show *where* each layer sits in a defense-in-depth
design; they are not a replacement for a managed guardrail.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass

INJECTION_RULES: list[tuple[str, str]] = [
    ("override-instructions", r"\b(ignore|disregard|forget)\b.{0,40}\b(previous|prior|above|earlier|all)\b.{0,30}\b(instructions?|rules?|prompts?)\b"),
    ("reveal-system-prompt", r"\b(reveal|show|print|repeat|leak)\b.{0,40}\b(system|hidden|initial)\b.{0,20}\b(prompt|instructions?|message)\b"),
    ("role-override", r"\b(you are now|act as|pretend to be|from now on you)\b.{0,60}\b(dan|unrestricted|no restrictions|without (any )?rules|jailbroken)\b"),
    ("delimiter-smuggling", r"(</?\s*(system|assistant)\s*>|^\s*#{2,}\s*system\b|\[/?INST\])"),
    ("exfiltration", r"\b(send|post|upload|forward)\b.{0,60}\b(https?://|to my (server|email))"),
]

PII_RULES: dict[str, str] = {
    "EMAIL": r"\b[\w.+-]+@[\w-]+(?:\.[\w-]+)+\b",
    "AWS_ACCESS_KEY": r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b",
    "US_SSN": r"\b\d{3}-\d{2}-\d{4}\b",
    "PHONE": r"(?<!\d)(?:\+?\d{1,2}[ .-]?)?\(?\d{3}\)?[ .-]\d{3}[ .-]\d{4}(?!\d)",
    "IP_ADDRESS": r"\b(?:\d{1,3}\.){3}\d{1,3}\b",
}
CARD_PATTERN = r"(?<!\d)(?:\d[ -]?){13,16}(?!\d)"


@dataclass(frozen=True)
class Finding:
    layer: str
    rule: str
    detail: str

    def as_row(self) -> dict:
        return {"layer": self.layer, "rule": self.rule, "detail": self.detail}


def luhn_valid(number: str) -> bool:
    digits = [int(ch) for ch in number if ch.isdigit()]
    if not 13 <= len(digits) <= 19:
        return False
    total = 0
    for index, digit in enumerate(reversed(digits)):
        if index % 2:
            digit = digit * 2 - 9 if digit > 4 else digit * 2
        total += digit
    return total % 10 == 0


def detect_injection(text: str) -> list[Finding]:
    found = []
    for name, pattern in INJECTION_RULES:
        match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE | re.DOTALL)
        if match:
            found.append(Finding("input: injection heuristics", name, match.group(0).strip()[:80]))
    return found


def find_pii(text: str) -> list[tuple[str, str]]:
    """Return (type, matched text) pairs; card numbers must pass the Luhn check."""
    hits = []
    for kind, pattern in PII_RULES.items():
        if kind == "IP_ADDRESS":
            hits += [(kind, m.group(0)) for m in re.finditer(pattern, text)
                     if all(0 <= int(part) <= 255 for part in m.group(0).split("."))]
        else:
            hits += [(kind, m.group(0)) for m in re.finditer(pattern, text)]
    hits += [("CARD_NUMBER", m.group(0).strip()) for m in re.finditer(CARD_PATTERN, text)
             if luhn_valid(m.group(0))]
    return hits


def detect_pii(text: str, layer: str = "input: PII") -> list[Finding]:
    return [Finding(layer, kind, value) for kind, value in find_pii(text)]


def mask_pii(text: str) -> str:
    """Replace each PII match with a {TYPE} placeholder, longest matches first."""
    for kind, value in sorted(find_pii(text), key=lambda hit: -len(hit[1])):
        text = text.replace(value, "{" + kind + "}")
    return text


def validate_output(
    raw: str,
    required_keys: tuple[str, ...] = ("answer", "sources"),
    disclaimer: str | None = None,
    source_text: str = "",
) -> list[Finding]:
    """Deterministic checks on a model answer: JSON shape, disclaimer, and numbers with no source."""
    layer = "output: deterministic validator"
    try:
        data = json.loads(raw)
    except (TypeError, ValueError):
        return [Finding(layer, "not-json", "The output is not valid JSON.")]
    if not isinstance(data, dict):
        return [Finding(layer, "not-object", "The JSON output is not an object.")]
    problems = [Finding(layer, "missing-key", f"Required key '{key}' is missing.")
                for key in required_keys if key not in data]
    answer = str(data.get("answer", ""))
    if disclaimer and disclaimer.lower() not in answer.lower():
        problems.append(Finding(layer, "missing-disclaimer", f"Answer must include: {disclaimer!r}."))
    if source_text:
        sources_numbers = set(re.findall(r"\d+(?:\.\d+)?", source_text))
        for number in re.findall(r"\d+(?:\.\d+)?", answer):
            if number not in sources_numbers:
                problems.append(Finding(layer, "unsupported-number", f"{number} does not appear in the source text."))
                break
    return problems


def run_layers(user_input: str, model_output: str | None = None, **output_options) -> dict:
    """Run every local layer and report which ones fired. Output layers run only when an answer is given."""
    input_findings = detect_injection(user_input) + detect_pii(user_input)
    output_findings: list[Finding] = []
    if model_output is not None:
        output_findings = detect_pii(model_output, layer="output: PII") + validate_output(model_output, **output_options)
    decision = "block" if any(f.rule in {r for r, _ in INJECTION_RULES} or f.rule == "AWS_ACCESS_KEY"
                              for f in input_findings) else "allow"
    if decision == "allow" and (input_findings or output_findings):
        decision = "review"
    return {"input": input_findings, "output": output_findings, "decision": decision}


# ---- Bedrock Guardrails -----------------------------------------------------------------------

def build_apply_request(
    guardrail_id: str, version: str, source: str, text: str,
    grounding_source: str = "", query: str = "",
) -> dict:
    """Build an ApplyGuardrail request. Grounding checks need qualified blocks (source, query, answer)."""
    if source not in ("INPUT", "OUTPUT"):
        raise ValueError("Source must be INPUT or OUTPUT.")
    if not guardrail_id.strip() or not version.strip():
        raise ValueError("Enter a guardrail ID and version.")
    if not text.strip():
        raise ValueError("Enter some text to check.")
    if grounding_source.strip():
        content = [{"text": {"text": grounding_source, "qualifiers": ["grounding_source"]}}]
        if query.strip():
            content.append({"text": {"text": query, "qualifiers": ["query"]}})
        content.append({"text": {"text": text, "qualifiers": ["guard_content"]}})
    else:
        content = [{"text": {"text": text}}]
    return {"guardrailIdentifier": guardrail_id.strip(), "guardrailVersion": version.strip(),
            "source": source, "content": content, "outputScope": "FULL"}


def summarize_assessments(response: dict) -> list[dict]:
    """Flatten the nested assessments into rows: policy, item, action."""
    rows = []
    for assessment in response.get("assessments", []):
        for policy, body in assessment.items():
            if not isinstance(body, dict):
                continue
            for collection, items in body.items():
                if not isinstance(items, list):
                    continue
                for item in items:
                    label = item.get("type") or item.get("name") or item.get("match") or collection
                    detail = item.get("match") or item.get("confidence") or item.get("score") or ""
                    rows.append({"policy": policy, "item": f"{label}", "detail": str(detail),
                                 "action": item.get("action", "")})
    return rows


def demo_guardrail_config(name: str, detect_only: bool) -> dict:
    """A small guardrail for the lab. Detect mode uses action NONE so findings are reported, not enforced."""
    action = "NONE" if detect_only else "BLOCK"
    pii_action = "NONE" if detect_only else "ANONYMIZE"
    ssn_action = "NONE" if detect_only else "BLOCK"
    return {
        "name": name,
        "description": "AIP-C01 lab guardrail (" + ("detect" if detect_only else "enforce") + " mode)",
        "blockedInputMessaging": "Sorry, I can't help with that request.",
        "blockedOutputsMessaging": "Sorry, I can't share that response.",
        "topicPolicyConfig": {"topicsConfig": [{
            "name": "Investment advice",
            "definition": "Recommendations about buying or selling specific stocks, funds or other financial products.",
            "examples": ["Which stock should I buy this week?", "Should I move my savings into crypto?"],
            "type": "DENY", "inputAction": action, "outputAction": action,
            "inputEnabled": True, "outputEnabled": True,
        }]},
        "contentPolicyConfig": {"filtersConfig": [
            {"type": "INSULTS", "inputStrength": "HIGH", "outputStrength": "HIGH",
             "inputAction": action, "outputAction": action, "inputEnabled": True, "outputEnabled": True},
            {"type": "PROMPT_ATTACK", "inputStrength": "HIGH", "outputStrength": "NONE",
             "inputAction": action, "inputEnabled": True, "outputEnabled": False},
        ]},
        "sensitiveInformationPolicyConfig": {"piiEntitiesConfig": [
            {"type": "EMAIL", "action": pii_action, "inputAction": pii_action, "outputAction": pii_action,
             "inputEnabled": True, "outputEnabled": True},
            {"type": "US_SOCIAL_SECURITY_NUMBER", "action": ssn_action, "inputAction": ssn_action,
             "outputAction": ssn_action, "inputEnabled": True, "outputEnabled": True},
        ]},
        "contextualGroundingPolicyConfig": {"filtersConfig": [
            {"type": "GROUNDING", "threshold": 0.75, "action": action, "enabled": True},
            {"type": "RELEVANCE", "threshold": 0.75, "action": action, "enabled": True},
        ]},
    }
