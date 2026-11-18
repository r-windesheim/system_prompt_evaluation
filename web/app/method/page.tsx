import type { Metadata } from "next";
import Link from "next/link";
import { HOME_RUN_ID } from "@/lib/parts";
import { loadRun } from "@/lib/runs.server";
import { REPO_URL } from "@/lib/site";

export const metadata: Metadata = { title: "Method" };

const SMALL = ["no", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten", "eleven", "twelve"];
const word = (n: number) => SMALL[n] ?? String(n);
const num = (n: number) => n.toLocaleString("en");

/** Every number on this page comes from the home run's bundle, at build time. */
function facts() {
  const b = loadRun(HOME_RUN_ID);
  const audit = b.readout?.audit;
  const intended = (ids: string[] = []) => ids.filter((id) => /\.i\d+$/.test(id)).length;
  const rejected = intended(audit?.invalid);
  const written = rejected + intended(audit?.valid);
  const authoredParts = new Set((b.authored?.statements ?? []).map((s) => s.section)).size;
  const parts = b.readout?.parts ?? [];
  const oneCheck = parts.filter((p) => (p.checks?.length ?? 0) === 1).length;
  const followed = parts.filter((p) => p.reading === "followed").map((p) => b.sections.find((s) => s.id === p.section)?.label ?? "");
  return {
    model: b.meta.model.split("/").pop() ?? b.meta.model,
    nParts: b.sections.length,
    nQ: b.meta.queries.length,
    perPart: Math.round(b.meta.queries.length / b.sections.length),
    nA: b.responses.length,
    cQ: b.confirmation?.queries.length ?? 0,
    cA: b.confirmation?.responses?.length ?? 0,
    written,
    rejected,
    authoredParts,
    oneCheck,
    followed,
  };
}

export default function Method() {
  const f = facts();
  return (
    <div className="page col">
      <h1>How it works</h1>
      <article className="article">
        <p>
          SPET takes one part of a system prompt out at a time, asks the model the same questions again, and compares the
          answers. For each part it asks two things: does the model do what the part says, and is the part the reason?
        </p>
        <p>
          Only &ldquo;Yes, because of this part&rdquo; claims a cause. It needs a difference with and without the part that
          a second test, on new questions, confirms. In this run that is {f.followed.length === 1 ? "one part" : `${word(f.followed.length)} parts`}:{" "}
          {f.followed.join(", ")}.
        </p>

        <h2 id="measured">How this is measured</h2>
        <p>
          The first run asks {num(f.nQ)} questions, {f.perPart} written for each part, and collects {num(f.nA)} answers. A
          judge reads each answer and says whether a statement about it holds. The share that does, with the part and
          without it, gives the two numbers for a check.
        </p>
        <p>
          Parts whose difference looks real are tested once more, on {num(f.cQ)} new questions and {num(f.cA)} new
          answers, with the rule for what counts fixed beforehand.
        </p>
        <p>
          p is the chance of a difference at least this large if the part changed nothing. &ldquo;No measurable
          difference&rdquo; means p was 0.05 or more. Each share also has a range, computed over questions, that says how
          far it could move with other questions; it is kept in the data.
        </p>

        <h2 id="judge">The judge</h2>
        <p>
          The judge is the same small model, {f.model}. It reads one answer at a time, without knowing which prompt wrote
          it. Its known weakness: it often says no where a statement does not apply to the question. That makes
          &ldquo;No&rdquo; and &ldquo;with or without this part&rdquo; less certain than &ldquo;Yes, because of this
          part&rdquo;.
        </p>

        <h2 id="checks">Why some checks are left out</h2>
        <p>
          The judge also wrote the statements, so a larger model, Claude Opus, reviewed them: {f.rejected} of {f.written}{" "}
          were rejected, for joining two claims, for referring to things the judge never sees, or because the judge&rsquo;s
          verdicts did not hold up in a spot check. For {word(f.authoredParts)} parts, Claude Opus wrote new statements
          from the part&rsquo;s text alone, before any answer was judged with them. Checks the judge was unsteady on are
          left out too, and checks that measure the same thing share one line.
        </p>
        <p>
          Each check has a short name, written by the judge model from its statement and checked by fixed rules. More
          detail shows the statement itself.
        </p>

        <h2 id="examples">The example answers</h2>
        <p>
          Each part shows one pair of answers, picked by a fixed rule: a typical pair for its first check, or for a
          confirmed check a pair that shows the difference. It illustrates; it is not the evidence. A pair can show a
          difference that the checks did not measure.
        </p>

        <h2 id="drew">What it drew on</h2>
        <p>
          A separate run recorded where the model looked in the prompt while reasoning about each question. It is a hint,
          not evidence that a part caused anything.
        </p>

        <h2 id="limits">Known limits</h2>
        <ul>
          <li>{cap(word(f.oneCheck))} of the {f.nParts} parts rest on a single check.</li>
          <li>The results describe {f.model} on these questions. Claude itself may behave differently.</li>
          <li>Taking out one part at a time misses parts that do the same job together.</li>
        </ul>

        <p className="quiet" style={{ marginTop: 40 }}>
          <Link href="/" className="link">See the results</Link>. Source, tests and the audit:{" "}
          <a className="link" href={REPO_URL}>github.com/r-windesheim/system_prompt_evaluation</a>
        </p>
      </article>
    </div>
  );
}

const cap = (s: string) => s.charAt(0).toUpperCase() + s.slice(1);
