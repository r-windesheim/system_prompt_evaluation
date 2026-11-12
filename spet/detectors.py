"""Span-level stylistic quirk detectors.

Every detector returns character spans, so the viewer can show *what matched*.
The attribution metric is *matches per response* (``counts``). Per-100-words
rates leak across quirks: a section that makes answers longer dilutes every
other quirk's rate and shows up as a spurious effect. ``rates`` is kept for
display only. Spans are observations only. Attribution to
prompt sections is computed separately (see attribution.py) and never painted
onto spans.

Compared with the legacy detectors, the loosest patterns are gone (`like`, bare
`may`, `\\w+ed` past tense, any `but`/`yet`); see docs/OVERHAUL_PLAN.md (M8).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

I = re.IGNORECASE
M = re.MULTILINE


@dataclass(frozen=True)
class DetectorDef:
    id: str
    label: str
    group: str
    description: str
    patterns: tuple[re.Pattern[str], ...] = field(repr=False)


def _d(id: str, label: str, group: str, description: str, *patterns: str, flags: int = I) -> DetectorDef:
    return DetectorDef(id, label, group, description, tuple(re.compile(p, flags) for p in patterns))


DETECTORS: tuple[DetectorDef, ...] = (
    # Deference
    _d("apology", "Apology", "Deference", "Apologising: sorry, apologies, I apologize.",
       r"\b(?:sorry|apologi[sz]e|apologies)\b"),
    _d("flattery", "Flattery", "Deference", "Praising the user or the question.",
       r"\b(?:great|good|excellent|fantastic|interesting|thoughtful) (?:question|point|idea)\b",
       r"\bwhat an? (?:great|interesting|excellent) \w+"),
    # Certainty
    _d("hedge", "Hedging", "Certainty", "Softening a claim: might, perhaps, possibly, it seems.",
       r"\b(?:might|perhaps|possibly|potentially|arguably|presumably)\b",
       r"\bit (?:seems|appears)\b", r"\bcould be\b", r"\bI think\b", r"\bnot (?:entirely )?sure\b"),
    _d("booster", "Certainty boost", "Certainty", "Overstating confidence: definitely, clearly, absolutely.",
       r"\b(?:definitely|absolutely|clearly|obviously|certainly|undoubtedly|without a doubt)\b"),
    # Structure
    _d("list_item", "List item", "Structure", "Bulleted or numbered list lines.",
       r"^[ \t]*(?:[-*•]|\d{1,2}[.)])[ \t]+\S", flags=M),
    _d("heading", "Heading", "Structure", "Markdown headings.", r"^[ \t]*#{1,6}[ \t]+\S.*$", flags=M),
    _d("bold", "Bold emphasis", "Structure", "Markdown bold spans.", r"\*\*[^*\n]+\*\*|__[^_\n]+__"),
    _d("parenthetical", "Parenthetical", "Structure", "Asides in parentheses.", r"\([^()\n]{3,}\)"),
    # Interaction
    _d("question", "Question back", "Interaction", "Sentences addressed back to the user ending in '?'.",
       r"[^.!?\n]*\?"),
    _d("clarify", "Clarification request", "Interaction", "Asking the user for more context.",
       r"\b(?:could|can|would) you (?:please )?(?:provide|share|clarify|give|tell me|specify|elaborate)\b",
       r"\bmore (?:context|details|information)\b"),
    _d("offer", "Offer of more help", "Interaction", "Closing offers: let me know, happy to help, feel free.",
       r"\blet me know if\b", r"\b(?:I'm|I am|I'd be) (?:happy|glad) to\b", r"\bfeel free to\b",
       r"\bhope this helps\b"),
    # Framing
    _d("caveat", "Caveat", "Framing", "Sentence-initial contrast or reservation.",
       r"(?:^|(?<=[.!?]\s))(?:However|But|Although|That said|Keep in mind|Note that)\b", flags=M),
    _d("disclaimer", "Disclaimer", "Framing", "Explicit disclaimers and warnings.",
       r"\b(?:please note|it'?s important to (?:note|remember)|I'?m not a (?:doctor|lawyer|professional)|"
       r"consult (?:a|an|with a) (?:professional|doctor|lawyer|expert))\b"),
    _d("meta", "Metacommentary", "Framing", "Talking about the answer instead of answering.",
       r"\b(?:let me (?:explain|break (?:this|it) down|walk you through)|here'?s (?:a|an|the|how|what)|"
       r"to answer your question|in summary|to summari[sz]e)\b"),
    _d("self_ai", "AI self-reference", "Framing", "Referring to itself as an AI or model.",
       r"\b(?:as an AI|I'?m (?:just )?an AI|as a (?:language|AI) model|I don'?t have (?:personal|feelings|opinions))\b"),
    # Tone
    _d("exclamation", "Exclamation", "Tone", "Sentences ending in '!'.", r"[^.!?\n]*!"),
    _d("emoji", "Emoji", "Tone", "Pictographic emoji.",
       r"[\U0001F300-\U0001FAFF☀-➿]", flags=0),
)

BY_ID = {d.id: d for d in DETECTORS}
_WORD = re.compile(r"\b\w+\b")


def word_count(text: str) -> int:
    return len(_WORD.findall(text))


def spans(text: str, detectors: tuple[DetectorDef, ...] = DETECTORS) -> list[tuple[int, int, str]]:
    """All (start, end, detector_id) matches, merged per detector, sorted by start."""
    out: list[tuple[int, int, str]] = []
    for d in detectors:
        hits = sorted(
            (m.start(), m.end()) for p in d.patterns for m in p.finditer(text) if m.end() > m.start()
        )
        merged: list[list[int]] = []
        for s, e in hits:
            # strip leading whitespace so spans start on visible text
            while s < e and text[s].isspace():
                s += 1
            if s >= e:
                continue
            if merged and s < merged[-1][1]:
                merged[-1][1] = max(merged[-1][1], e)
            else:
                merged.append([s, e])
        out.extend((s, e, d.id) for s, e in merged)
    out.sort(key=lambda t: (t[0], t[1]))
    return out


def rates(text: str, detectors: tuple[DetectorDef, ...] = DETECTORS) -> dict[str, float]:
    """Matches per 100 words for each detector (0 for empty text)."""
    wc = word_count(text)
    counts = {d.id: 0 for d in detectors}
    for _, _, det in spans(text, detectors):
        counts[det] += 1
    return {k: (v / wc * 100 if wc else 0.0) for k, v in counts.items()}


def counts(text: str, detectors: tuple[DetectorDef, ...] = DETECTORS) -> dict[str, float]:
    """Matches per response for each detector: the attribution metric."""
    out = {d.id: 0.0 for d in detectors}
    for _, _, det in spans(text, detectors):
        out[det] += 1
    return out
