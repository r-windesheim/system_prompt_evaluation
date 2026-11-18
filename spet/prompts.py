"""Prompts and output parsers for the discovery stage (spet/discovery.py).

Written for a small reasoning model (gpt-oss-20b on vLLM): short instructions and a
strict, minimal output format. Parsers are defensive. Output they cannot read is
reported as unreadable (None), never guessed as "no".
"""

from __future__ import annotations

import hashlib
import re

# 1a. Intended behaviour, from the instruction text alone.
INTENDED_SYSTEM = """You turn one instruction from a system prompt into checks.
Write up to {n} short statements about a single assistant answer that would be true if the assistant followed the instruction.
Each statement must be checkable with yes or no by reading one answer and the user's question.
Start each statement with "The answer". If the instruction only applies in some situations, say so, e.g. "If the user reports a problem, the answer apologises."
Output only the statements, one per line, each starting with "- "."""

# 1b. Discovered differences, from paired answers. The instruction is NOT shown.
PROPOSE_SYSTEM = """You compare pairs of assistant answers. In each pair both answers reply to the same user question.
One answer in each pair comes from group A, the other from group B. The two groups differ in one hidden way.
Find differences that recur across several pairs: things that appear in one group's answers much more often than in the other's.
Write up to {n} statements, each about a single answer and checkable with yes or no by reading that one answer.
Start each statement with "The answer". Do not mention groups, pairs, or the other answer, and do not compare.
Output only the statements, one per line, each starting with "- "."""

# 2. Verification: one statement, one question, one answer. Nothing about the configuration.
JUDGE_SYSTEM = """You check one statement against one assistant answer.
Reply with exactly one word:
YES if the statement is true of the answer,
NO if it is false,
NA if the statement only applies to a situation that the user's question does not involve."""

# 3. Re-judging with a second, equivalent template (different wording, order and option order),
#    so agreement measures how stable the verdict is, not the cache.
JUDGE_ALT_SYSTEM = """Read the assistant answer, then decide whether the claim holds for it.
Output a single word:
NA if the claim is about a situation the user's question does not involve,
NO if the claim does not hold,
YES if the claim holds."""

# 4. Classification of a verified effect relative to the instruction.
CLASSIFY_SYSTEM = """You decide whether a change in an assistant's answers is what an instruction asks for.
Reply with exactly one word:
INTENDED if the instruction asks for this change or directly implies it,
SIDE_EFFECT if it does not."""


def intended_user(instruction: str) -> str:
    return f"Instruction:\n{instruction.strip()}"


def propose_user(pairs: list[tuple[str, str, str]]) -> str:
    """pairs: (question, answer shown first, answer shown second) with labels already applied by the caller."""
    blocks = []
    for i, (q, first, second) in enumerate(pairs, 1):
        blocks.append(f"### Pair {i}\nUser question: {q}\n\n{first}\n\n{second}")
    return "\n\n".join(blocks)


def labelled(label: str, text: str) -> str:
    return f"[Answer from group {label}]\n{text.strip()}\n[End of answer]"


def judge_user(statement: str, question: str, answer: str) -> str:
    return (f"Statement: {statement}\n\nUser question:\n{question}\n\nAnswer:\n<<<\n{answer.strip()}\n>>>\n\n"
            "Reply YES, NO or NA.")


def judge_alt_user(statement: str, question: str, answer: str) -> str:
    return (f"Assistant answer:\n<<<\n{answer.strip()}\n>>>\n\nIt replied to this question:\n{question}\n\n"
            f"Claim: {statement}\n\nReply NA, NO or YES.")


def classify_user(instruction: str, statement: str, more_often: bool) -> str:
    way = "MORE often" if more_often else "LESS often"
    return (f"Instruction:\n{instruction.strip()}\n\n"
            f"Observed change: with this instruction, answers are {way} like this:\n{statement}")


def version() -> str:
    """Hash of every prompt, recorded in the bundle so a rerun can tell if prompts changed."""
    blob = "\n".join([INTENDED_SYSTEM, PROPOSE_SYSTEM, JUDGE_SYSTEM, JUDGE_ALT_SYSTEM, CLASSIFY_SYSTEM,
                      judge_user("s", "q", "a"), judge_alt_user("s", "q", "a"), classify_user("i", "s", True),
                      labelled("A", "x"), propose_user([("q", "a", "b")])])
    return hashlib.sha256(blob.encode()).hexdigest()[:12]


# ---------------------------------------------------------------------------
# Parsers
# ---------------------------------------------------------------------------

_VERDICT = re.compile(r"\b(YES|NO|N/?A)\b", re.I)
_BULLET = re.compile(r"^\s*(?:[-*•]|\d{1,2}[.)])\s+(.*\S)\s*$")
# references to the other side or to the comparison: not checkable on a single answer
_COMPARATIVE = re.compile(r"\b(?:group|pair|answer [AB]\b|response [AB]\b|other answer|first answer|second answer|"
                          r"both answers|compared|than the other|whereas)\b", re.I)


def parse_verdict(text: str | None) -> str | None:
    """'yes', 'no', 'na', or None when unreadable. Reads the last non-empty line; both or neither = None."""
    if not text:
        return None
    lines = [ln for ln in str(text).strip().splitlines() if ln.strip()]
    if not lines:
        return None
    found = {m.group(1).upper().replace("/", "") for m in _VERDICT.finditer(lines[-1])}
    if len(found) == 1:
        return {"YES": "yes", "NO": "no", "NA": "na"}[found.pop()]
    return None


def parse_statements(text: str | None, limit: int) -> list[str]:
    """Bulleted single-answer statements, cleaned. Comparative or malformed lines are dropped."""
    out: list[str] = []
    for ln in str(text or "").splitlines():
        m = _BULLET.match(ln)
        if not m:
            continue
        s = m.group(1).strip().strip('"“”*` ').strip()
        if not s or _COMPARATIVE.search(s):
            continue
        words = len(s.split())
        if words < 3 or words > 40:
            continue
        if not re.match(r"(?:the answer|if\b)", s, re.I):
            continue
        if not s.endswith((".", "?", "!")):
            s += "."
        out.append(s[0].upper() + s[1:])
        if len(out) >= limit:
            break
    return out


def parse_classification(text: str | None) -> str | None:
    if not text:
        return None
    lines = [ln for ln in str(text).strip().splitlines() if ln.strip()]
    if not lines:
        return None
    found = set(re.findall(r"\b(INTENDED|SIDE[_ ]EFFECT)\b", lines[-1], re.I))
    found = {f.upper().replace(" ", "_") for f in found}
    if len(found) == 1:
        return {"INTENDED": "intended", "SIDE_EFFECT": "side_effect"}[found.pop()]
    return None


# ---------------------------------------------------------------------------
# Near-duplicate statements
# ---------------------------------------------------------------------------

_STOP = {"the", "answer", "a", "an", "of", "to", "and", "or", "is", "are", "it", "its", "in", "on", "for",
         "with", "that", "this", "at", "least", "one", "user", "user's", "contains", "includes", "uses", "has"}


def _tokens(s: str) -> set[str]:
    return {w.rstrip("s") for w in re.findall(r"[a-z']+", s.lower()) if w not in _STOP}


def similar(a: str, b: str, threshold: float = 0.6) -> bool:
    ta, tb = _tokens(a), _tokens(b)
    if not ta or not tb:
        return a.strip().lower() == b.strip().lower()
    return len(ta & tb) / len(ta | tb) >= threshold


def dedupe(statements: list[str], against: list[str] = ()) -> list[str]:
    out: list[str] = []
    for s in statements:
        if any(similar(s, t) for t in [*against, *out]):
            continue
        out.append(s)
    return out
