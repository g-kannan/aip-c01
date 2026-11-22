"""Task 2.1 / 2.4 / 1.2: retries, backoff, circuit breakers, fallbacks, routing and agent stop conditions.

Everything here runs on a virtual clock, so a simulation of minutes finishes instantly and is repeatable.
"""

from __future__ import annotations

import random
from collections import Counter
from dataclasses import dataclass, field

BACKOFF_MODES = ["none", "fixed", "exponential", "full jitter", "equal jitter"]
RETRYABLE = {"429", "500", "503", "timeout"}


def backoff_delay(attempt: int, mode: str, base: float = 0.5, cap: float = 20.0, rng: random.Random | None = None) -> float:
    """Seconds to wait before retry number `attempt` (1 = first retry)."""
    rng = rng or random.Random()
    ceiling = min(cap, base * 2 ** (attempt - 1))
    if mode == "none":
        return 0.0
    if mode == "fixed":
        return base
    if mode == "exponential":
        return ceiling
    if mode == "full jitter":
        return rng.uniform(0, ceiling)
    if mode == "equal jitter":
        return ceiling / 2 + rng.uniform(0, ceiling / 2)
    raise ValueError(f"Unknown backoff mode: {mode}")


@dataclass
class CallResult:
    success: bool
    attempts: int
    elapsed: float
    trace: list[dict] = field(default_factory=list)


def call_with_retry(outcomes: list[str], mode: str, max_attempts: int = 4, deadline: float | None = None,
                    base: float = 0.5, cap: float = 20.0, latency: float = 0.4, seed: int = 1) -> CallResult:
    """Replay scripted `outcomes` ('ok', '429', '500', '503', 'timeout', '400') against a retry policy.

    Non-retryable outcomes (such as 400 or 403) stop immediately; retrying a bad request never fixes it.
    A deadline bounds the *total* time, because retries multiply latency.
    """
    rng = random.Random(seed)
    clock, trace = 0.0, []
    for attempt in range(1, max_attempts + 1):
        outcome = outcomes[min(attempt - 1, len(outcomes) - 1)]
        clock += latency * (5 if outcome == "timeout" else 1)
        trace.append({"attempt": attempt, "t": round(clock, 2), "outcome": outcome, "wait_before_next": 0.0})
        if outcome == "ok":
            return CallResult(True, attempt, round(clock, 2), trace)
        if outcome not in RETRYABLE:
            trace[-1]["note"] = "not retryable: stop"
            return CallResult(False, attempt, round(clock, 2), trace)
        if attempt == max_attempts:
            trace[-1]["note"] = "attempts exhausted"
            break
        wait = backoff_delay(attempt, mode, base, cap, rng)
        if deadline is not None and clock + wait > deadline:
            trace[-1]["note"] = "deadline would be exceeded: give up"
            break
        trace[-1]["wait_before_next"] = round(wait, 2)
        clock += wait
    return CallResult(False, len(trace), round(clock, 2), trace)


def simulate_herd(clients: int, capacity_per_second: int, mode: str, max_attempts: int = 6,
                  base: float = 1.0, cap: float = 16.0, seed: int = 7) -> dict:
    """Many clients hit a rate-limited service at t=0. Without jitter they retry in lockstep."""
    rng = random.Random(seed)
    pending = {i: 0.0 for i in range(clients)}
    attempts = Counter()
    per_second: Counter = Counter()
    succeeded, gave_up = 0, 0
    for second in range(0, 200):
        due = [c for c, t in pending.items() if int(t) <= second]
        if not due:
            if not pending:
                break
            continue
        rng.shuffle(due)
        per_second[second] = len(due)
        for index, client in enumerate(due):
            attempts[client] += 1
            if index < capacity_per_second:
                del pending[client]
                succeeded += 1
            elif attempts[client] >= max_attempts:
                del pending[client]
                gave_up += 1
            else:
                pending[client] = second + max(0.0, backoff_delay(attempts[client], mode, base, cap, rng))
                if mode == "none":
                    pending[client] = second + 1  # an immediate retry lands in the next bucket
    horizon = max(per_second, default=0) + 1
    return {"mode": mode, "succeeded": succeeded, "gave_up": gave_up,
            "peak_load": max(per_second.values(), default=0), "total_requests": sum(per_second.values()),
            "load_by_second": [per_second.get(s, 0) for s in range(horizon)]}


class CircuitBreaker:
    """closed -> open after N consecutive failures -> half-open after a cool-down -> closed on one success."""

    def __init__(self, failure_threshold: int = 3, reset_after: float = 30.0):
        self.threshold, self.reset_after = failure_threshold, reset_after
        self.state, self.failures, self.opened_at = "closed", 0, 0.0

    def allow(self, now: float) -> bool:
        if self.state == "open":
            if now - self.opened_at >= self.reset_after:
                self.state = "half-open"
                return True
            return False
        return True

    def record(self, success: bool, now: float) -> None:
        if success:
            self.state, self.failures = "closed", 0
            return
        self.failures += 1
        if self.state == "half-open" or self.failures >= self.threshold:
            self.state, self.opened_at = "open", now


def run_with_breaker(outcomes: list[str], threshold: int = 3, reset_after: float = 30.0, spacing: float = 5.0) -> list[dict]:
    """One call every `spacing` seconds. While open, calls fail fast and never touch the dependency."""
    breaker, rows = CircuitBreaker(threshold, reset_after), []
    for index, outcome in enumerate(outcomes):
        now = index * spacing
        if not breaker.allow(now):
            rows.append({"t": now, "state": "open", "call": "skipped (fail fast)", "outcome": "-"})
            continue
        state_before = breaker.state
        breaker.record(outcome == "ok", now)
        rows.append({"t": now, "state": state_before, "call": "sent", "outcome": outcome})
    return rows


def call_chain(models: list[dict]) -> list[dict]:
    """Try models in order until one succeeds. `models` rows: {name, outcome}. Returns the attempt log."""
    log = []
    for model in models:
        log.append({"model": model["name"], "outcome": model["outcome"]})
        if model["outcome"] == "ok":
            break
    return log


TIERS = {"small": "fast, cheap model", "large": "capable, slower model"}


def choose_tier(prompt: str, mode: str, stats: dict[str, float] | None = None, task: str = "") -> str:
    """Routing: by a static rule on the task, by the content of the prompt, or by observed latency."""
    if mode == "static":
        return "large" if task in {"analysis", "code"} else "small"
    if mode == "content":
        hard = len(prompt.split()) > 60 or any(w in prompt.lower() for w in ("explain why", "step by step", "compare", "prove"))
        return "large" if hard else "small"
    if mode == "performance":
        stats = stats or {}
        return min(stats, key=stats.get) if stats else "small"
    raise ValueError(f"Unknown routing mode: {mode}")


def run_agent(steps: list[dict], max_steps: int = 6, time_budget: float = 20.0, token_budget: int = 3000,
              stop_on_repeat: bool = True) -> dict:
    """Walk a scripted agent. Each step is {action, seconds, tokens}. The first guard that trips stops the loop."""
    elapsed, tokens, seen, trace = 0.0, 0, Counter(), []
    for index, step in enumerate(steps, 1):
        reason = None
        if index > max_steps:
            reason = f"max steps ({max_steps})"
        elif elapsed + step["seconds"] > time_budget:
            reason = f"time budget ({time_budget:g}s)"
        elif tokens + step["tokens"] > token_budget:
            reason = f"token budget ({token_budget})"
        elif stop_on_repeat and seen[step["action"]] >= 2:
            reason = f"repeated action '{step['action']}' (loop detected)"
        if reason:
            return {"stopped": reason, "steps": len(trace), "seconds": elapsed, "tokens": tokens, "trace": trace}
        elapsed += step["seconds"]
        tokens += step["tokens"]
        seen[step["action"]] += 1
        trace.append({"step": index, **step, "total_tokens": tokens})
    return {"stopped": "finished normally", "steps": len(trace), "seconds": elapsed, "tokens": tokens, "trace": trace}


LOOPING_AGENT = [{"action": "search_docs", "seconds": 2.0, "tokens": 500}] * 3 + [
    {"action": "summarize", "seconds": 3.0, "tokens": 700}] + [{"action": "search_docs", "seconds": 2.0, "tokens": 500}] * 6
