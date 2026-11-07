"""
The ONLY place LLM calls happen in this codebase (see .claude/CLAUDE.md).

Three tiers:
  FAST_MODEL   (gpt-5.4-mini) -> job 1: consent.py banner-click fallback
                                  job 2: policy.py extraction
  STRONG_MODEL (gpt-5.4)      -> job 3: letter.py drafting only
  REVIEW_MODEL (env var, defaults to FAST_MODEL)
                              -> job 4: legal_review.py (AI legal review of the evidence)
     Set REVIEW_MODEL=<model id> in .env to switch (e.g. to a Luna model) without code changes.

Never import this from capture.py.
"""
import json
import os
import time

from openai import OpenAI

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

FAST_MODEL = "gpt-5.4-mini"
STRONG_MODEL = "gpt-5.4"
REVIEW_MODEL = os.getenv("REVIEW_MODEL", FAST_MODEL)  # read after load_dotenv(), so .env works

# Budget guard: a normal audit makes 2-4 calls (banner fallback, policy, review, letter).
# Anything past this is a bug (e.g. a retry loop) burning credit, so refuse the call.
MAX_CALLS_PER_AUDIT = 6

_client = None


def _get_client():
    global _client
    if _client is None:
        _client = OpenAI()
    return _client


class Cost:
    """Cumulative cost tracker for one audit run. Create one per audit,
    pass it to every ask_fast()/ask_strong() call via cost=, then call
    as_dict() and drop the result into audit_json["cost"]."""

    def __init__(self):
        self.llm_calls = 0
        self.input_tokens = 0
        self.output_tokens = 0
        self.models_used = set()
        self._start = time.monotonic()

    def record(self, model, usage):
        self.llm_calls += 1
        self.input_tokens += usage.prompt_tokens
        self.output_tokens += usage.completion_tokens
        self.models_used.add(model)

    def as_dict(self):
        return {
            "llm_calls": self.llm_calls,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "model": "+".join(sorted(self.models_used)) if self.models_used else None,
            "elapsed_s": round(time.monotonic() - self._start, 2),
        }


usage = Cost()  # convenience default for quick/ad-hoc scripts only


class CallLimitReached(RuntimeError):
    """Raised instead of making an LLM call once an audit has used MAX_CALLS_PER_AUDIT."""


def _call(model, prompt, *, system, max_tokens, json_mode, cost):
    # Only per-audit Cost objects are capped; the global `usage` default is for ad-hoc scripts.
    if cost is not None and cost.llm_calls >= MAX_CALLS_PER_AUDIT:
        raise CallLimitReached(f"LLM call limit reached ({MAX_CALLS_PER_AUDIT} per audit)")
    cost = cost or usage
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    kwargs = {
        "model": model,
        "messages": messages,
        "max_completion_tokens": max_tokens,
    }
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}
    response = _get_client().chat.completions.create(**kwargs)
    cost.record(model, response.usage)
    text = response.choices[0].message.content
    return json.loads(text) if json_mode else text


def ask_fast(prompt, *, system=None, max_tokens=500, json_schema=None, cost=None):
    """System-1: quick judgment calls. Pass json_schema (any truthy value) for
    a parsed dict back — the prompt itself must describe the required shape,
    since this uses plain JSON mode rather than strict schema validation."""
    return _call(FAST_MODEL, prompt, system=system, max_tokens=max_tokens,
                 json_mode=json_schema is not None, cost=cost)


def ask_strong(prompt, *, system=None, max_tokens=2000, cost=None):
    """System-2: plain text only, used for letter drafting."""
    return _call(STRONG_MODEL, prompt, system=system, max_tokens=max_tokens,
                 json_mode=False, cost=cost)


def ask_review(prompt, *, system=None, max_tokens=6000, cost=None):
    """Job 4: legal review. Always JSON back (the prompt must describe the shape).
    6000 tokens: reasoning-style models spend part of the budget thinking before answering,
    and a cut-off answer is broken JSON."""
    return _call(REVIEW_MODEL, prompt, system=system, max_tokens=max_tokens,
                 json_mode=True, cost=cost)


def ask_strong_json(prompt, *, system=None, max_tokens=2500, cost=None):
    """Job 3 (letter drafting) with a JSON answer ({"subject", "body"}) so the subject
    line and body come back separately."""
    return _call(STRONG_MODEL, prompt, system=system, max_tokens=max_tokens,
                 json_mode=True, cost=cost)
