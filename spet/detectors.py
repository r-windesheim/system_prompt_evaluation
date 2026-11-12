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
    tail_only: bool = False          # only count matches in the last two sentences
    skip_list_leadin: bool = False   # ignore labels: bullet lead-ins, table cells, bold lines standing alone
    skip_in_questions: bool = False  # ignore matches inside the model's own questions


def _d(id: str, label: str, group: str, description: str, *patterns: str, flags: int = I,
       tail_only: bool = False, skip_list_leadin: bool = False, skip_in_questions: bool = False) -> DetectorDef:
    # models often emit typographic apostrophes (it’s, I’m); accept both everywhere
    pats = tuple(re.compile(p.replace("'", "['\u2019]"), flags) for p in patterns)
    return DetectorDef(id, label, group, description, pats, tail_only, skip_list_leadin, skip_in_questions)


DETECTORS: tuple[DetectorDef, ...] = (
    # Deference
    _d("apology", "Apology", "Deference", "Apologising: I'm sorry, apologies, I apologize (not sympathy).",
       r"\b(?:apologi[sz]e|apologies)\b",
       r"\bsorry\b(?! to hear)(?! (?:that )?(?:you|your)\b)(?! (?:for|about) (?:the|your) (?:trouble|frustration|inconvenience)\b)"),
    _d("sympathy", "Sympathy", "Deference", "Sympathising with the user: sorry to hear, sorry you're…",
       r"\bsorry to hear\b", r"\bsorry (?:that )?(?:you|your)\b",
       r"\bsorry (?:for|about) (?:the|your) (?:trouble|frustration|inconvenience)\b"),
    _d("flattery", "Flattery", "Deference", "Praising the user or the question.",
       r"\b(?:great|good|excellent|fantastic|interesting|thoughtful) (?:question|point)\b",
       # "good idea" dropped: 0/4 in the audit ("whether it's a good idea or not")
       r"\bwhat an? (?:great|interesting|excellent) \w+"),
    # Certainty
    _d("hedge", "Hedging", "Certainty", "Softening a claim: might, perhaps, possibly, it seems, I think.",
       r"(?<!what )(?<!which )\b(?:might|perhaps|possibly|potentially|arguably|presumably)\b",
       r"\bit (?:seems|appears)\b", r"\bcould be\b", r"\bI think\b(?!:)", skip_in_questions=True),
    _d("unclear", "Didn't understand", "Certainty", "Saying it doesn't understand what the user means.",
       r"\bnot (?:entirely |quite |totally )?sure (?:what|which|how|if|whether|I (?:understand|follow))\b",
       r"\b(?:I don't|I do not) (?:quite |fully )?(?:understand|follow)\b",
       r"\bit's (?:not |un)clear (?:what|which)\b", r"\bnot (?:quite )?clear (?:on|about) what\b"),
    _d("booster", "Certainty boost", "Certainty", "Overstating confidence: definitely, clearly, absolutely.",
       r"\b(?:definitely|absolutely|obviously|certainly|undoubtedly|without a doubt)\b",
       # "clearly" only as a stance marker; as a manner adverb ("explain clearly") it was 0/7 in the audit
       r"\b(?:is|are|was|were|it's) clearly\b", r"(?:^|(?<=[.!?]\s))Clearly,"),
    # Structure
    _d("list_item", "List item", "Structure", "Bulleted or numbered list lines.",
       r"^[ \t]*(?:[-*•]|\d{1,2}[.)])[ \t]+\S.*$", flags=M),
    _d("heading", "Heading", "Structure", "Markdown headings.", r"^[ \t]*#{1,6}[ \t]+\S.*$", flags=M),
    _d("bold", "Bold emphasis", "Structure", "Markdown bold inside running text (not bullet lead-ins).",
       r"\*\*[^*\n]+\*\*|__[^_\n]+__", skip_list_leadin=True),
    _d("parenthetical", "Parenthetical", "Structure", "Asides in parentheses.", r"\([^()\n]{3,}\)"),
    # Interaction
    _d("question", "Question back", "Interaction", "Sentences addressed back to the user ending in '?'.",
       r"(?:(?:\be\.g|\bi\.e|\betc|\bvs)\.|[^.!?\n])*\?"),
    _d("clarify", "Clarification request", "Interaction", "Asking the user for more context.",
       r"\b(?:could|can|would) you (?:please )?(?:provide|share|clarify|give|tell me|specify|elaborate|"
       r"let me know|explain|describe|say (?:a bit )?more|point me)\b",
       r"\bmore (?:context|details|information)\b",
       r"\b(?:feel free to|please|just) (?:share|provide|paste|send|give|tell)\b",
       r"\bwhat (?:exactly )?(?:are you|you're) referring to\b", r"\bwhat (?:exactly )?do you mean\b"),
    _d("offer", "Offer of more help", "Interaction", "A closing offer in the last two sentences: let me know if, happy to help.",
       r"\blet me know if\b", r"\b(?:I'm|I am|I'd be) (?:happy|glad) to (?:help|assist|dig|walk|go)\b",
       r"\bfeel free to (?:reach out|ask|follow up|let me know)\b", r"\bhope this helps\b", tail_only=True),
    # Framing
    _d("caveat", "Caveat", "Framing", "Sentence-initial contrast or reservation.",
       r"(?:^|(?<=[.!?]\s))(?:However|But|Although|That said|Keep in mind|Note that)\b", flags=M),
    _d("disclaimer", "Disclaimer", "Framing", "Explicit disclaimers and warnings.",
       r"\b(?:please note|it'?s important to (?:note|remember)|I'?m not a (?:doctor|lawyer|professional)|"
       r"consult (?:a|an|with a) (?:professional|doctor|lawyer|expert))\b"),
    _d("meta", "Metacommentary", "Framing", "Talking about the answer instead of answering.",
       r"\b(?:let me (?:explain|break (?:this|it) down|walk you through)|"
       r"to answer your question|in summary|to summari[sz]e)\b"),
    _d("self_ai", "AI self-reference", "Framing", "Referring to itself as an AI or model.",
       r"\b(?:as an AI|I'?m (?:just )?an AI|as a (?:language|AI) model|I don'?t have (?:personal|feelings|opinions))\b"),
    # Tone
    _d("exclamation", "Exclamation", "Tone", "Sentences ending in '!'.", r"[^.!?\n]*!"),
    _d("emoji", "Emoji", "Tone", "Pictographic emoji.",
       r"[\U0001F300-\U0001FAFF☀-➿]", flags=0),
)

BY_ID = {d.id: d for d in DETECTORS}
_LEADIN = re.compile(r"[ \t]*(?:[-*\u2022]|\d{1,2}[.)])[ \t]+\*")  # bullet marker then the bold's first '*'
_SENT_END = re.compile(r"[.!?](?:[\"')\]]*)\s+")


_FENCE = re.compile(r"^[ \t]*```.*?(?:^[ \t]*```[^\n]*$|\Z)", re.M | re.S)


def _is_label(text: str, h: tuple[int, int]) -> bool:
    """Bold used as a label rather than emphasis: bullet lead-in, table cell, or a line on its own."""
    ls = text.rfind("\n", 0, h[0]) + 1
    le = text.find("\n", h[1])
    line = text[ls:le if le != -1 else len(text)]
    if _LEADIN.fullmatch(text, ls, h[0] + 1) or line.lstrip().startswith("|"):
        return True
    rest = (text[ls:h[0]] + text[h[1]:le if le != -1 else len(text)]).strip(" \t:#*-\u2022")
    return rest == ""


def _tail_start(text: str) -> int:
    """Start offset of the last two sentences."""
    ends = [m.end() for m in _SENT_END.finditer(text.rstrip())]
    return ends[-2] if len(ends) >= 2 else 0
_WORD = re.compile(r"\b\w+\b")


def word_count(text: str) -> int:
    return len(_WORD.findall(text))


def spans(text: str, detectors: tuple[DetectorDef, ...] = DETECTORS) -> list[tuple[int, int, str]]:
    """All (start, end, detector_id) matches, merged per detector, sorted by start."""
    out: list[tuple[int, int, str]] = []
    tail = _tail_start(text)
    fences = [(m.start(), m.end()) for m in _FENCE.finditer(text)]
    questions = [(m.start(), m.end()) for m in BY_ID["question"].patterns[0].finditer(text)] if any(
        d.skip_in_questions for d in detectors) else []
    for d in detectors:
        hits = sorted(
            (m.start(), m.end()) for p in d.patterns for m in p.finditer(text) if m.end() > m.start()
        )
        # code blocks are not prose: no habits inside them (e.g. "# comment" is not a heading)
        hits = [h for h in hits if not any(a <= h[0] < b for a, b in fences)]
        if d.skip_in_questions:
            hits = [h for h in hits if not any(a <= h[0] < b for a, b in questions)]
        if d.tail_only:
            hits = [h for h in hits if h[0] >= tail]
        if d.skip_list_leadin:
            hits = [h for h in hits if not _is_label(text, h)]
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


# ---------------------------------------------------------------------------
# Shape metrics: per-answer numbers that are not span detectors. They run through
# the same paired analysis, so length and formatting shifts are visible as effects
# in their own right (methodology review, problems 9 and 10).
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class MetricDef:
    id: str
    label: str
    group: str
    description: str
    unit: str
    binary: bool = False


METRICS: tuple[MetricDef, ...] = (
    MetricDef("words", "Answer length", "Shape", "Words per answer.", "words"),
    MetricDef("lines", "Lines", "Shape", "Non-empty lines per answer.", "lines"),
    MetricDef("any_question", "Asks any question", "Shape", "Share of answers with at least one question.", "share of answers", True),
    MetricDef("ends_question", "Ends with a question", "Shape", "Share of answers whose last sentence is a question.", "share of answers", True),
    MetricDef("any_list", "Uses a list", "Shape", "Share of answers with at least one list item.", "share of answers", True),
    MetricDef("asks_context", "Asks for context", "Shape", "Share of answers that ask the user for more context.", "share of answers", True),
)
METRIC_BY_ID = {m.id: m for m in METRICS}
_TRAIL = re.compile(r"[\s\U0001F300-\U0001FAFF☀-➿*_)\"'”]+$")


def metrics(text: str, sp: list[tuple[int, int, str]] | None = None) -> dict[str, float]:
    sp = spans(text) if sp is None else sp
    kinds = {d for _, _, d in sp}
    body = _TRAIL.sub("", text.strip())
    return {
        "words": float(word_count(text)),
        "lines": float(sum(1 for ln in text.splitlines() if ln.strip())),
        "any_question": float("question" in kinds),
        "ends_question": float(body.endswith("?")),
        "any_list": float("list_item" in kinds),
        "asks_context": float("clarify" in kinds),
    }


def list_line_share(text: str, sp: list[tuple[int, int, str]], detector: str) -> tuple[int, int]:
    """(matches of `detector` that sit on a list line, total matches of `detector`)."""
    lines = [(m.start(), m.end()) for m in BY_ID["list_item"].patterns[0].finditer(text)]
    hits = [(s, e) for s, e, d in sp if d == detector]
    inside = sum(1 for s, _ in hits if any(a <= s < b for a, b in lines))
    return inside, len(hits)


def detector_version() -> str:
    import hashlib
    from pathlib import Path
    return hashlib.sha256(Path(__file__).read_bytes()).hexdigest()[:12]
