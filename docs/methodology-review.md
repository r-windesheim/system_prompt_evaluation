# SPET methodology evaluation

## Verdict in one paragraph

The core statistics are sound. The design compares each "without section k" answer to the full-prompt answer on the same question and sample (paired diffs), tests them with a sign-flip test, and corrects for multiple testing with Benjamini-Hochberg across all 119 (habit, section) pairs. Recomputing from the real bundle reproduces all 119 stored deltas and p-values. The 7 significant effects are real for this run: bold/s0, apology/s1, list_item/s3, parenthetical/s3, question/s3, exclamation/s3 and exclamation/s5. The page around them is not ready to show as it stands, for three reasons:

- It shows a "Likely" tier that is mostly noise.
- It says "no effect" for sections these probes could not test, or could only have detected if the section removed the habit almost entirely.
- It names some causes wrongly, e.g. "Step Formatting makes the model ask more questions" when the bullets split the questions it would ask anyway.

It is fine to show people if you:

- show significant effects only;
- word every claim as "On these 5 questions, removing section X changed habit Y by Z";
- say "not detected" instead of "no effect";
- flag sections that could not be tested;
- note when an effect probably comes from bullet formatting or answer length.

All of this is post-processing and UI text. None of it needs new model runs.

## What holds up

- **Paired design and test.** Every config answers the same (query, sample) cell. The sign-flip test is valid with these queries fixed, even though the cells cluster by query. It is conservative: under a simulated null it rejected 2.6% of the time at a 5% level.
- **No hand-picking of results.** Every (habit, section) pair gets an effect, a 95% interval (CI), a p-value and a corrected q-value. The tool does not just show the top section.
- **Fully reproducible from the stored text.** The bundle stores the full text and highlighted spans for all 320 responses. Re-running `spet/detectors.py` gives 0 mismatches, and every check in this review was done after the fact from the bundle.
- **The significant effects are robust.**
  - All 7 keep their sign when the CI is resampled by question instead of by cell.
  - 6 of 7 also hold on a yes/no metric ("does the answer contain this at all").
  - No single response drives any of them: the top 4 cells carry at most 53% of the total difference.
- **The ablation recovers instruction-shaped effects on a real model.** Apology/s1 +0.45, list_item/s3 +1.68, exclamation/s5 +0.53. The apology and exclamation effects survive correcting for answer length.
- **Counting matches per answer (not per 100 words) was the right choice.** Answer length varies from 50 to 79 words across configs, which would distort rates.
- **The seed travels as an API parameter, not in the prompt.** The section split is only accepted if every section appears word for word in the prompt.
- **The precision audit is honest about its limits.** Curly apostrophes are handled, which matters a lot for gpt-oss.
- **`DEFAULT_QUERIES` in `spet/server.py` and `spet/cli.py` are concrete and varied.** The test-coverage problems below come from choosing the vague "original probes" for this run, not from the defaults.

## Problems, ranked

### Critical

**1. The "Likely" label puts noise on screen**
- **Where:** `docs/mockups/template.html:217`, `strength()`.
- **What goes wrong:**
  - "Likely" means |delta| ≥ 0.25 and the uncorrected 95% CI excludes 0, with no multiple-testing correction.
  - The real run has 6 "Likely" effects with q = 0.30–0.69.
  - 3 of them miss even uncorrected p < 0.05: list_item/s0 p = 0.055, exclamation/s1 0.065, list_item/s4 0.075.
  - In a simulation with no real effects, this rule produced 1.9–2.3 "Likely" labels per run, and at least one in 86–95% of runs. Significant results under the same simulation: zero, every time.
  - Here, 6 of the 13 items on the findings list are "Likely".
  - The rule also contradicts the other view: `drilldown.template.html` lists the same pairs (e.g. list_item/s4) under "other habits stayed the same".
  - One "Likely" (clarify/s5 +0.275) is purely a wording effect (see problem 8).
- **Fix:** delete the tier, or rename it "suggestive" and require q < 0.20. Keep it out of the findings list and the section chips. Use one `strength()` function in both mockups. No compute.

**2. "No effect" is shown for sections the probes cannot test**
- **What goes wrong:** Sections 2, 4 and 6 are the only ones with no significant effect, and all three are untestable here. About 293–305 of the 320 answers are clarification requests.
  - **Length Constraint (s6):** "Keep answers under 200 words" never binds. The longest answer of all 320 is about 167–170 words, and 0 exceed 200. Without s6, answers average about 61–65 words.
  - **Uncertainty Handling (s2):** the confidence-booster count is 0 in every config, and hedging is 0.275 vs 0.25 per answer. The answers make no claims for the section to soften.
  - **Follow-up Prompt (s4):** 100% of full answers and 90% of without-s4 answers already contain a question, so there is almost no room to move. "At the end" is never followed: 0 of 40 full answers end with "?".
- **What the user sees:** the drilldown shows "No clear effect" and "Its job may be something we don't track" (`drilldown.template.html` lines 213 and 233), which points the user at the wrong reason.
- **Fix:** add a per-section "exercised?" check.
  - Habit at floor or ceiling in both arms (e.g. max mean < 0.1, or present in ≥ 90% of both).
  - A numeric limit never comes within ~80% in any config.
  - If either holds, show "Not testable with these questions".
  - Also warn when the probes are very short (< ~8 words). This check needs no compute.
  - Adding section-targeted probes, e.g. a long how-to question, needs runs.

### Major

**3. The UI misdescribes the interval and the q-value**
- **What goes wrong:**
  - The CI is described as "if we repeated the run, the difference would usually land in this range". It is actually an interval for the average over these 40 cells.
  - q is labelled "Chance of a fluke". It is a false-discovery-rate cutoff, not the probability that this effect is false.
  - The highlight text says the 40-pair comparison "is what shows the cause", which overstates a remove-one-section-at-a-time design. See `drilldown.template.html` lines 262–271.
- **Fix:**
  - CI: "range of plausible average differences on these questions".
  - q: "expected share of false findings at this cutoff".
  - Add one line saying sections are removed one at a time, so overlapping instructions can hide each other. No compute.

**4. The example pairs are the most extreme, not typical, and "same seed" does not make them twins**
- **What goes wrong:**
  - The shared seed gives almost no pairing on gpt-oss. Text similarity is 0.39–0.45 for same-seed pairs, versus 0.34–0.40 for a different sample of the same question.
  - The variance of paired diffs vs diffs with samples shuffled within each question: median 0.997.
  - `schedule.py:6` still claims "common random numbers", and the UI says "Same question, same seed."
  - `pickBest()` (`template.html` lines 318–325) picks the pair with the largest gap. So sections with no effect show 3–4-item gaps that are pure noise: s6/question, s4/question, s2/list_item.
  - Inference itself is still valid.
- **Fix:**
  - Pick the pair closest to the average effect, or a random one, and label which probe it came from.
  - Reword: the seed is shared for reproducibility; the pairs are not counterfactual twins.
  - No compute.

**5. "No effect" really means "not detected"; 40 pairs can only see large changes**
- **What goes wrong:** the smallest change detectable 80% of the time, at a realistic corrected threshold:

  | Habit | Smallest detectable change | As a share of the habit's normal level |
  |---|---|---|
  | hedge | 0.35–0.4 | ~1.2–1.45× |
  | parenthetical | 0.55–0.6 | ~1.1–1.3× |
  | exclamation | 0.55–0.6 | ~0.85–1.1× |
  | clarify | 0.6 | ~0.7–0.8× |
  | list_item | 1.0–1.4 | ~0.5–0.8× |
  | question | 1.05–1.4 | ~0.4–0.6× |
  | apology | 0.3 | ~0.3–0.4× |

  A section that halved hedging or parentheticals would usually show "no effect", and the findings list says such pairs "showed no reliable change and are left out".
- **Fix:** rename it "Not detected" and show the interval or the smallest detectable change next to it. Warn when that exceeds the habit's normal level. No compute. Halving the detectable change needs about 4× the pairs, roughly 160 per test.

**6. Results cover 5 questions, not "the prompt"**
- **What goes wrong:**
  - The 40 cells come from only 5 probes, and the effects depend strongly on the probe. Share of variation due to the probe: 0.46–0.51 for apology/s1, list_item/s3 and parenthetical/s3.
  - Resampling by probe instead of by cell widens the CIs by up to 2×. list_item/s3 goes from [1.12, 2.25] to [0.52, 2.85].
  - Per-probe deltas for list_item/s3: [0, 0.38, 2.25, 3.25, 2.5]. Six of the 7 significant effects are exactly 0 on "Should I do this?". bold/s0 is negative on all 5.
  - With 5 probes, no test at the probe level can reach p < 0.0625.
  - The UI says "Because of this part, the model will:" with no scope. The scope caveat lives only in the `attribution.py` docstring.
- **Fix:**
  - Write "On these N questions…" and show per-probe consistency, e.g. "higher on 4 of 5".
  - Add a CI that resamples by probe. No compute.
  - For claims meant to generalise, use 15–20 probes with 2–3 samples each instead of 5×8, at the same cost. Needs runs.

**7. The apology effect is mostly apologising for not understanding**
- **What goes wrong:**
  - The section says "apologise when the user reports a problem". Yet on "This seems wrong", the one probe that clearly reports a problem, apology is 1.0 per answer with and without the section.
  - The +0.45 comes from the non-problem probes. Per probe, full vs without s1: [0.62, 0.38, 1.0, 1.0, 1.0] vs [0, 0, 1.0, 0, 0.75]. The added apologies are "I'm sorry, I'm not sure what you're referring to".
- **Fix:** the per-probe breakdown from problem 6 exposes this. Also label which probe each example pair came from. No compute.

**8. The clarify detector misses gpt-oss's main phrasing**
- **What goes wrong:**
  - The pattern does not match "Could you let me know…" or "feel free to share…".
  - About 133–137 responses that ask for clarification score clarify = 0. With a broader pattern, 0.98–1.00 of full answers ask for clarification, against 0.625 as shipped.
  - Tone (s5) × clarify, +0.275, shown as "Likely", is purely a change of verb. On the broader yes/no metric it is +0.05 (p ≈ 0.5–0.6). The s0 clarify effect survives (+0.15, p ≈ 0.02–0.03).
- **Fix:** broaden the regex and measure clarify as yes/no per answer. Read about 30 answers per model to check what it misses. No compute.

**9. Question and parenthetical counts measure bullet formatting**
- **What goes wrong:** the question detector counts every "?"-terminated sentence, so one clarification split into bullets counts several times.
  - question/s3: +0.97, q = 0.006. Questions on bullet lines: 1.35 per answer in full vs 0.15 without s3. Questions outside bullets go down by 0.225, and "has any question" barely moves (1.00 vs 0.975).
  - 17 of 19 parentheticals in full sit on bullet lines, vs 2 in total without s3.
  - So 2 of s3's 4 headline effects restate "more bullets".
  - Exclamation/s3 is not explained this way: 0 of its spans are on list lines.
  - The extra questions are literally there (3 bulleted questions instead of 1 compound one), so the label misleads but is not flatly false.
  - Follow-up Prompt (s4) shows nothing on any metric: +0.20 count, p = 0.50; yes/no +0.10, p = 0.12–0.13; ends-with-"?" 0% in both arms.
- **Fix:**
  - Add yes/no metrics ("any question", "last sentence is a question", "any list") through the same pipeline.
  - Flag an effect as "probably a side effect of bullet formatting" when more than 70% of its spans sit inside list items, or when the same section also moves list_item or line count significantly.
  - Make the question regex skip "e.g." and "i.e.". It currently cuts 71–72 of 696 highlights in half.
  - No compute.

**10. Counts still scale with answer length, and the length rule has no metric**
- **What goes wrong:**
  - Correlation of counts with word count (Spearman): list_item 0.85, parenthetical 0.58, question 0.51.
  - Removing s0 makes answers longer by 18 words (CI [−27, −8]). Removing s3 makes them shorter by 11 words (CI [5, 17]).
  - The "Likely fewer bullets" for s0 (−0.80) becomes +0.26 (p = 0.34) after adjusting for length. bold/s0 survives at −0.95 (p ≈ 0.002).
  - question/s3: about half of the +68% comes from length (+30% characters).
  - No metric targets length, so "Length Constraint" can never register an effect.
  - Adjusting for length shows the mechanism; it is not a corrected causal effect.
- **Fix:** add word and line count as tracked metrics with their own CI. Flag effects in sections that also shift length ("may be a by-product of longer or shorter answers"), optionally with a length-adjusted delta. No compute.

**11. Precision values in the bundle come from a different model**
- **What goes wrong:**
  - The bundle reports precision = 1.0 (n = 30) for offer, question, clarify, list_item, bold and exclamation. Those numbers come from a gpt-4o-mini audit labelled by an LLM (`docs/detector-precision.md`).
  - On gpt-oss, Offer is about 0 of 36. Its hits are 21 "I'm happy to…" openers, 14 "feel free to share/paste…" and 1 "Let me know if there's a deadline". Almost none are closing offers of more help.
  - The UI shows no badge, but it also shows no warning, which implies the detector was validated. No offer effect reaches the screen in this run.
- **Fix:**
  - Store precision per model, or mark these numbers "measured on gpt-4o-mini".
  - Require Offer to sit in the last 1–2 sentences.
  - Label about 20 gpt-oss hits per detector. This is a labelling pass of about 300 hits, not new model runs.

### Minor

**12. The role sentence is context, not a style rule**
- **What goes wrong:**
  - Removing s0 turns Lumen support answers into generic-assistant answers. Share of answers on dev topics: 0.68–0.72 in full vs 0.30–0.33 without s0.
  - Bold appears in 0.375 of answers without s0, against 0.00–0.05 in every other config.
  - "Role & Audience reduces bold" is causally true but reads like a formatting rule.
- **Fix:** flag identity or audience sections as "context shift". Optionally ablate by swapping in "You are a helpful assistant." instead of deleting. That costs one more config.

**13. "Hedge" and "apology" measure something other than their labels**
- **What goes wrong:**
  - 73–76 of 100 hedge hits are "not sure what you mean", i.e. the model not understanding. Real hedges (might / perhaps / I think) occur 22 times in 320 answers.
  - 141 of 243 apology hits are sympathy: "sorry to hear", "sorry you're…".
  - No wrong verdict is shown in this run.
- **Fix:** split each detector into two ("hedge on a claim" vs "didn't understand"; "apology" vs "sympathy"), or rename them. No compute.

**14. The q-values include 49 tests that cannot fire**
- **What goes wrong:**
  - 7 detectors are zero in all 320 answers, giving 49 tests with p = 1.
  - Dropping them leaves the same 7 significant effects, but every q falls by 1.7×. For example clarify/s5 goes from 0.30 to 0.17.
- **Fix:** exclude tests where both arms are all zero from the correction, and report the number of tests (m). No compute.

**15. CI wording in the drilldown contradicts the significance verdict**
- **What goes wrong:**
  - 14 CIs exclude 0, but only 7 are significant (q of the other 7: 0.30–0.79).
  - "If it doesn't cross zero, the direction is solid" sits next to large q-values.
  - You can only reach those pages by typing a hash URL by hand.
- **Fix:** drop that sentence for non-significant effects, or show corrected intervals. No compute.

**16. One formatting choice is counted under several habits**
- **What goes wrong:** 86 of 93 bold hits are bullet lead-ins. One bolded list scores N list_item + N bold, which shows up as two "habits".
- **Fix:** count bold outside bullet lead-ins only, and group effects that occur in the same spots. No compute.

**17. The bundle lacks what a rerun needs**
- **What goes wrong:**
  - Not stored: max_tokens (defaults: server 4000, CLI 1500, Modal smoke 400), reasoning_effort (sent only if the `SPET_REASONING_EFFORT` env var is set), model revision, vLLM version, detector hash, finish_reason.
  - The `.spet_cache` key has no revision or date, so after a redeploy a rerun can silently mix old cached answers with new ones.
- **Fix:** add these fields to the bundle, the revision and date to the cache key, and finish_reason to each response. No compute.

**18. A truncated answer would be scored as a clean zero**
- **What goes wrong:**
  - Truncation is clean in this run: 0 empty answers, and all end in punctuation or an emoji.
  - But `providers.py:85` turns empty content into `""`, and finish_reason is not stored. An answer cut off at max_tokens would count as a valid zero-quirk answer.
- **Fix:** store finish_reason and exclude or flag cells where it is `length` or the content is empty. No compute.

**19. Where the prompt lands on vLLM**
- **What goes wrong:**
  - In vLLM 0.11.0 the API "system" message becomes a second system message next to vLLM's own, which carries a date. It does not become developer instructions.
  - This was not checked on the pinned vllm==0.18.1.
  - It does not bias the deltas within a single-day run.
- **Fix:** check on 0.18.1. Consider sending the prompt as role "developer", and record the date and version.

**20. Sections that repeat each other cannot be seen**
- **What goes wrong:**
  - Removing one section at a time gives zero credit to behaviour that two sections both produce, or that the probes already produce.
  - `shapley_values` is implemented but never called (`shapley: null`).
  - Only probe-induced redundancy is visible here: without s4, there are still 2.2 vs 2.4 questions per answer.
- **Fix:** add a "baseline" config with an empty or role-only prompt and report full vs baseline (one config). Offer pairwise removals or Shapley for small prompts (more runs).

## Fix plan

1. **[no compute]** Delete the "Likely" tier, or require q < 0.20. Use one `strength()` in `template.html` and `drilldown.template.html`, and keep non-significant effects out of the findings list and the chips. Resolves 1 and part of 15.
2. **[no compute]** Reword the UI:
   - "On these N questions…"
   - CI: "range of plausible average differences on these questions"
   - q: "expected share of false findings"
   - "No effect" becomes "Not detected (range X to Y)"
   - Note that sections are removed one at a time.
   - Drop "direction is solid" for non-significant effects.

   Resolves 3, 5 (wording), 6 (wording), 15.
3. **[no compute]** Choose the example pair closest to the average effect, show which probe it came from, and fix the "same seed / common random numbers" wording in `spet/schedule.py` and the templates. Resolves 4 and part of 7.
4. **[no compute]** Add a per-section "exercised?" check (floor or ceiling in both arms; numeric limit never approached) that shows "Not testable with these questions". Also warn when the probes are very short. Resolves 2.
5. **[no compute]** Add metrics recomputed from the stored text and run them through `section_effects`:
   - word and line count
   - "any question", "last sentence is a question", "any list"
   - clarify as yes/no

   Resolves 2 (length row), 9, 10.
6. **[no compute]** Flag likely mediators next to each effect:
   - more than 70% of spans inside list items;
   - the section also shifts list_item or length;
   - identity sections marked "context shift".

   Optionally show a length-adjusted delta. Resolves 9, 10, 12.
7. **[no compute]** Detector fixes:
   - broaden clarify ("could you let me know", "feel free to share…");
   - require Offer to be at the end of the answer;
   - split hedge (claim vs didn't understand) and apology (apology vs sympathy);
   - count bold outside bullet lead-ins only;
   - make the question regex skip "e.g."/"i.e.".

   Resolves 8, 11 (Offer), 13, 16.
8. **[no compute]** Statistics output:
   - per-probe deltas ("higher on 4 of 5");
   - a CI that resamples by probe;
   - the smallest detectable change per test;
   - all-zero tests excluded from the correction, with m reported.

   Resolves 5, 6, 7, 14.
9. **[no compute]** Bundle and cache:
   - add max_tokens, reasoning_effort, base_url host, model revision, vLLM version, detector hash, run date and per-response finish_reason;
   - put the revision and date in the cache key;
   - flag or exclude truncated or empty cells;
   - mark precision values with the model they were measured on.

   Resolves 17, 18, 11 (labelling), 19 (recording).
10. **[no compute, labelling only]** Label about 20 gpt-oss hits per detector and check the slot vLLM 0.18.1 puts the prompt in. Resolves 11, 19.
11. **[needs model runs]** Rerun with 15–20 concrete, varied probes (e.g. 15×3 instead of 5×8), including probes aimed at each section: a long how-to for the length cap, claim-heavy questions for uncertainty. Resolves 2, 5, 6, 7.
12. **[needs model runs]** Add a baseline config (empty or role-only prompt). Optionally swap in a neutral role for s0, and run pairwise or Shapley removals for prompts with 7 sections or fewer. Resolves 12, 20.

## Checked and dismissed

No finding was refuted outright. These parts of surviving findings were overstated and have been corrected above:

- "Follow-up Prompt's question effect is masked by bullets": not supported. s4 shows nothing on count, yes/no or ends-with-"?". The outside-bullet +0.25 result was chosen after the fact.
- "s4 is the only section that changes whether a question is asked": false. Without s0 it is 0.925 and without s1 0.95, vs 0.90 without s4.
- "The UI shows 100% precision badges": no badge is shown. The problem is that no warning is shown.
- "Step Formatting's question effect is false": the extra "?" sentences are real. The label "more inquisitive" is what misleads.
- "Users will see 'direction is solid' next to a high q": only reachable by typing a hash URL by hand.
- "Each significant effect holds on at most 4 of 5 probes": wrong for bold/s0, which holds on all 5.
- "The smoke bundle exercises the length rule": its prompt has no Length Constraint section. It only shows unconstrained answers run 370 words or more.
- "Most parentheticals in bullets are 'e.g.' examples": only 6 of 19 are. The rest are inline lists, but the bullet-line placement holds (17 of 19).
