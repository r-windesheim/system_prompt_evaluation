"""Prompts and output parsers for the discovery stage (spet/discovery.py).

Written for a small reasoning model (gpt-oss-20b on vLLM): short instructions and a
strict, minimal output format. Parsers are defensive. Output they cannot read is
reported as unreadable (None), never guessed as "no".
"""

from __future__ import annotations

import hashlib
import re

# The proposer prompts as they were before labels (schema 8). Kept only so bundles made with them still match the
# judge check (``version_before_labels``); never sent.
_INTENDED_V8 = """You turn one instruction from a system prompt into checks.
Write up to {n} short statements about a single assistant answer that would be true if the assistant followed the instruction.
Each statement must be checkable with yes or no by reading one answer and the user's question.
Start each statement with "The answer". If the instruction only applies in some situations, say so, e.g. "If the user reports a problem, the answer apologises."
Output only the statements, one per line, each starting with "- "."""
_PROPOSE_V8 = """You compare pairs of assistant answers. In each pair both answers reply to the same user question.
One answer in each pair comes from group A, the other from group B. The two groups differ in one hidden way.
Find differences that recur across several pairs: things that appear in one group's answers much more often than in the other's.
Write up to {n} statements, each about a single answer and checkable with yes or no by reading that one answer.
Start each statement with "The answer". Do not mention groups, pairs, or the other answer, and do not compare.
Output only the statements, one per line, each starting with "- "."""

# A label: what a viewer shows for a statement. It continues "The model ..." (rules in ``label_problem``).
LABEL_RULES = """A label is a verb phrase of at most eight words that continues the sentence "The model ...", for example "says it cannot open the link" or "does not start with an apology".
Start it with a verb such as "says", "asks", "uses", "keeps", "avoids", or with "does not". Do not write "the answer" and do not quote more than five words. No full stop."""

# 1a. Intended behaviour, from the instruction text alone. Each statement comes with its label (v9).
INTENDED_SYSTEM = _INTENDED_V8.replace(
    'Output only the statements, one per line, each starting with "- ".',
    'After each statement write " || " and a label for the behaviour the instruction asks for.\n' + LABEL_RULES + '\n'
    'Output only the statements, one per line, each starting with "- ", e.g. "- The answer says it cannot open links. || says it cannot open links".')

# 1b. Discovered differences, from paired answers. The instruction is NOT shown.
PROPOSE_SYSTEM = _PROPOSE_V8.replace(
    'Output only the statements, one per line, each starting with "- ".',
    'After each statement write " || " and a label for the behaviour it describes.\n' + LABEL_RULES + '\n'
    'Output only the statements, one per line, each starting with "- ", e.g. "- The answer ends with a question. || ends with a question".')

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

# 5. A label for a statement that has none (``spet label``): one short call per statement.
LABEL_SYSTEM = """You write a short label for a check on an assistant's answers.
""" + LABEL_RULES + """
The label must mean exactly what the check means: the same behaviour and the same condition, in plain words a first-time reader understands. Add nothing that is not in the check.
Keep the check's key words. To fit the word limit, leave out examples and lists, never the behaviour itself, and never end in the middle of a phrase.
Reply with the label only, on one line."""

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


def label_user(statement: str, reverse: bool = False) -> str:
    """For ``spet label``. Only the check is shown, never the instruction, so the label cannot drift to another part
    of the instruction. ``reverse``: the part asks for the opposite of the check, so the label is its negation (the
    compliant behaviour), written with "does not"."""
    how = ('Label the OPPOSITE of this check: start with "does not" and keep the rest of the check\'s meaning, e.g. '
           '"The answer starts with an apology." becomes "does not start with an apology".'
           if reverse else "Label exactly the behaviour this check describes.")
    return f"Check: {statement.strip()}\n\n{how}\nReply with the label only."


def classify_user(instruction: str, statement: str, more_often: bool) -> str:
    way = "MORE often" if more_often else "LESS often"
    return (f"Instruction:\n{instruction.strip()}\n\n"
            f"Observed change: with this instruction, answers are {way} like this:\n{statement}")


def _hash(intended: str, propose: str) -> str:
    blob = "\n".join([intended, propose, JUDGE_SYSTEM, JUDGE_ALT_SYSTEM, CLASSIFY_SYSTEM,
                      judge_user("s", "q", "a"), judge_alt_user("s", "q", "a"), classify_user("i", "s", True),
                      labelled("A", "x"), propose_user([("q", "a", "b")])])
    return hashlib.sha256(blob.encode()).hexdigest()[:12]


def version() -> str:
    """Hash of every discovery prompt, recorded in the bundle so a rerun can tell if prompts changed."""
    return _hash(INTENDED_SYSTEM, PROPOSE_SYSTEM)


def version_before_labels() -> str:
    """``version()`` as it was before the proposer prompts asked for labels (schema 8 and earlier). The judge prompts
    are the same, so a bundle recorded with this hash was judged exactly as the current judge would judge it."""
    return _hash(_INTENDED_V8, _PROPOSE_V8)


def judge_version() -> str:
    """Hash of the judge's prompts only (v9): what must match when a later stage judges more answers for a run."""
    blob = "\n".join([JUDGE_SYSTEM, JUDGE_ALT_SYSTEM, judge_user("s", "q", "a"), judge_alt_user("s", "q", "a")])
    return hashlib.sha256(blob.encode()).hexdigest()[:12]


def label_version() -> str:
    return hashlib.sha256((LABEL_SYSTEM + label_user("s", True) + label_user("s")).encode()).hexdigest()[:12]


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
    return [s for s, _ in parse_labelled(text, limit)]


def parse_labelled(text: str | None, limit: int) -> list[tuple[str, str | None]]:
    """Like ``parse_statements``, with each statement's label ("statement || label"); the label is None when missing
    or when it breaks the label rules (``label_problem``)."""
    out: list[tuple[str, str | None]] = []
    for ln in str(text or "").splitlines():
        m = _BULLET.match(ln)
        if not m:
            continue
        body, _, lab = m.group(1).partition("||")
        label = clean_label(lab) if lab.strip() else None
        if label is not None and label_problem(label):
            label = None
        s = body.strip().strip('"“”*` ').strip()
        if not s or _COMPARATIVE.search(s):
            continue
        words = len(s.split())
        if words < 3 or words > 40:
            continue
        if not re.match(r"(?:the answer|if\b)", s, re.I):
            continue
        if not s.endswith((".", "?", "!")):
            s += "."
        out.append((s[0].upper() + s[1:], label))
        if len(out) >= limit:
            break
    return out


# ---------------------------------------------------------------------------
# Labels
# ---------------------------------------------------------------------------

LABEL_MAX_WORDS = 8
_QUOTED = re.compile(r'[“"]([^”"]*)[”"]|‘([^’]*)’')
_NOT_VERB = {"its", "this", "thus", "his", "us", "yes", "less", "unless", "always", "is", "was", "as"}


def clean_label(text: str | None) -> str:
    """The model's reply as a label: last non-empty line, no bullet, no "The model", no full stop, lower-case start."""
    lines = [ln.strip() for ln in str(text or "").splitlines() if ln.strip()]
    t = lines[-1] if lines else ""
    t = re.sub(r"^(?:[-*•]\s+|label:\s*)", "", t, flags=re.I).strip().strip("*`").strip()
    if len(t) > 1 and t[0] in "\"“'‘" and t[-1] in "\"”'’" and not _QUOTED.fullmatch(t[1:-1] or "x"):
        t = t[1:-1].strip()
    t = re.sub(r"^the model\s+", "", t, flags=re.I).rstrip(" .;:")
    return t[:1].lower() + t[1:] if t else t


def label_problem(label: str) -> str | None:
    """Why a label breaks the rules, or None if it is fine. Checked mechanically, the same for every run."""
    words = label.split()
    if not words:
        return "empty"
    if len(words) > LABEL_MAX_WORDS:
        return f"more than {LABEL_MAX_WORDS} words"
    if re.search(r"\b(?:the|this|an?)\s+(?:answer|response)\b", label, re.I):
        return 'says "the answer"'
    first = words[0].lower()
    if not (re.match(r"(?:does\s+not|doesn['’]t)\b", label, re.I) or
            (first.endswith("s") and first.isalpha() and first not in _NOT_VERB) or first in ("is", "has", "does")):
        return "does not start with a verb such as \"says\" or \"does not\""
    for m in _QUOTED.finditer(label):
        if len((m.group(1) or m.group(2) or "").split()) > 5:
            return "quotes more than five words"
    if label.endswith("."):
        return "ends with a full stop"
    return None


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
