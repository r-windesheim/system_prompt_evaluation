"""Readout: two facts per intended statement, then one reading per part. Works on a finished bundle; no model calls.

The discovery reading (spet/discovery.py, ``_reading``) asks one label to answer two questions at once, so a part is
"inconclusive" unless the causal question is settled, even where the model plainly does (or does not do) what the
part says. The readout separates them:

1. **Does the model do what the part says?** An estimate: the share of answers WITH the part, on the questions written
   for that part, where the statement holds, with its by-question interval. No comparison and no multiple-testing
   correction. Read as "mostly" (rate >= 0.8), "rarely" (rate <= 0.2) or "sometimes"; "unclear" if the interval
   reaches both 0.2 and 0.8.
2. **Is the part the reason?** The causal claim. "confirmed" only if the confirmation run confirmed the statement;
   "not_needed" if it is mostly done both with and without the part (both rates >= 0.8); otherwise "not_shown".

A statement's numbers come from the confirmation run when it was retested there (more samples, fresh questions), else
from the main run (targeted questions only). Intended statements are read, and so are author-written ones (the
bundle's ``authored`` block, v8), on the main run's answers. A statement is left out if an audit marks it invalid, or if
it carries a flag in ``EXCLUDED`` in the run its numbers come from. A reverse-coded authored statement describes what
the part asks the model not to do, so its rates are read as 1 - the share judged yes.

Per part, from its usable checks, in this order:

- unclear: no usable check, or every check is "unclear";
- followed: every check "mostly", at least one "confirmed";
- not_needed: every check "mostly" and "not_needed";
- does_it: every check "mostly", the cause not shown (the model does this; the part was not shown to be the reason);
- not_followed: every check "rarely";
- partly_followed: anything else (a mix, including "sometimes" and a mix with "unclear").

Only "followed" carries a causal claim. See docs/discovery.md, "Two questions".
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path

import yaml

from .bundle import (SCHEMA_VERSION, AnnotationsRecord, AuditRecord, Check, ExcludedCheck, PartReadout, Readout,
                     ReadoutRule, RunBundle, Statement)
from .discovery import DiscoveryOptions
from .prompts import label_problem

MOSTLY = DiscoveryOptions().redundant_rate  # 0.8: the engine's existing "the behaviour is there" rate
RARELY = 0.2
# judge or data problems that make a rate untrustworthy. "ceiling" and "never_seen" are NOT here: a behaviour that
# always or never happens is exactly what question 1 measures.
EXCLUDED = ("judge_unreliable", "judge_unchecked", "unparseable", "exclusion_asymmetry", "few_pairs")

ONE_CLASS_NOTE = ("The judge gave the same verdict to every re-judged answer, so whether it could say the opposite "
                  "was not tested.")
NOTES = {
    "followed": "Answers do this with the part, and the confirmation run showed the part is the reason.",
    "not_needed": "Answers do this with and without the part: the part is not needed for it.",
    "does_it": "Answers do this with the part, but the part was not shown to be the reason.",
    "not_followed": "Even with the part, answers rarely do this.",
    "partly_followed": "Answers do some of this, or do it only some of the time.",
    "unclear": "The checks are too uncertain to say whether answers do this.",
}


def rule() -> ReadoutRule:
    return ReadoutRule(mostly_at=MOSTLY, rarely_at=RARELY, excluded_flags=list(EXCLUDED))


def does(rate: float, ci: tuple[float, float] | None) -> str:
    """Question 1 for one statement. The interval is checked first: one reaching both bounds says nothing."""
    lo, hi = ci if ci is not None else (rate, rate)
    if lo <= RARELY and hi >= MOSTLY:
        return "unclear"
    if rate >= MOSTLY:
        return "mostly"
    if rate <= RARELY:
        return "rarely"
    return "sometimes"


def cause(confirmed: bool, rate_with: float, rate_without: float) -> str:
    """Question 2 for one statement. Only the confirmation run can say "confirmed"."""
    if confirmed:
        return "confirmed"
    if rate_with >= MOSTLY and rate_without >= MOSTLY:
        return "not_needed"
    return "not_shown"


def part_reading(checks: list[Check]) -> str:
    d = {c.does for c in checks}
    if not checks or d == {"unclear"}:
        return "unclear"
    if d == {"mostly"}:
        if any(c.cause == "confirmed" for c in checks):
            return "followed"
        if all(c.cause == "not_needed" for c in checks):
            return "not_needed"
        return "does_it"
    if d == {"rarely"}:
        return "not_followed"
    return "partly_followed"


# ---- audit ------------------------------------------------------------------------------------------------

def load_audit(path: str | Path, b: RunBundle) -> tuple[dict[str, tuple[bool, str]], AuditRecord]:
    """Read an audit YAML: ``reviewer``, ``date`` and ``statements: {id: {valid, reason, ...}}``. It must cover every
    intended statement of the bundle and name no other. If the bundle has authored statements (v8), the audit also
    needs ``authored_statements: {id: {valid, reason, ...}}`` covering exactly those."""
    path = Path(path)
    data = path.read_bytes()
    raw = yaml.safe_load(data) or {}
    sts = raw.get("statements") or {}
    if not isinstance(sts, dict):
        raise ValueError(f"{path.name}: `statements` must map statement ids to entries")
    intended = {s.id for s in b.discovery.statements if s.source == "intended"}
    unknown, missing = set(sts) - intended, intended - set(sts)
    if unknown:
        raise ValueError(f"{path.name}: not intended statements of this bundle: {', '.join(sorted(unknown))}")
    if missing:
        raise ValueError(f"{path.name}: no audit entry for {', '.join(sorted(missing))}")
    auth_ids = {s.id for s in b.authored.statements} if b.authored else set()
    auth = raw.get("authored_statements") or {}
    if not isinstance(auth, dict):
        raise ValueError(f"{path.name}: `authored_statements` must map statement ids to entries")
    unknown, missing = set(auth) - auth_ids, auth_ids - set(auth)
    if unknown:
        raise ValueError(f"{path.name}: not authored statements of this bundle: {', '.join(sorted(unknown))}")
    if missing:
        raise ValueError(f"{path.name}: no audit entry for authored {', '.join(sorted(missing))}")
    out = {}
    for sid, e in {**sts, **auth}.items():
        if not isinstance(e, dict) or not isinstance(e.get("valid"), bool):
            raise ValueError(f"{path.name}: {sid} needs `valid: true|false`")
        out[sid] = (e["valid"], str(e.get("reason", "")))
    rec = AuditRecord(file=path.name, sha256=hashlib.sha256(data).hexdigest(), reviewer=str(raw.get("reviewer", "")),
                      date=str(raw.get("date", "")), valid=sorted(k for k, v in out.items() if v[0]),
                      invalid=sorted(k for k, v in out.items() if not v[0]))
    return out, rec


# ---- annotations: an author's notes on checks (v9) ------------------------------------------------------------

NOTE_MAX_CHARS = 200
DESCRIPTION_MAX_CHARS = 300


def load_annotations(path: str | Path, b: RunBundle) -> tuple[dict[str, str], AnnotationsRecord]:
    """Read an annotations YAML: ``author``, ``date``, ``notes: {statement id: note}``, ``labels: {statement id:
    label}`` and ``description``. A note is shown beside a check's example answers, marked as a note; it is never a
    measurement. A label replaces the generated one on that check (``Check.label_source`` "author") and follows the
    same rules (``prompts.label_problem``). The description is one line on what the run is, shown under the headline.
    Every id must be a statement of the bundle. Labels and description are kept in the returned record."""
    path = Path(path)
    data = path.read_bytes()
    raw = yaml.safe_load(data) or {}
    notes = raw.get("notes") or {}
    labels = raw.get("labels") or {}
    for key, m in (("notes", notes), ("labels", labels)):
        if not isinstance(m, dict):
            raise ValueError(f"{path.name}: `{key}` must map statement ids to text")
    known = {s.id for s in b.discovery.statements} if b.discovery else set()
    known |= {s.id for s in b.authored.statements} if b.authored else set()
    unknown = (set(notes) | set(labels)) - known
    if unknown:
        raise ValueError(f"{path.name}: not statements of this bundle: {', '.join(sorted(unknown))}")
    out = {}
    for sid, text in notes.items():
        t = " ".join(str(text or "").split())
        if not t or len(t) > NOTE_MAX_CHARS:
            raise ValueError(f"{path.name}: the note for {sid} must be 1 to {NOTE_MAX_CHARS} characters")
        out[sid] = t
    lab = {}
    for sid, text in labels.items():
        t = " ".join(str(text or "").split())
        why = label_problem(t)
        if why:
            raise ValueError(f"{path.name}: the label for {sid} breaks the label rules: {why}")
        lab[sid] = t
    desc = raw.get("description")
    if desc is not None:
        desc = " ".join(str(desc).split())
        if not desc or len(desc) > DESCRIPTION_MAX_CHARS:
            raise ValueError(f"{path.name}: the description must be 1 to {DESCRIPTION_MAX_CHARS} characters")
    rec = AnnotationsRecord(file=path.name, sha256=hashlib.sha256(data).hexdigest(), author=str(raw.get("author", "")),
                            date=str(raw.get("date", "")), labels=lab, description=desc)
    return out, rec


# ---- the readout ------------------------------------------------------------------------------------------

REVERSE_NOTE = "Reverse-coded: the statement says what the part asks the model not to do; the rate is 1 - the share judged yes."
MEASURE_NOTE = "Decided by the engine's {m}, not by the judge."


def _check(st: Statement, data: str, confirmed: bool, label: str | None = None, author_note: str | None = None) -> Check:
    rate_w, rate_o, ci = st.full_rate, st.ablated_rate, st.full_rate_ci
    rev = st.polarity == "reverse"
    if rev:  # read compliance the right way round: the share of answers that do NOT do what the statement says
        rate_w, rate_o = 1 - rate_w, 1 - rate_o
        ci = (1 - ci[1], 1 - ci[0]) if ci is not None else None
    notes = []
    if rev:
        notes.append(REVERSE_NOTE)
    if st.measure:
        notes.append(MEASURE_NOTE.format(m=st.measure))
    if "rejudge_one_class" in st.flags:
        notes.append(ONE_CLASS_NOTE)
    if "untargeted" in st.flags:
        notes.append("No question targets this part, so the rate counts questions where it may not apply.")
    return Check(id=st.id, text=st.text, data=data, rate_with=rate_w, rate_with_ci=ci,
                 rate_without=rate_o, n_questions=st.n_questions, n_answers=st.n_pairs,
                 does=does(rate_w, ci), cause=cause(confirmed, rate_w, rate_o), flags=list(st.flags),
                 note=" ".join(notes), polarity=st.polarity, rate_with_raw=st.full_rate,
                 label=st.label or label, author_note=author_note)


def readout(b: RunBundle, audit: dict[str, tuple[bool, str]] | None = None,
            audit_record: AuditRecord | None = None, annotations: dict[str, str] | None = None,
            annotations_record: AnnotationsRecord | None = None) -> RunBundle:
    """Return a copy of ``b`` with a ``readout`` block. ``audit`` maps statement id -> (valid, reason);
    ``annotations`` maps statement id -> an author's note for that check (``load_annotations``); the labels in
    ``annotations_record`` replace the generated ones on their checks."""
    annotations = annotations or {}
    author_labels = annotations_record.labels if annotations_record else {}
    if not b.discovery:
        raise ValueError("the bundle has no discovery block to read")
    cands = {c.id: c for c in b.confirmation.candidates if c.source == "intended"} if b.confirmation else {}
    earlier = {r.section: r for r in b.discovery.readings}
    conf_rd = {r.section: r for r in b.confirmation.readings} if b.confirmation else {}
    parts = sorted({c.removed for c in b.configs if c.removed is not None} & {s.id for s in b.sections})
    authored = list(b.authored.statements) if b.authored else []
    out_parts = []
    for k in parts:
        checks, excluded = [], []
        mine = [s for s in b.discovery.statements if s.section == k and s.source == "intended"]
        mine += [s for s in authored if s.section == k]
        for st in mine:
            if audit is not None and not audit[st.id][0]:
                excluded.append(ExcludedCheck(id=st.id, text=st.text, reason="audit: " + audit[st.id][1]))
                continue
            src = cands.get(st.id) if st.source == "intended" else None
            use, data = (src, "confirmation") if src is not None else (st, "authored" if st.source == "authored" else "screen")
            bad = [f for f in EXCLUDED if f in use.flags]
            if bad:
                where = {"confirmation": "in the confirmation run", "screen": "in the main run",
                         "authored": "when judged as an authored statement"}[data]
                excluded.append(ExcludedCheck(id=st.id, text=st.text, reason=f"flag {where}: " + ", ".join(bad)))
                continue
            c = _check(use, data, bool(src is not None and src.confirmed), label=st.label,
                       author_note=annotations.get(st.id))
            if st.id in author_labels:  # last, so it wins over the statement's and the candidate's label
                c.label, c.label_source = author_labels[st.id], "author"
            checks.append(c)
        reading = part_reading(checks)
        note = NOTES[reading]
        if not checks:
            note = "No usable check: " + ("every intended statement was left out." if excluded else
                                          "the part has no intended statement.")
        elif reading in ("does_it", "not_needed", "not_followed") and all("rejudge_one_class" in c.flags for c in checks):
            note += " " + ONE_CLASS_NOTE
        prev = conf_rd.get(k) or earlier.get(k)
        out_parts.append(PartReadout(
            section=k, reading=reading, adherence=prev.adherence if prev else "not_assessed",
            adherence_basis=getattr(prev, "basis", "screen") if k in conf_rd else "screen",
            checks=checks, excluded=excluded, side_effects=list(prev.side_effects) if prev else [], note=note))
    out = b.model_copy(deep=True)
    out.schema_version = SCHEMA_VERSION
    out.readout = Readout(created_at=datetime.now(timezone.utc).isoformat(timespec="seconds"), rule=rule(),
                          audit=audit_record, parts=out_parts, annotations=annotations_record)
    return RunBundle.model_validate(out.model_dump())
