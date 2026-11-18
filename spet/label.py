"""Labels for statements that lack one (``spet label``): one short judge call per statement used in the readout.

A label is what a viewer shows for a statement: a verb phrase that continues "The model ..." and names the behaviour
the part asks for (for a reverse-coded statement, the compliant behaviour), e.g. "says it cannot open the link".
Runs from schema 9 on get labels when their statements are written (spet/prompts.py, INTENDED_SYSTEM and
PROPOSE_SYSTEM; author files may carry one). This command fills them in for older bundles.

Each reply is checked mechanically (``prompts.label_problem``: at most eight words, starts with a verb form, never
"the answer", no quote of more than five words). A label that fails is asked for once more, with the reason; if it
fails again the statement keeps no label and a viewer shows the statement text. Labels never enter a test or a reading.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable

from . import prompts
from .bundle import SCHEMA_VERSION, RunBundle, Statement


def targets(b: RunBundle) -> list[str]:
    """Statement ids the readout uses (its checks, then its side effects), in order, each once."""
    out: list[str] = []
    for p in (b.readout.parts if b.readout else []):
        for sid in [c.id for c in p.checks] + list(p.side_effects):
            if sid not in out:
                out.append(sid)
    return out


def _statements(b: RunBundle) -> list[Statement]:
    """Every statement object in the bundle (the same id can appear in discovery and in the confirmation)."""
    out: list[Statement] = []
    if b.discovery:
        out += b.discovery.statements
    if b.confirmation:
        out += b.confirmation.candidates
    if b.authored:
        out += b.authored.statements
    return out


async def label_bundle(b: RunBundle, judge, *, force: bool = False, max_calls: int | None = None,
                       progress: Callable[[int, int], None] | None = None) -> tuple[RunBundle, dict]:
    """Return a copy of ``b`` with labels on the statements the readout uses, and a report:
    ``{"calls": n, "labels": {id: label or None}, "failed": {id: reason}, "skipped": [ids over budget]}``."""
    out = b.model_copy(deep=True)
    by_id: dict[str, list[Statement]] = {}
    for st in _statements(out):
        by_id.setdefault(st.id, []).append(st)
    todo = [sid for sid in targets(out) if sid in by_id and (force or not by_id[sid][0].label)]
    calls = 0
    report: dict = {"labels": {}, "failed": {}, "skipped": []}
    lock = asyncio.Lock()

    async def ask(user: str, seed: int) -> str | None:
        nonlocal calls
        async with lock:
            if max_calls is not None and calls >= max_calls:
                return None
            calls += 1
        try:
            return await judge.complete(prompts.LABEL_SYSTEM, user, temperature=0.0, seed=seed)
        except Exception:
            return None

    async def one(sid: str) -> None:
        st = by_id[sid][0]
        user = prompts.label_user(st.text, reverse=st.polarity == "reverse")
        reply = await ask(user, 0)
        if reply is None:
            report["skipped"].append(sid)
            return
        label = prompts.clean_label(reply)
        why = prompts.label_problem(label)
        if why:  # once more, saying what was wrong
            retry = await ask(f"{user}\n\nYour previous label was {label!r}, which breaks a rule: {why}. "
                              "Write a new label that follows every rule.", 1)
            if retry is not None:
                label = prompts.clean_label(retry)
                why = prompts.label_problem(label)
        if why:
            report["failed"][sid] = f"{label!r}: {why}"
            label = None
        report["labels"][sid] = label
        for s in by_id[sid]:
            s.label = label
        if progress:
            progress(len(report["labels"]) + len(report["skipped"]), len(todo))

    await asyncio.gather(*(one(sid) for sid in todo))
    report["calls"] = calls
    if out.readout:
        labels = {sid: by_id[sid][0].label for sid in by_id}
        for p in out.readout.parts:
            for c in p.checks:
                c.label = labels.get(c.id)
    js = getattr(judge, "settings", {}) or {}
    out.meta.settings.update({"label_model": getattr(judge, "model", None), "label_endpoint_host": js.get("endpoint_host"),
                              "label_prompts_version": prompts.label_version()})
    out.schema_version = SCHEMA_VERSION
    return RunBundle.model_validate(out.model_dump()), report
