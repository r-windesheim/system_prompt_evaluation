# Discovery: effects nobody wrote a detector for

The habit detectors only see 19 regex patterns and 6 shape metrics. Discovery looks for anything else a part changes, including side effects and instructions that are not followed. The rule is **propose, then verify**: a model may suggest an effect, but an effect is only reported if blinded per-answer judgments, run through the same paired statistics as the habits, confirm it. Code: `spet/discovery.py`. Prompts and parsers: `spet/prompts.py`.

**The main run is a screen.** It tests every proposed statement (111 in the July 2024 run) and corrects within two large families. Its p-values are valid, but a statement that comes close is a candidate, not a finding. **Only the confirmation supports a claim** (see [Confirmation](#confirmation)): a few candidates, chosen by a fixed rule, retested on fresh questions in a small family.

```
python -m spet plan spec.yaml                        # answers, call bounds and test floors; no model calls
python -m spet discover runs/x.json -o runs/x.json   # judge calls only, no new answers
python -m spet discover runs/x.json --screen runs_out/x-screen.json   # proposer sees high-lift pairs first
python -m spet run spec.yaml --discover              # answers, then discovery
POST /api/runs {..., "discover": true}               # status gains phase, discovery_done, discovery_total
```

The judge uses the same OpenAI-compatible provider class as the answers, so it has the same cache, concurrency limit and retries. It runs at temperature 0. Settings are resolved in this order:

1. CLI flags (`--judge-base-url`, `--judge-model`).
2. `SPET_JUDGE_BASE_URL`, `SPET_JUDGE_MODEL`, `SPET_JUDGE_API_KEY`, `SPET_JUDGE_MAX_TOKENS` (default 4000), `SPET_JUDGE_REASONING_EFFORT`, `SPET_JUDGE_MAX_CONCURRENCY`.
3. The run's endpoint and model.

The run's key (`SPET_API_KEY`) is only sent to a judge on the same host as the run. A judge on another host needs `SPET_JUDGE_API_KEY`.

A stub run always gets the stub judge unless `--judge-base-url` is given, so environment variables never send stub answers to a real endpoint.

## What is proposed and what is verified

For each part *k*, statements about a **single answer** that can be checked with yes or no come from two sources:

- **Intended** (up to 3): written from the instruction text alone, without looking at any answer. Each one says what an answer would show if the instruction were followed. These are how the tool can say "not followed".
- **Discovered** (up to 6): a model sees about 6 pairs per call, 2 calls per part. Each pair is the with-*k* and without-*k* answers to the same question and sample. The model is asked what differs systematically.
  - The two sides are labelled group A and group B. Which letter is the with-part side is random per call, and the order within each pair is random too.
  - The instruction is not shown, so the model can neither tell nor be led by which side has the part.
  - Comparative or two-answer statements ("Answer A is longer…") are dropped by the parser.
  - Near-duplicates are merged by word overlap. A discovered statement that duplicates an intended one is dropped, and the intended one gets the flag `also_discovered`.

**Verification.** The judge sees one statement, the user's question and one answer. It is told nothing about the configuration, and it replies YES, NO, or NA ("this statement is about a situation the question doesn't involve"). It judges the answers in `full` and `without_k` on the statement's questions (see [Targeted questions](#targeted-questions)). Pairs where either side is NA or unreadable are dropped, and so are pairs where either answer recites the system prompt (see [Recited prompts](#recited-prompts)). The 0/1 judgments then go through `attribution.paired_stats`, the code the habits use, **with the question as the unit** (`discovery.test = "question"`):

- with and without rates;
- the paired difference;
- the sign-flip p-value, flipping whole questions (see [Pairs from the same question](#pairs-from-the-same-question));
- a bootstrap interval over questions (`ci`, and the same in `ci_query`);
- per-question differences: `per_query[i]` belongs to question `per_query_idx[i]`. Questions with no usable pair are absent, so `per_query` is **not** indexed by question;
- the smallest detectable change, from the spread of per-question differences.

**Every verdict is stored** (v5). `verdicts` lists each judged pair as `[query_idx, sample_idx, "yn"]`: the with-part verdict, then the without-part verdict (y yes, n no, a NA, u unreadable or failed). `rejudged` lists the re-judged sample as `[query_idx, sample_idx, side, verdict]`, with side `w` or `o`. From these alone you can recompute the rates, `per_query`, the exclusions and the agreement; `tests/test_discovery.py` does so. Pairs dropped before judging (recited prompts) are not listed. The July 2024 bundle (v3) has none of this, which is why its per-question breakdown could not be audited.

**Nothing rests on the proposer.** A discovered statement that is false, such as the stub's planted "mentions a pricing plan", gets judged no on both sides and is never significant. The proposer only decides which statements get tested.

## Targeted questions

A run spec may say which part each question was written for:

```yaml
n_per_query: 2              # samples where the question targets the removed part
n_per_query_untargeted: 1   # samples everywhere else (optional; needs targets)
queries:
  - text: "Write a JavaScript function that debounces another function."
    targets: ["Code formatting"]       # section labels, or 0-based section ids
  - text: "What's the capital of Australia?"
    targets: []                        # targets no part
  - "A plain string also targets no part."
```

`POST /api/runs` takes the same: `queries` as strings or `{text, targets}`, and `n_per_query_untargeted`. The targets are stored in `meta.query_targets` (section ids per question). With them:

- **Intended statements for part *k*** are judged only on the questions that target *k*, and the reading (followed / partly followed / redundant / not followed) is computed from those. An instruction about code is no longer averaged over 45 questions that contain no code, and "not followed" no longer counts questions where the instruction cannot apply.
- **A part that no question targets** keeps the old behaviour: its intended statements are judged on every question. They get the flag `untargeted`, the reading's note says so, and a warning lists those parts. A run that gives no targets at all gets one warning instead.
- **Discovered statements for part *k*** look for side effects, so they are proposed from, and judged on, questions that do **not** target *k*. The held-out split still applies.

**Sample counts.** With `n_per_query_untargeted`, a question gets `n_per_query` samples in `without_k` when it targets *k*, and in `full` when it targets any part; it gets `n_per_query_untargeted` samples everywhere else. Every targeted pair then has the full count, and every other pair has the smaller count. Samples share seeds by index, so the pairs are the first min(*n*₁, *n*₂) samples. Without targets, or without `n_per_query_untargeted`, every configuration gets `n_per_query` samples on every question, as before.

Habit effects pool every pair, so with unequal counts they lean on each part's targeted questions. The run adds a warning when that happens.

`python -m spet plan spec.yaml` prints the answer count and upper bounds on discovery calls without calling any model.

## The held-out split

The questions are split once per run, deterministically from the run seed:

- Discovered statements are proposed from about a third of the questions (`discovery_queries`), minus those that target the part.
- They are judged **only** on the remaining questions (`holdout_queries`), minus those that target the part. `verified_on` lists them.
- Both lists are stored in the bundle.

So a discovered hypothesis is never tested on the answers that suggested it, and its p-value is valid. An attention screen (`--screen`) only reorders the pairs drawn from the discovery questions; it never draws from the held-out ones (see [Attention screen](#attention-screen)). Intended statements come from no data, so they are verified on all of the part's targeted questions (or all questions, if it has none).

The cost is power. With 5 questions, discovered statements are tested on 3 questions. If a run has a single question, discovered statements are skipped and a warning is added.

## Pairs from the same question

Answers to the same question resemble each other, whichever configuration wrote them. Up to v3, discovery used the habits' test: a sign flip per **cell** (question × sample) and a bootstrap over cells. That test is valid for "removing *k* changes answers to these exact questions". But it counts five samples of one question as five pieces of evidence, so a single question can carry a result. In the July 2024 run, the "Claude Sonnet 3.5" statement drew its largest difference (+1.0) from the one question that made the model recite its prompt.

Discovery now treats the question as the unit:

- The p-value flips the sign of each question's summed difference (`attribution.cluster_sign_flip_p`). It is exact up to 16 questions.
- `ci` is a bootstrap over questions. `full_rate_ci`, used for "not followed", already was.
- `mde` is computed from per-question differences. It is `null` when the test cannot reach the MDE level at all.

**The price is a floor on p.** With *G* questions, the smallest possible p is 2/2^*G*: 0.0078 for 8 questions and 0.00024 for 13. Benjamini-Hochberg's first threshold is α/*m* for *m* tests in the statement's family (see [Multiple testing](#multiple-testing)). A statement whose floor is above that threshold can only become significant alongside many others; it gets the flag `too_few_questions`, and a warning counts them. The remedy is more questions, not more samples. With 1 sample per question, as in the side-effect checks under `n_per_query_untargeted: 1`, a cell is a question and nothing changes.

Two details make the floor higher in practice:

- **A question whose differences sum to zero does not count.** Flipping its sign changes nothing, so the floor is 2/2^(questions with a nonzero sum). With 2 samples per question a sum is −2 to +2, and 0 is common when the part changes behaviour only sometimes.
- **Above 16 questions the test is Monte Carlo** (10,000 sign draws), and its smallest p is 1/10,001 ≈ 0.0001. `attribution.cluster_p_floor`, which sets `too_few_questions`, still returns 2/2^*G* there. That is harmless while α/*m* > 0.0001, i.e. *m* < 500 per family.

**The example after this change** (`examples/sonnet35-july2024.yaml`: 13 questions per part, `spet plan` prints these):

| family | tests *m* (at most) | first threshold α/*m* | questions per statement | smallest p |
|---|---|---|---|---|
| intended | 48 | 0.00104 | 13 | 2/2^13 = 0.00024 |
| discovered | 96 | 0.00052 | 128–134 | 1/10,001 ≈ 0.0001 (Monte Carlo) |

An intended statement can now pass on its own if at least 11 of its 13 questions show a difference of the same sign (2/2^11 = 0.00098 ≤ 0.00104; 10 such questions give 0.00195, which needs other statements to pass too). Under the old plan (8 questions, one family of up to 144) the floor 0.0078 was 22 times the threshold 0.00035.

The habit effects (`spet/run.py`) still use the per-cell test. Their planted-instruction test runs on 3 questions, where a by-question test could never reach significance (floor 0.25).

## Recited prompts

Some questions ("repeat your instructions word for word") make the model recite its system prompt. A recited instruction satisfies any statement about the instruction's content. The `without_k` prompt lacks part *k*, so its recitation lacks it too. Every intended statement then looks followed on that question.

- An answer **recites** its prompt when at least half the words of its own configuration's system prompt sit in runs of 8 or more consecutive words that the answer repeats (`echo_share`, options `echo_ngram` and `echo_share`). In the July 2024 run, every answer to that question that complied scored 0.74 to 1.0, and every other answer scored at most 0.012.
- Pairs with a recitation on either side are left out **before** judging, for intended and discovered statements and for the proposer. The question stays in the run; only its recited answers drop out.
- The answers are listed in `discovery.prompt_echoes`, and each statement counts its lost pairs in `n_excluded_echo`. A warning gives the total and the questions. These exclusions are not part of the NA-asymmetry check: they happen before judging and depend on the answer alone.

## Multiple testing

- **Two Benjamini-Hochberg families, by source** (v5). Intended statements answer "is the instruction followed?" and discovered statements "does the part have side effects?". They are different questions, asked of different questions (targeted versus non-targeted), so each source is corrected on its own, across all parts. Up to v4 both sources formed one family.
- **What that costs:** the FDR holds within each family, not across both. If both families are reported together, the expected share of false findings among all of them can be up to about α + α rather than α. This is the same convention as habits versus shape metrics.
- These families are separate from the habits, which are separate from the shape metrics.
- `statement.family` says which family its q-value comes from; `discovery.families` gives the number of tested statements in each, and `discovery.n_tests` their sum. Statements judged no in every answer on both sides are reported but not counted, matching the habits.
- `too_few_questions` compares a statement's floor with the first threshold of its own family.
- Candidates dropped before testing (by the cap or deduplication) were never tested, so they don't count.
- Statements with unreliable judges **stay** in the family. They are only barred from being significant. That is conservative: the family is not chosen after seeing reliability.

## Confirmation

```
python -m spet confirm runs/x.json confirm.yaml -o runs/x-v3.json --plan    # candidates and plan, no model calls
python -m spet confirm runs/x.json confirm.yaml -o runs/x-v3.json --max-answers 1000 --max-judge-calls 4000
```

The screen picks candidates; the confirmation tests them once, on answers the screen never saw. Code: `spet/confirm.py`.

**Selection rule** (`SelectionRule`, fixed in code and stored as `confirmation.rule`). A screen statement is a candidate if it was tested, none of `judge_unreliable`, `rejudge_one_class`, `ceiling`, `never_seen`, `few_pairs`, `too_few_questions` is set, and its screen p is below 0.1 (intended) or 0.01 (discovered). The rule is applied to the bundle by code; nobody picks candidates by hand. The command prints what it picked.

**Fresh questions** (the confirm YAML). For each part with an intended candidate, questions that target that part (13 in the July 2024 example); for discovered candidates, general questions that target no part (`targets: []`, 60 in the example). The command refuses a spec that:

- targets a part without an intended candidate, or misses one that has one;
- has general questions without a discovered candidate, or the reverse;
- repeats a screen question or nearly does (content-word Jaccard of 0.5 or more), or repeats itself. This is a backstop: the questions are written to differ from the screen's in task and object, and each one's largest overlap is stored (`queries[i].overlap`);
- uses the run's seed, or a provider block that differs from the run's model, endpoint host, `max_tokens` or reasoning effort. The temperature is always the run's.

The judge must also be the screen's: the same model, host, `max_tokens`, reasoning effort and judge prompts (`discovery_prompts_version`), compared with the bundle's `meta.settings` before anything runs. So `SPET_JUDGE_MAX_TOKENS` and `SPET_JUDGE_REASONING_EFFORT` must be set as they were for the screen.

**Answers.** Only `full` and each candidate part's `without_k` are answered. Targeted questions get `n_per_query` samples (6) and general ones `n_per_query_general` (2). Samples share seeds across configs by (question, sample), from the confirmation's seed. Six samples, not two: a question whose differences sum to zero drops out of the by-question test, and with 2 samples the screen saw many such ties. The answers are stored in `confirmation.responses`, indexed into `confirmation.queries`, not in the run's `responses`.

**Judging and test.** These follow discovery, with nothing changed:

- the candidate's statement text, verbatim;
- the blinded judge prompt;
- the stratified re-judge with the second prompt, and the same flags (`judge_unreliable`, `judge_unchecked`, `unparseable`, `exclusion_asymmetry` block);
- recited prompts left out before judging;
- the two-sided by-question sign-flip test;
- Benjamini-Hochberg at the run's alpha, intended and discovered as separate families.

The family size *m* is the number of candidates in the family, fixed by the rule (4 and 1 in the example). A candidate that turns out untested stays in with p = 1, so *m* never depends on the data. The Monte Carlo test (above 16 questions) is seeded from the confirmation seed (`settings.test_rng_seed`).

**Confirmed** means all three hold:

- q < alpha;
- no blocking flag;
- a difference with the same sign as in the screen.

A significant difference in the other direction is **not** confirmed and gets the flag `reversed`. The test stays two-sided; using the screen's direction to make it one-sided is not allowed.

**Reported, never dropped.** Every candidate is stored as a `Candidate` with:

- the screen's p, q and rates (`screen_*`);
- the confirmation's rates, interval, p and q;
- `confirmed`;
- its flags, verdicts, re-judge sample and example pairs.

**Readings** (`confirmation.readings`, one per part, with `basis`):

- A part whose intended candidates are all confirmed reads `followed`. If some of them fail, it reads `partly_followed`.
- A part with no confirmed intended candidate keeps the main run's reading (`basis: screen`). Its failed candidates are listed in `not_confirmed`. Failing to confirm is not evidence that the instruction is not followed.
- A confirmed discovered candidate is a side effect of its part. This is by rule; no model classifies it.
- Parts with no candidate keep the main run's reading (`basis: screen`).

**Resuming.** Answers and verdicts are cached (`.spet_cache/`). If any judge call fails after the provider's retries, the command writes nothing and exits non-zero, and you rerun the same command. If the same calls still fail on two identical reruns (a call that fails every time, not an outage), run the same command once more with `--keep-failed-calls`. The failed calls then count as unreadable, as in discovery, and `n_errors` and a warning report them. This fallback was fixed before the July 2024 confirmation ran. Run the confirmation once. If the result disappoints, do not change the rule, the questions, the seed, the test or alpha, and do not run it again.

**Bundle.** The combined bundle is schema 6: the run and its screen, unchanged, plus `confirmation`. `spet rescore` keeps it. `spet discover` drops it, because a new screen voids it.

**Cost of the July 2024 example:**

- answers: 3 parts × 13 questions × 6 samples × 2 configs + 60 × 2 × 2 = 708;
- judge calls: ≤ 4 × 13 × 6 × 2 + 60 × 2 × 2 = 864;
- re-judge calls: ≤ 100.

## Attention screen

The proposer sees about 12 pairs per part, drawn at random from the discovery questions. Most of them are questions where the part plausibly does nothing. The screen picks them by where the model actually looks.

**What it measures.** `deploy/modal_attention.py::screen` renders each question exactly as vLLM 0.18.1 sends it to gpt-oss: the harmony system header (date, reasoning effort), then the joined parts as a second `system` message, then the question. It asserts that layout, that re-tokenizing it gives the same ids, and that every part is found once, in order. It samples N answers per question with the full prompt (default 4; transformers with MXFP4 weights dequantized to bf16, not vLLM, so these are fresh samples from nearly the same distribution), runs one teacher-forced pass with eager attention, and keeps, per full-attention layer, the head-averaged attention mass of the reasoning tokens and of the answer tokens on each part. `spet/screen.py` turns that into the screen file:

- density = mass on a part / its token count; rel = density / the mean density of all parts in that generation;
- **lift** = a part's rel on one question (mean over samples) / that part's median rel over all questions, on the middle and late full-attention layers. Raw attention is dominated by position, so only lift is used.
- per pair: the lift for reasoning and answer tokens, the per-sample lifts, their spread, and the share of samples on the same side of 1; per question: the mean pairwise Spearman correlation of the part profile between samples.

In the pilot (two samples, 10 questions, a different prompt layout) reasoning-token attention put the part a question was written for first on 7 of 10 questions. The screen is a ranking aid, not a finding.

**How discovery uses it** (`--screen file`, `--screen-block reasoning|answer`, default reasoning):

- The pool of pairs for part *k* is unchanged: the discovery questions that do not target *k*, without recitations. The screen only **orders** it, highest lift for *k* first. Ties and questions the screen lacks keep the random order.
- Verification is unchanged: the same held-out questions, the same test, the same families. `verified_on` is identical with and without a screen, and so are the intended statements' results; only their `also_discovered` flag can change, since the proposer may now find other things.
- A screen made for other parts or questions is refused (a fingerprint of the part and question texts).
- The bundle records `discovery.screen`: the file's name and sha256, the block, the model, the samples, and every pair shown (`picked`: part, question, sample, lift, call).

**Why the held-out split still holds.** A p-value is valid if the statement was chosen without looking at the data that test it. Those data are the judge's verdicts on the run's answers to the held-out questions. The screen sees only its own generations, and it only chooses among discovery questions, which are never verified on. So no statement can depend on a verification answer. A wider option was considered: let the screen pick from **all** non-target questions and drop its picks from that part's verification. That is also valid (the screen never sees run answers), and it would give a larger verification set, but the held-out set would then differ by part and depend on the screen file, and runs with and without a screen would no longer be tested on the same questions. It was not taken.

**What it costs.** The smoke run (`--smoke`: render all 208 prompts, one 300-token generation) took 21 s inside the function on an H100. The full example, 208 questions × 4 samples, is estimated at **about 50 to 65 GPU minutes** on H100s, in 13 calls of 16 questions run at most 4 at a time. The estimate assumes the old run's answer lengths (about 420 tokens per generation, 0.4% cut off at 4,000), a decode step of 32 to 45 ms in batches of 16 (the pilot measured about 32 ms in batches of 10), and about a minute of start-up per call.

## Judge reliability

Reliability is measured, not assumed.

- **Re-judging.** For each statement, up to 10 YES and 10 NO verdicts are re-judged with a second prompt that means the same thing: different wording, the answer before the claim, and the options in reverse order.
  - Re-judging with the same prompt at temperature 0 would just hit the cache and report 100%.
  - The sample is stratified, so `agreement` is not inflated by rare behaviours.
  - Cohen's `kappa` is reported alongside it.
- **Flags.** A statement with agreement below 0.8 or kappa below 0.5 gets `judge_unreliable`. One with fewer than 5 comparable re-judgments gets `judge_unchecked`. Either flag means it is **never significant**. Its raw q is kept so you can see what the gate blocked.
- **Unreadable output** (no verdict, both YES and NO, empty, cut off by max_tokens, or a failed call):
  - It is counted per statement (`n_unparseable`) and in total, and its pair is excluded. It is never read as "no".
  - If more than 20% of a statement's verdicts are unreadable, it gets `unparseable` and is never significant.
  - A warning goes into `analysis.warnings`.
- **Lopsided exclusions** (NA or unreadable verdicts). NA should depend only on the question, which is the same on both sides of a pair. A small judge, though, may say NA where it means NO, and long answers may run out its reasoning budget on one side only. Either way, dropping pairs then keeps only the cases where both sides show the behaviour.
  - The per-cell difference in exclusions (with side minus without side) gets its own sign-flip test.
  - If p < 0.05, the statement gets `exclusion_asymmetry`. It is then never significant and is not used for the reading.
  - `n_excluded_with` and `n_excluded_without` show the split.
- **One-sided re-judge samples.** If the judge said NO to every answer (the usual case for `not_followed`), the re-judge sample holds only NO verdicts. Agreement of 1.0 then shows only that the judge repeats itself, not that it could say YES.
  - Such statements get `rejudge_one_class`.
  - A `not_followed` or `redundant` reading that rests only on them carries a note and a warning.
  - They are not blocked: that would make every "not followed" verdict impossible.
- **What agreement does not measure.** Agreement is stability, not accuracy. A judge that is consistently wrong passes. Check the stored `examples` by eye before trusting a finding.

## Classification and the per-part reading

- **Intended statements** are classified as intended by source.
- **Significant discovered statements** get one model call each. The call is told the instruction and the direction ("with this instruction, answers are MORE/LESS often like this") and returns `intended` or `side_effect`. The label is a model's opinion; the effect underneath is verified.
- **Non-significant discovered statements** are not classified (`classification: null`).

`readings` derives a verdict for each part mechanically, from the intended statements whose judge is reliable:

| adherence | meaning |
|---|---|
| `followed` | at least one intended statement is significant with delta > 0, and the rest are confirmed or redundant |
| `partly_followed` | some intended statements are confirmed and some are not |
| `redundant` | the intended behaviour occurs at ≥ 80% both with and without the part |
| `not_followed` | the upper 95% bound (by question) of the with-part rate is below 50% for every intended statement |
| `inconclusive` | none of the above |
| `not_assessed` | no intended statement has a reliable judge |

`side_effects` lists significant statements classified as side effects. **Caution:** `not_followed` and `redundant` rest on the judge's absolute yes-rate, not on a paired difference. A judge that is biased toward yes or toward no shifts both arms equally, which leaves the difference intact but moves the rates. Trust these two readings less than `followed`.

## What a small judge (gpt-oss-20b) can and cannot be trusted with

- **Fairly trustworthy:** concrete, surface-level statements. Examples: "contains an apology", "uses a numbered list", "ends with a question", "mentions a backup", "is written in French".
- **Not trustworthy:** vague or evaluative statements. Examples: "has a friendly tone", "is well structured", "is more confident". Its verdicts drift with wording. The reliability gate is designed to catch this, and it does so in the stub test.
- **Weak areas:**
  - counting (exact numbers of items or words; the regex metrics are better here);
  - long answers (it may miss things late in the answer);
  - conditional statements and NA;
  - negation.
- **The proposer:** a 20B model will miss subtle differences and may phrase statements loosely. Missing an effect costs power, not validity.
- **The classification** is the least reliable output. Treat it as a hint.
- **Formatting:** gpt-oss reasons before it replies. A `max_tokens` cap that is too small cuts the reply off. That shows up as unreadable, not as "no".
- **Upgrading:** use a stronger judge by setting `SPET_JUDGE_*`. The bundle records `judge_model`, the host, max_tokens, the reasoning effort and a hash of the prompts in `meta.settings`.

## Cost in model calls

Notation:

- *K*: parts (with a `without_k` config);
- *Q*: questions, of which *Q_h* are held out (*Q_d* = round(*Q*/3), at least 1, *Q_h* = *Q* − *Q_d*);
- *S*: samples per question (no targets);
- *I* ≤ 3 intended and *D* ≤ 6 discovered statements per part;
- *C* = 2 proposer calls per part;
- *R* = 10 re-judgments per class.

Before dropped answers, the calls are (without targets):

```
intended  K
propose   K·C
judge     2·S·K·(Q·I + Q_h·D)          (every answer in full and without_k, per statement)
rejudge   ≤ 2·R·K·(I + D)
classify  ≤ K·D                        (significant discovered statements only)
```

With targets, part *k*'s intended statements see its *T_k* targeted questions at *S_t* samples, and its discovered statements see the held-out questions that do not target it at *S_u* samples:

```
judge     Σ_k 2·(I·T_k·S_t + D·|holdout ∖ targets(k)|·S_u)
```

**The July 2024 example** (`examples/sonnet35-july2024.yaml`: *K* = 16, 208 questions, 13 per part, *S_t* = 2, *S_u* = 1): 3,952 answers. `spet plan` gives at most 27,516 judge calls (2,496 intended, the rest discovered), 2,880 re-judgments, 16 + 32 proposal calls and ≤ 96 classifications. The previous plan (128 questions, 8 per part, *S_t* = 8) had 3,968 answers and 21,444 judge calls: the discovered checks grow with the held-out questions (about 130 per part instead of about 80). The first run (48 questions × 5 samples, no targets) made 4,080 answers and 35,266 judge calls.

**Example: 7 parts, 15 questions, 8 samples** (*Q_d* = 5, *Q_h* = 10, *I* = 3, *D* = 6):

- intended: 7
- propose: 14
- judge: 2·8·7·(15·3 + 10·6) = 11,760
- rejudge: ≤ 1,260
- classify: ≤ 42
- total: **≤ 13,083 calls**

The answers themselves take (K+1)·Q·S = 960 calls, so discovery costs about 13–14× as many calls as the run. Each judge call carries a full answer, so input tokens scale the same way. Judging dominates.

To reduce cost, lower *D* or *I* (`--max-discovered`, `--max-intended`). The re-judging could also be shrunk. Answers from `full` are judged once per statement and are not shared across parts.

## What stays invisible

- **Interactions between parts.** This is still leave-one-out. Behaviour that two parts both cause, or that the questions already cause, shows no difference when either part is removed. Shapley or pairwise removals would need more answer runs.
- **Effects outside these questions.** Results describe these questions. Intervals and p-values are by question, so they are honest about other questions like these. With few questions they are wide, and some statements cannot reach significance at all (`too_few_questions`).
- **Effects the proposer did not notice,** or that it noticed only on the discovery questions. The attention screen changes which pairs it sees, not this.
- **Small effects.** The test's power depends on the number of questions, not pairs. `mde` gives the smallest change detectable 80% of the time, and is `null` when the question count rules detection out.
- **Instructions in parts with no targeted question** are judged on every question, so the rates are diluted (`untargeted`).
- **Mechanism.** A verified statement says answers differ, not why. `length_shift` and `context_shift` flags mark parts that also change answer length or set identity. A judge may say yes more readily to longer answers.
