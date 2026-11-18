"""Run bundle: the single JSON contract between the engine and the viewer.

A bundle holds everything needed to render a run statically: the full section
texts, every raw response for every configuration, detector spans, and the
per-(detector, section) effects with uncertainty.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

SCHEMA_VERSION = 8  # 3: optional `discovery` block (spet/discovery.py, docs/discovery.md)
# 4: question targets and per-target sample counts (meta), per_query_idx, prompt-echo exclusions (all optional)
# 5: discovery q-values come from two Benjamini-Hochberg families (intended, discovered) instead of one; per-answer
#    judge verdicts; the attention screen record. All new fields are optional, so v1-v4 bundles still load.
# 6: optional `confirmation` block: screen candidates chosen by a fixed rule, retested on fresh questions with their
#    own answers (spet/confirm.py). Optional, so v1-v5 bundles still load.
# 7: optional `readout` block: per intended statement, whether the model does it (an estimate) and whether the part
#    was shown to be the reason (the confirmation), and one reading per part from those (spet/readout.py). Optional,
#    so v1-v6 bundles still load.
# 8: optional `authored` block: statements written by a reviewer from the instruction text, judged on the run's stored
#    answers (spet/authored.py); `Statement.source` may be "authored", with `polarity` and `measure`; the readout's
#    `Check` gains `data: "authored"`, `polarity` and `rate_with_raw`. Optional, so v1-v7 bundles still load.


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Meta(_Strict):
    id: str
    title: str
    created_at: str
    model: str
    provider: str
    temperature: float
    n_per_query: int = Field(ge=1)
    seed: int
    queries: list[str]
    fixture: bool = False
    notes: str = ""
    # everything needed to rerun: max_tokens, reasoning_effort, endpoint host, model revision,
    # vLLM version, detector version, run date (methodology review, problem 17)
    settings: dict[str, str | int | float | None] = {}
    # v4: which parts (section ids) each question was written for; None = not given. A question may target none.
    query_targets: list[list[int]] | None = None
    # v4: samples per question in a config where the question does NOT target the removed part (and in `full` for
    # questions that target no part). None = n_per_query everywhere. n_per_query is then the targeted count.
    n_per_query_untargeted: int | None = Field(default=None, ge=1)


class Section(_Strict):
    id: int
    label: str
    text: str
    notes: list[str] = []  # e.g. "never tested: no answer came within 80% of the 200-word limit"


class Config(_Strict):
    id: str
    removed: int | None = None


class Span(_Strict):
    start: int = Field(ge=0)
    end: int
    detector: str


class Response(_Strict):
    config: str
    query_idx: int = Field(ge=0)
    sample_idx: int = Field(ge=0)
    text: str
    spans: list[Span] = []
    finish_reason: str | None = None  # "length" means the answer was cut off


class Detector(_Strict):
    id: str
    label: str
    group: str
    description: str = ""
    kind: Literal["habit", "metric"] = "habit"
    unit: str = "per response"
    precision: float | None = None
    precision_n: int | None = None
    precision_model: str | None = None  # which model's answers the precision was measured on


class Effect(_Strict):
    detector: str
    section: int
    full_mean: float
    ablated_mean: float
    delta: float  # full_mean - ablated_mean: >0 means the section increases the quirk
    ci: tuple[float, float]
    p: float = Field(ge=0, le=1)
    q: float = Field(ge=0, le=1)
    significant: bool
    n_pairs: int
    tested: bool = True
    ci_query: tuple[float, float] | None = None
    per_query: list[float] = []
    # question index of each per_query entry; questions without a usable pair are absent, so per_query is NOT
    # indexed by question. Empty in bundles before v4 (there, per_query skips such questions without saying which).
    per_query_idx: list[int] = []
    mde: float | None = None
    # "in_lists": mostly sits inside bullet lists; "length_shift": the section also changes answer length;
    # "context_shift": the section sets identity/audience; "not_testable": floor/ceiling or never exercised
    flags: list[str] = []


class Analysis(_Strict):
    n_tests: int
    alpha: float
    mde_alpha: float
    warnings: list[str] = []


class PairExample(_Strict):
    """One paired cell where the judge said yes on one side and no on the other."""
    query_idx: int = Field(ge=0)
    sample_idx: int = Field(ge=0)
    with_config: str = "full"       # the answer generated with the part
    without_config: str             # the answer generated without it
    with_yes: bool                  # judgment on the with-part answer (the other side is the opposite)


class Statement(_Strict):
    """A yes/no-checkable claim about a single answer, judged on every answer of one part's pair of configs."""
    id: str
    section: int
    text: str
    # intended: from the instruction text (by the judge model); discovered: from paired answers; authored (v8): written
    # by a reviewer from the instruction text, blind to the answers, and judged later (the `authored` block)
    source: Literal["intended", "discovered", "authored"]
    classification: Literal["intended", "side_effect"] | None = None  # None: discovered but not significant
    full_rate: float          # share of judged answers WITH the part where the judge said yes
    ablated_rate: float       # same, WITHOUT the part
    full_rate_ci: tuple[float, float] | None = None  # by question (cluster bootstrap) on the with-part arm
    delta: float              # full_rate - ablated_rate over paired cells
    ci: tuple[float, float]
    ci_query: tuple[float, float] | None = None
    p: float = Field(ge=0, le=1)
    q: float = Field(ge=0, le=1)
    significant: bool
    tested: bool = True       # False when the judge said no on every answer in both arms
    n_pairs: int              # pairs analysed (both sides parsed and applicable)
    n_questions: int
    verified_on: list[int] = []  # query indices the statement was verified on
    per_query: list[float] = []
    per_query_idx: list[int] = []  # question index of each per_query entry (v4; see Effect.per_query_idx)
    mde: float | None = None
    n_unparseable: int = 0    # judgments that could not be read (or failed), excluded with their pair
    n_na: int = 0             # judgments of "does not apply to this question", excluded with their pair
    n_excluded_with: int = 0      # cells dropped because the with-part verdict was NA or unreadable
    n_excluded_without: int = 0   # same, without-part side; a lopsided split is flagged "exclusion_asymmetry"
    n_excluded_echo: int = 0      # cells left out before judging because an answer recites the system prompt (v4)
    agreement: float | None = None  # same verdict under a second, equivalent judge prompt (re-judged sample)
    kappa: float | None = None
    n_rejudged: int = 0
    # blocking (never significant): "judge_unreliable", "judge_unchecked", "unparseable", "exclusion_asymmetry";
    # informative: "rejudge_one_class", "never_seen", "ceiling", "few_pairs", "length_shift", "context_shift",
    # "also_discovered", "unclassified", "untargeted" (intended, but no question targets the part, so it was
    # checked on every question), "too_few_questions" (too few questions for the by-question test to pass the
    # multiple-testing correction on its own)
    flags: list[str] = []
    examples: list[PairExample] = []
    # v5: the Benjamini-Hochberg family the q-value comes from ("intended" or "discovered"). None: a bundle before v5,
    # where every tested statement of the run formed one family.
    family: Literal["intended", "discovered"] | None = None
    # v5: every judged pair, as (query_idx, sample_idx, verdicts). verdicts is two letters, the with-part answer
    # first, then the without-part answer: y = yes, n = no, a = does not apply (NA), u = unreadable or failed.
    # Pairs left out before judging (recited prompts) are not listed.
    verdicts: list[tuple[int, int, str]] = []
    # v5: the re-judged sample, as (query_idx, sample_idx, side, verdict under the second prompt); side is
    # "w" (with-part answer) or "o" (without); compare with the first letter set in `verdicts`.
    rejudged: list[tuple[int, int, Literal["w", "o"], str]] = []
    # v8, authored statements: "reverse" means the statement describes what the part asks the model NOT to do, so
    # compliance is 1 - full_rate (the readout reads it that way round); the rates here are always the share judged yes
    polarity: Literal["positive", "reverse"] = "positive"
    # v8, authored statements: decided by an engine metric instead of the judge, e.g. "words <= 60"; None = judged
    measure: str | None = None


Adherence = Literal["followed", "partly_followed", "redundant", "not_followed", "inconclusive", "not_assessed"]


class PartReading(_Strict):
    """What the verified statements say about one part, derived mechanically from them."""
    section: int
    # followed: an intended statement is confirmed; partly_followed: some confirmed, some not;
    # redundant: the intended behaviour is there with AND without the part; not_followed: it is rarely there
    # even with the part; inconclusive: none of these; not_assessed: no usable intended statement
    # (v7: see `readout` for a reading that separates "does the model do it" from "is the part the reason")
    adherence: Adherence
    confirmed: list[str] = []      # intended statement ids that are significant with delta > 0
    side_effects: list[str] = []   # significant statements classified "side_effect"
    note: str = ""


class ScreenPick(_Strict):
    """One pair the attention screen put in front of the proposer."""
    section: int
    query_idx: int = Field(ge=0)
    sample_idx: int = Field(ge=0)
    lift: float | None = None   # the screen's lift for (section, question); None: the screen had no value
    call: int = 0               # which proposer call showed it


class ScreenUse(_Strict):
    """v5: discovery ordered the proposer's pairs by an attention screen (scripts: deploy/modal_attention.py)."""
    file: str                    # file name as given
    sha256: str                  # of the screen file
    block: Literal["reasoning", "answer"]  # which tokens' lift the order used
    model: str | None = None
    n_samples: int | None = None  # screen generations per question
    fingerprint: str             # hash of the section and question texts it was made for (must match the run)
    picked: list[ScreenPick] = []


class Discovery(_Strict):
    n_tests: int                   # tested statements in all BH families together
    n_statements: int
    n_unreliable: int = 0
    alpha: float
    discovery_queries: list[int]   # discovered statements were proposed from these questions only...
    holdout_queries: list[int]     # ...and verified only on these
    statements: list[Statement] = []
    readings: list[PartReading] = []
    calls: dict[str, int] = {}     # model calls by kind: intended, propose, judge, rejudge, classify
    n_unparseable: int = 0
    n_errors: int = 0
    # v4: answers that largely recite their own system prompt, as (config, query_idx, sample_idx). They are left
    # out of intended checks (whole pair), because a recited instruction looks like a followed one.
    prompt_echoes: list[tuple[str, int, int]] = []
    test: Literal["cell", "question"] = "cell"  # unit of the sign-flip test and bootstrap; v3 bundles used "cell"
    # v5: tested statements per Benjamini-Hochberg family. Empty before v5 (one family of n_tests).
    families: dict[str, int] = {}
    screen: ScreenUse | None = None  # v5: set when an attention screen ordered the proposer's pairs


class ConfirmRule(_Strict):
    """v6: how the candidates were chosen from the screen and when one counts as confirmed. Fixed in code
    (spet/confirm.py) before any confirmation answer exists, and stored so the choice can be checked."""
    intended_p_below: float        # intended statements with screen p below this...
    discovered_p_below: float      # ...and discovered statements with screen p below this
    require_tested: bool = True
    excluded_flags: list[str] = []  # a statement with any of these screen flags is not a candidate
    test: Literal["question"] = "question"  # sign flips over whole questions, two-sided
    two_sided: bool = True
    confirmed_if: str = ""         # the confirmation criterion in words


class ConfirmQuery(_Strict):
    text: str
    targets: list[int] = []        # the part it was written for; [] = a general question (side-effect checks)
    overlap: float = 0.0           # largest word overlap (Jaccard) with any question of the screen


class Candidate(Statement):
    """v6: a screen statement retested on the confirmation's fresh questions. The Statement fields hold the
    confirmation's numbers (verified_on, per_query_idx, verdicts and examples index confirmation.queries and
    confirmation.responses); the screen_* fields copy the screen's, for comparison."""
    screen_p: float = Field(ge=0, le=1)
    screen_q: float = Field(ge=0, le=1)
    screen_full_rate: float
    screen_ablated_rate: float
    screen_delta: float
    screen_n_questions: int
    confirmed: bool                # q < alpha in its family, no blocking flag, and the same sign as in the screen


class ConfirmReading(_Strict):
    """v6: the per-part reading after confirmation."""
    section: int
    adherence: Literal["followed", "partly_followed", "redundant", "not_followed", "inconclusive", "not_assessed"]
    basis: Literal["confirmation", "screen"]  # screen: no candidate was confirmed, the main run's reading stands
    confirmed: list[str] = []      # candidate ids (intended) confirmed on fresh questions
    not_confirmed: list[str] = []  # candidate ids (intended or discovered) that were retested and failed
    side_effects: list[str] = []   # discovered candidate ids confirmed on fresh questions
    note: str = ""


class Confirmation(_Strict):
    """v6: confirmation of screen candidates on fresh questions (docs/discovery.md, "Confirmation")."""
    id: str
    created_at: str
    seed: int                      # sampling seed of the confirmation answers (differs from the run's)
    alpha: float
    rule: ConfirmRule
    n_per_query: int = Field(ge=1)           # samples per targeted question
    n_per_query_general: int = Field(ge=1)   # samples per general question
    queries: list[ConfirmQuery]
    configs: list[str]             # configs answered: full and each candidate part's without_k
    responses: list[Response] = []  # query_idx indexes confirmation.queries
    candidates: list[Candidate] = []
    families: dict[str, int] = {}  # candidates per Benjamini-Hochberg family (m, fixed by the rule)
    n_tests: int = 0
    readings: list[ConfirmReading] = []
    prompt_echoes: list[tuple[str, int, int]] = []
    calls: dict[str, int] = {}
    n_unparseable: int = 0
    n_errors: int = 0
    n_cut_off: int = 0             # answers cut off or empty, left out like in the run
    warnings: list[str] = []
    settings: dict[str, str | int | float | None] = {}


class Check(_Strict):
    """v7: one intended statement, read two ways (docs/discovery.md, "Two questions").

    ``does`` answers "does the model do what the part says?": an estimate from the with-part answers alone, read from
    the rate and its by-question interval. ``cause`` answers "is the part the reason?": only the confirmation run can
    say "confirmed"."""
    id: str                        # statement id (discovery.statements; also a confirmation candidate if data is so)
    text: str
    # which run the numbers below come from; "authored" (v8): the main run's answers, judged with an authored statement
    data: Literal["confirmation", "screen", "authored"]
    # share of judged answers WITH the part that do what the part asks: the share judged yes, or for a reverse-coded
    # statement (polarity "reverse") 1 - that share. rate_with_ci and rate_without are oriented the same way.
    rate_with: float
    rate_with_ci: tuple[float, float] | None = None  # by-question bootstrap interval of rate_with
    rate_without: float            # same, WITHOUT the part (same questions and samples)
    n_questions: int               # questions with at least one judged pair
    n_answers: int                 # judged answers per side (pairs)
    does: Literal["mostly", "sometimes", "rarely", "unclear"]
    cause: Literal["confirmed", "not_needed", "not_shown"]
    flags: list[str] = []          # the statement's flags in the run its numbers come from
    note: str = ""
    polarity: Literal["positive", "reverse"] = "positive"  # v8
    rate_with_raw: float | None = None  # v8: the share judged yes WITH the part, before any reversal


class ExcludedCheck(_Strict):
    """v7: an intended statement left out of the reading, and why."""
    id: str
    text: str
    reason: str                    # "audit: <the audit's reason>" or "flag: <blocking flags>"


class PartReadout(_Strict):
    """v7: one part's reading from its usable checks. Only "followed" carries a causal claim."""
    section: int
    reading: Literal["followed", "not_needed", "does_it", "not_followed", "partly_followed", "unclear"]
    adherence: Adherence           # the earlier reading (confirmation's if any, else discovery's), kept for compatibility
    adherence_basis: Literal["confirmation", "screen"]
    checks: list[Check] = []
    excluded: list[ExcludedCheck] = []
    side_effects: list[str] = []   # side effects of the earlier reading (statement ids), unchanged
    note: str = ""


class ReadoutRule(_Strict):
    """v7: the thresholds and exclusions the readout used (fixed in spet/readout.py)."""
    mostly_at: float               # rate_with >= this: "mostly"
    rarely_at: float               # rate_with <= this: "rarely"; an interval reaching both bounds: "unclear"
    excluded_flags: list[str] = []  # a statement with any of these flags (in its data's run) is not used
    # discovered statements are side-effect checks, not part of the reading; authored statements (v8) are read
    intended_only: bool = True


class AuditRecord(_Strict):
    """v7: the human or AI audit of the intended statements that the readout honoured."""
    file: str
    sha256: str
    reviewer: str
    date: str
    valid: list[str] = []
    invalid: list[str] = []


class Readout(_Strict):
    """v7: two facts per intended statement and one reading per part (spet/readout.py; no model calls)."""
    created_at: str
    rule: ReadoutRule
    audit: AuditRecord | None = None
    parts: list[PartReadout] = []


class Authored(_Strict):
    """v8: author-written statements judged on the run's stored answers (spet/authored.py, docs/discovery.md).

    Estimates for the readout's first question. Not in any Benjamini-Hochberg family and never a confirmation
    candidate: each statement's p is for information only, its q is fixed at 1 and `significant` is false."""
    file: str                      # the statement file, as given
    sha256: str                    # of the statement file
    reviewer: str
    date: str                      # when the statements were written
    created_at: str                # when they were judged
    statements: list[Statement] = []  # source "authored"; verdicts index the run's questions and responses
    calls: dict[str, int] = {}
    n_unparseable: int = 0
    n_errors: int = 0
    warnings: list[str] = []
    settings: dict[str, str | int | float | None] = {}
    note: str = ""


class RunBundle(_Strict):
    schema_version: Literal[1, 2, 3, 4, 5, 6, 7, 8] = SCHEMA_VERSION
    meta: Meta
    sections: list[Section]
    configs: list[Config]
    responses: list[Response]
    detectors: list[Detector]
    effects: list[Effect]
    analysis: Analysis | None = None
    shapley: dict[str, dict[str, float]] | None = None  # detector -> section id -> value
    discovery: Discovery | None = None  # open-ended effects, proposed by a model and verified per answer
    confirmation: Confirmation | None = None  # v6: screen candidates retested on fresh questions
    readout: Readout | None = None  # v7: per-statement facts and per-part readings from discovery and confirmation
    authored: Authored | None = None  # v8: author-written statements judged on the stored answers

    @model_validator(mode="after")
    def _check_refs(self) -> "RunBundle":
        section_ids = {s.id for s in self.sections}
        config_ids = {c.id for c in self.configs}
        detector_ids = {d.id for d in self.detectors}
        if self.meta.query_targets is not None:
            if len(self.meta.query_targets) != len(self.meta.queries):
                raise ValueError("meta.query_targets must have one entry per query")
            if not {k for t in self.meta.query_targets for k in t} <= section_ids:
                raise ValueError("meta.query_targets references an unknown section")
        if "full" not in config_ids:
            raise ValueError("configs must include 'full'")
        for c in self.configs:
            if c.removed is not None and c.removed not in section_ids:
                raise ValueError(f"config {c.id} removes unknown section {c.removed}")
        for r in self.responses:
            if r.config not in config_ids:
                raise ValueError(f"response references unknown config {r.config}")
            if r.query_idx >= len(self.meta.queries):
                raise ValueError(f"response query_idx {r.query_idx} out of range")
            for sp in r.spans:
                if sp.detector not in detector_ids:
                    raise ValueError(f"span references unknown detector {sp.detector}")
                if not (0 <= sp.start < sp.end <= len(r.text)):
                    raise ValueError(f"span {sp.start}:{sp.end} out of bounds")
        for e in self.effects:
            if e.detector not in detector_ids or e.section not in section_ids:
                raise ValueError(f"effect references unknown detector/section {e.detector}/{e.section}")
            if e.per_query_idx and len(e.per_query_idx) != len(e.per_query):
                raise ValueError(f"effect {e.detector}/{e.section}: per_query_idx and per_query differ in length")
        if self.discovery:
            ids = {st.id for st in self.discovery.statements}
            have = {(r.config, r.query_idx, r.sample_idx) for r in self.responses}
            for st in self.discovery.statements:
                if st.section not in section_ids:
                    raise ValueError(f"statement {st.id} references unknown section {st.section}")
                if st.per_query_idx and len(st.per_query_idx) != len(st.per_query):
                    raise ValueError(f"statement {st.id}: per_query_idx and per_query differ in length")
                for ex in st.examples:
                    for cfg in (ex.with_config, ex.without_config):
                        if (cfg, ex.query_idx, ex.sample_idx) not in have:
                            raise ValueError(f"statement {st.id} example references a missing answer")
                for q, s_, v in st.verdicts:
                    if len(v) != 2 or set(v) - set("ynau") or ("full", q, s_) not in have:
                        raise ValueError(f"statement {st.id}: bad verdict entry {(q, s_, v)}")
                for q, s_, _side, v in st.rejudged:
                    if v not in tuple("ynau") or ("full", q, s_) not in have:
                        raise ValueError(f"statement {st.id}: bad re-judge entry {(q, s_, v)}")
            for ref in self.discovery.prompt_echoes:
                if tuple(ref) not in have:
                    raise ValueError(f"prompt echo {ref} references a missing answer")
            sc = self.discovery.screen
            if sc:
                disc_q = set(self.discovery.discovery_queries)
                targets = self.meta.query_targets
                for pk in sc.picked:
                    if pk.section not in section_ids or pk.query_idx not in disc_q:
                        raise ValueError(f"screen pick {pk} is not a discovery question of a known part")
                    if targets and pk.section in targets[pk.query_idx]:
                        raise ValueError(f"screen pick {pk} is a question that targets its own part")
                    if ("full", pk.query_idx, pk.sample_idx) not in have:
                        raise ValueError(f"screen pick {pk} references a missing answer")
            for rd in self.discovery.readings:
                if rd.section not in section_ids or not set(rd.confirmed + rd.side_effects) <= ids:
                    raise ValueError(f"reading for section {rd.section} references unknown ids")
        if self.confirmation:
            self._check_confirmation(section_ids, config_ids)
        if self.authored:
            self._check_authored(section_ids, config_ids)
        if self.readout:
            self._check_readout(section_ids)
        return self

    def _check_authored(self, section_ids: set[int], config_ids: set[str]) -> None:
        have = {(r.config, r.query_idx, r.sample_idx) for r in self.responses}
        seen = {st.id for st in self.discovery.statements} if self.discovery else set()
        for st in self.authored.statements:
            if st.source != "authored" or st.significant or st.family is not None:
                raise ValueError(f"authored statement {st.id}: source must be authored, not significant, no family")
            if st.id in seen:
                raise ValueError(f"authored statement {st.id}: duplicate id")
            seen.add(st.id)
            wo = f"without_{st.section}"
            if st.section not in section_ids or wo not in config_ids:
                raise ValueError(f"authored statement {st.id} references an unknown part")
            if st.per_query_idx and len(st.per_query_idx) != len(st.per_query):
                raise ValueError(f"authored statement {st.id}: per_query_idx and per_query differ in length")
            for ex in st.examples:
                for cfg in (ex.with_config, ex.without_config):
                    if (cfg, ex.query_idx, ex.sample_idx) not in have:
                        raise ValueError(f"authored statement {st.id} example references a missing answer")
            for q, s_, v in st.verdicts:
                if len(v) != 2 or set(v) - set("ynau") or ("full", q, s_) not in have or (wo, q, s_) not in have:
                    raise ValueError(f"authored statement {st.id}: bad verdict entry {(q, s_, v)}")
            for q, s_, _side, v in st.rejudged:
                if v not in tuple("ynau") or ("full", q, s_) not in have:
                    raise ValueError(f"authored statement {st.id}: bad re-judge entry {(q, s_, v)}")

    def _check_readout(self, section_ids: set[int]) -> None:
        if not self.discovery:
            raise ValueError("a readout needs the discovery block it reads")
        ids = {st.id for st in self.discovery.statements}
        authored = {st.id for st in self.authored.statements} if self.authored else set()
        cand = {c.id for c in self.confirmation.candidates} if self.confirmation else set()
        for pr in self.readout.parts:
            if pr.section not in section_ids:
                raise ValueError(f"readout part {pr.section} is not a section")
            for ch in pr.checks:
                if (ch.data == "authored") != (ch.id in authored) or ch.id not in ids | authored \
                        or (ch.data == "confirmation" and ch.id not in cand):
                    raise ValueError(f"readout check {ch.id} references an unknown statement")
            for ex in pr.excluded:
                if ex.id not in ids | authored:
                    raise ValueError(f"readout exclusion {ex.id} references an unknown statement")

    def _check_confirmation(self, section_ids: set[int], config_ids: set[str]) -> None:
        c = self.confirmation
        if not self.discovery:
            raise ValueError("a confirmation needs the discovery block it retests")
        screen_ids = {st.id for st in self.discovery.statements}
        if "full" not in c.configs or not set(c.configs) <= config_ids:
            raise ValueError("confirmation.configs must include 'full' and only the run's configs")
        for qq in c.queries:
            if not set(qq.targets) <= section_ids:
                raise ValueError("a confirmation question targets an unknown section")
        have = set()
        for r in c.responses:
            if r.config not in c.configs or r.query_idx >= len(c.queries):
                raise ValueError(f"confirmation response {(r.config, r.query_idx, r.sample_idx)} is out of range")
            have.add((r.config, r.query_idx, r.sample_idx))
        cand_ids = set()
        for st in c.candidates:
            cand_ids.add(st.id)
            if st.id not in screen_ids or st.section not in section_ids:
                raise ValueError(f"candidate {st.id} is not a statement of the screen")
            wo = f"without_{st.section}"
            if wo not in c.configs:
                raise ValueError(f"candidate {st.id}: config {wo} was not answered")
            if st.per_query_idx and len(st.per_query_idx) != len(st.per_query):
                raise ValueError(f"candidate {st.id}: per_query_idx and per_query differ in length")
            for ex in st.examples:
                for cfg in (ex.with_config, ex.without_config):
                    if (cfg, ex.query_idx, ex.sample_idx) not in have:
                        raise ValueError(f"candidate {st.id} example references a missing answer")
            for q, s_, v in st.verdicts:
                if len(v) != 2 or set(v) - set("ynau") or ("full", q, s_) not in have or (wo, q, s_) not in have:
                    raise ValueError(f"candidate {st.id}: bad verdict entry {(q, s_, v)}")
            for q, s_, _side, v in st.rejudged:
                if v not in tuple("ynau") or ("full", q, s_) not in have:
                    raise ValueError(f"candidate {st.id}: bad re-judge entry {(q, s_, v)}")
        for ref in c.prompt_echoes:
            if tuple(ref) not in have:
                raise ValueError(f"confirmation prompt echo {ref} references a missing answer")
        for rd in c.readings:
            if rd.section not in section_ids or not set(rd.confirmed + rd.not_confirmed + rd.side_effects) <= cand_ids:
                raise ValueError(f"confirmation reading for section {rd.section} references unknown ids")


def load(path: str | Path) -> RunBundle:
    return RunBundle.model_validate_json(Path(path).read_text())


def dump(bundle: RunBundle, path: str | Path) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(bundle.model_dump_json() + "\n")


def json_schema() -> str:
    return json.dumps(RunBundle.model_json_schema(), indent=2) + "\n"
