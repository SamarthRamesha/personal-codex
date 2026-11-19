"""Content-free model metadata and bounded inference observations; no I/O."""
from __future__ import annotations

import math
import re
import time


def number(value, maximum, *, integer=False):
    if type(value) not in ((int,) if integer else (int, float)):
        return None
    if not 0 <= value <= maximum or not math.isfinite(value):
        return None
    return value


def label(value, maximum=120):
    if (not isinstance(value, str) or not value or value.strip() != value or len(value) > maximum
            or any(ord(c) < 32 or 127 <= ord(c) <= 159 or '\u202a' <= c <= '\u202e' or '\u2066' <= c <= '\u2069' for c in value)):
        return None
    return value


def model_catalog(entries):
    """Whitelist /api/tags fields. Unknown capabilities/context are never guessed."""
    if not isinstance(entries, list):
        return []
    models, seen = [], set()
    for entry in entries[:1000]:
        if not isinstance(entry, dict):
            continue
        name = label(entry.get("name"))
        if not name or name in seen:
            continue
        seen.add(name)
        details = entry.get("details") if isinstance(entry.get("details"), dict) else {}
        digest = entry.get("digest")
        if not isinstance(digest, str) or not re.fullmatch(r"(?:sha256:)?[0-9a-f]{64}", digest):
            digest = None
        models.append({"name": name, "digest": digest, "size_bytes": number(entry.get("size"), 10**13, integer=True),
                       "format": label(details.get("format")), "family": label(details.get("family")),
                       "parameter_size": label(details.get("parameter_size")),
                       "quantization": label(details.get("quantization_level")), "context_length": None,
                       "tool_calls": None, "vision": None, "hardware_fit": "unmeasured",
                       "metadata_source": "ollama-tags"})
        if len(models) == 200:
            break
    return models


def reported_usage(reply, *, kind="ollama"):
    """Server-reported counts/durations, distinct from observed client timings."""
    if not isinstance(reply, dict):
        return {}
    fields = ({"prompt_eval_count": "input_tokens", "eval_count": "output_tokens",
               "eval_duration": "generation_ns", "prompt_eval_duration": "prompt_eval_ns",
               "load_duration": "load_ns", "total_duration": "total_ns"} if kind == "ollama" else
              {"prompt_tokens": "input_tokens", "completion_tokens": "output_tokens"})
    values = {}
    for source, target in fields.items():
        value = number(reply.get(source), 86_400*10**9 if target.endswith("_ns") else 10**9, integer=True)
        if value is not None:
            values[target] = value
    if values.get("generation_ns", 0) > 0 and "output_tokens" in values:
        values["tokens_per_second"] = round(values["output_tokens"]*10**9/values["generation_ns"], 3)
    return values


def completed(started, first_text=None, reported=None):
    duration = max(0, (time.monotonic()-started)*1000)
    first_ms = max(0, (first_text-started)*1000) if first_text is not None else None
    return {"client_duration_ms": round(duration, 3),
            "first_text_ms": round(first_ms, 3) if first_ms is not None else None,
            "provider_reported": reported or {}}


def invocation_metrics(value, started):
    """Accept closed numeric fields only; the caller always measures its own total."""
    result = completed(started)
    if not isinstance(value, dict):
        return result
    first = number(value.get("first_text_ms"), result["client_duration_ms"])
    result["first_text_ms"] = first
    source = value.get("provider_reported")
    if isinstance(source, dict):
        limits = {"input_tokens": 10**9, "output_tokens": 10**9,
                  **{key: 86_400*10**9 for key in ("generation_ns", "prompt_eval_ns", "load_ns", "total_ns")}}
        for key, maximum in limits.items():
            valid = number(source.get(key), maximum, integer=True)
            if valid is not None:
                result["provider_reported"][key] = valid
        counts = result["provider_reported"]
        if counts.get("generation_ns", 0) > 0 and "output_tokens" in counts:
            counts["tokens_per_second"] = round(counts["output_tokens"]*10**9/counts["generation_ns"], 3)
    return result
