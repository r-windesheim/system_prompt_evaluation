"""Split a system prompt into sections.

Two strategies:
- ``split_heuristic``: deterministic. Splits on top-level XML blocks, markdown
  headings, or blank-line paragraphs, in that order of preference.
- ``split_with_model``: asks the configured endpoint to group the prompt into
  sections and return the exact text. Every section the model returns must
  appear verbatim in the prompt, and together they must cover most of it.
  Otherwise we fall back to the heuristic, so the model can't paraphrase the
  prompt being tested.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass


@dataclass
class Section:
    label: str
    text: str


def _label_from(text: str) -> str:
    t = text.strip()
    m = re.match(r"^\s*#{1,6}\s+(.+)$", t, re.M)
    if m:
        return m.group(1).strip()[:48]
    m = re.match(r"^\s*<([A-Za-z_][\w-]*)", t)
    if m:
        return m.group(1).replace("_", " ").replace("-", " ").capitalize()[:48]
    words = re.sub(r"\s+", " ", t).split(" ")
    return (" ".join(words[:5]) + ("…" if len(words) > 5 else ""))[:48]


def _merge_small(parts: list[str], min_chars: int = 25) -> list[str]:
    out: list[str] = []
    for p in parts:
        if out and len(p) < min_chars:
            out[-1] = out[-1] + "\n\n" + p
        else:
            out.append(p)
    if len(out) > 1 and len(out[0]) < min_chars:
        out[1] = out[0] + "\n\n" + out[1]
        out.pop(0)
    return out


def split_heuristic(prompt: str, max_sections: int = 16) -> list[Section]:
    p = prompt.strip()
    if not p:
        return []
    # 1. top-level XML blocks (<tag> ... </tag>), keeping text between them as its own block
    xml = list(re.finditer(r"<([A-Za-z_][\w-]*)[^>]*>.*?</\1>", p, re.S))
    if len(xml) >= 2:
        parts, cur = [], 0
        for m in xml:
            if p[cur:m.start()].strip():
                parts.append(p[cur:m.start()].strip())
            parts.append(m.group(0).strip())
            cur = m.end()
        if p[cur:].strip():
            parts.append(p[cur:].strip())
    # 2. markdown headings
    elif len(re.findall(r"^\s*#{1,6}\s+\S", p, re.M)) >= 2:
        parts = [b.strip() for b in re.split(r"(?=^\s*#{1,6}\s+\S)", p, flags=re.M) if b.strip()]
    # 3. paragraphs, or sentences for a single-paragraph prompt
    else:
        parts = [b.strip() for b in re.split(r"\n\s*\n", p) if b.strip()]
        if len(parts) == 1:
            parts = [s.strip() for s in re.split(r"(?<=[.!?])\s+(?=[A-Z])", p) if s.strip()]
    parts = _merge_small(parts)
    while len(parts) > max_sections:  # merge the shortest adjacent pair
        i = min(range(len(parts) - 1), key=lambda j: len(parts[j]) + len(parts[j + 1]))
        parts[i : i + 2] = [parts[i] + "\n\n" + parts[i + 1]]
    return [Section(_label_from(t), t) for t in parts]


SPLIT_INSTRUCTIONS = """You split system prompts into sections for an ablation study.
Group the prompt into 4-14 coherent sections (one topic or instruction group each).
Copy each section's text EXACTLY from the prompt: no paraphrasing, no omissions, no reordering.
Give each a short label (2-4 words).
Reply with JSON only: {"sections": [{"label": "...", "text": "..."}]}"""


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def validate_model_split(prompt: str, raw: str) -> list[Section] | None:
    m = re.search(r"\{.*\}", raw, re.S)
    if not m:
        return None
    try:
        items = json.loads(m.group(0))["sections"]
    except (json.JSONDecodeError, KeyError, TypeError):
        return None
    np_ = _norm(prompt)
    out = []
    for it in items:
        if not isinstance(it, dict) or not isinstance(it.get("text"), str):
            return None
        if _norm(it["text"]) not in np_:  # paraphrased: reject the whole split
            return None
        out.append(Section(str(it.get("label") or _label_from(it["text"]))[:48], it["text"].strip()))
    covered = sum(len(_norm(s.text)) for s in out)
    if len(out) < 2 or covered < 0.85 * len(np_):
        return None
    return out


async def split_with_model(prompt: str, provider) -> tuple[list[Section], str]:
    """Returns (sections, method), where method is "model" or "heuristic"."""
    try:
        raw = await provider.complete(SPLIT_INSTRUCTIONS, prompt, temperature=0.0, seed=0)
        got = validate_model_split(prompt, raw)
        if got:
            return got, "model"
    except Exception:  # noqa: BLE001 (endpoint down: fall back)
        pass
    return split_heuristic(prompt), "heuristic"
