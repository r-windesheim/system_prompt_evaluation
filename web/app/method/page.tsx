import type { Metadata } from "next";
import { REPO_URL } from "@/lib/site";

export const metadata: Metadata = { title: "Method" };

const H = ({ children }: { children: React.ReactNode }) => (
  <h2 className="mt-12 text-[19px] font-semibold tracking-tight">{children}</h2>
);
const P = ({ children }: { children: React.ReactNode }) => <p className="mt-3">{children}</p>;

export default function Method() {
  return (
    <article className="max-w-[66ch] pt-10 text-[15.5px] leading-[1.7]">
      <h1 className="text-[34px] leading-tight font-semibold tracking-[-0.02em]">How SPET attributes a quirk</h1>
      <P>
        A system prompt is a list of instructions, and a model&apos;s habits come out of all of them at once. SPET asks a
        narrower question that can be measured: if you take one section out and replay the exact same conversations,
        what changes?
      </P>

      <H>1. Split, then leave one out</H>
      <P>
        The prompt is split into sections. For a prompt with <em>k</em> sections SPET builds <em>k</em> + 1
        configurations: the full prompt, and the prompt with each section removed in turn.
      </P>

      <H>2. Replay the same conversations</H>
      <P>
        Every configuration answers the same user messages the same number of times, so answers can be compared in
        pairs: message 2, sample 5 with the full prompt against message 2, sample 5 without section 3. Each pair shares
        a sampling seed for reproducibility. That doesn&apos;t make the two answers twins, because once the prompts
        differ the sampling diverges. The seed goes in the request, never in the prompt text. An earlier version
        appended a cache-busting tag to the user message, and the model dutifully answered the tag.
      </P>

      <H>3. Count, don&apos;t normalise</H>
      <P>
        Detectors mark spans in each response: apologies, hedges, list items, questions back to the user and so on.
        The quantity compared is <strong>matches per response</strong>. Per-100-words rates looked natural but were
        wrong: a section that makes answers longer dilutes every other quirk&apos;s rate, so it appears to
        &ldquo;reduce&rdquo; hedging it never touched. The planted-instruction test caught this.
      </P>

      <H>4. Paired effects with honest uncertainty</H>
      <P>
        For each quirk and section, the effect is the mean paired difference, with minus without. The interval is a
        95% bootstrap over paired conversations. The p-value comes from a sign-flip permutation test (exact up to 16 pairs, 10,000 random flips above that). Because
        one run tests every quirk against every section, p-values are corrected with Benjamini–Hochberg, and an effect
        counts as significant only at q &lt; 0.05. Every section is reported, not just the largest.
      </P>

      <H>5. Checked against known answers</H>
      <P>
        The test suite runs the full pipeline against a stub model whose behaviours are switched on by specific
        sentences. The run must flag exactly those section–quirk pairs and nothing else, across five seeds. The
        synthetic run on the front page is that setup.
      </P>
      <P>
        Detector precision was audited on 262 hits sampled from real gpt-4o-mini responses and labelled by an independent LLM annotator: a separate Claude agent that never saw the detector code. A person has not
        checked the labels. Three detectors were wrong every time and were rewritten. Rewritten detectors, and detectors
        with too few hits, show as &ldquo;precision unmeasured&rdquo; until a fresh sample is labelled.
      </P>

      <H>What it does not claim</H>
      <ul className="mt-3 list-disc pl-5 marker:text-graphite">
        <li>Underlined phrases are detector matches. They are not evidence that a particular section produced that phrase.</li>
        <li>Leave-one-out misses interactions. If two sections each cause a habit on their own, removing either one changes little. Shapley values over subsets would capture that. The estimator exists, but running subset configurations isn&apos;t wired up yet.</li>
        <li>Effects describe these user messages on this model. They may not transfer to other conversations.</li>
      </ul>

      <H>Related work</H>
      <P>
        Context ablation and attribution are established: Captum&apos;s LLM attribution (2023), ContextCite (2024) and
        TokenSHAP (2024) attribute outputs to parts of the input. SPET&apos;s contribution is the combination:
        section-level system-prompt ablation, a curated scorecard of stylistic quirks, paired statistics, and a viewer
        that keeps observation and attribution apart.
      </P>

      <p className="mt-12 text-[14px] text-graphite">
        Source, tests and the detector audit:{" "}
        <a className="underline underline-offset-4" href={REPO_URL}>
          github.com/r-windesheim/system_prompt_evaluation
        </a>
      </p>
    </article>
  );
}
