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
          A system prompt is a list of instructions. SPET takes one part out at a time, asks the model the same questions
          again, and compares the answers with the part and without it.
        </p>

        <h2>Two questions per part</h2>
        <p>
          <strong>Does the model do what the part says?</strong> This is how often answers with the whole prompt do it:
          mostly, sometimes or rarely.
        </p>
        <p>
          <strong>Is the part the reason?</strong> Only if answers without the part do it measurably less, and a second
          test confirms it. A model can do something without being told, so doing it is not proof that the part is why.
        </p>

        <h2>A first run, then a second test</h2>
        <p>
          The first run asks {num(f.nQ)} questions, {f.perPart} written for each of the {f.nParts} parts, and collects{" "}
          {num(f.nA)} answers. It points to the parts worth testing again.
        </p>
        <p>
          Those are tested once more, on {num(f.cQ)} new questions and {num(f.cA)} new answers, with the rule for what
          counts fixed beforehand. Only a difference that shows up again there is called &ldquo;followed&rdquo;. In this run
          that is {f.followed.length === 1 ? "one part" : `${word(f.followed.length)} parts`}: {f.followed.join(", ")}.
        </p>

        <h2>Who reads the answers</h2>
        <p>
          A judge reads each answer on its own, without knowing which prompt wrote it, and says whether a statement holds,
          such as &ldquo;the answer says it cannot open the link&rdquo;. The judge is the same small model, {f.model}.
        </p>
        <p>
          The judge also wrote the statements, so a larger model, Claude Opus, reviewed them: {f.rejected} of its{" "}
          {f.written} were rejected, for joining two claims, for referring to things the judge never sees, or because its
          verdicts did not hold up in a spot check. For {word(f.authoredParts)} parts, Claude Opus wrote new statements from
          the part&rsquo;s text alone, without seeing any answers, before the judge used them.
        </p>

        <h2>What it drew on</h2>
        <p>
          A separate run recorded where the model looked in the prompt while reasoning about each question. It is shown as a
          hint beside an example. It is not evidence that a part caused anything.
        </p>

        <h2>Known limits</h2>
        <ul>
          <li>
            The judge often answers no where a statement does not apply to the question. Readings that rest on how often it
            says yes, such as &ldquo;not followed&rdquo;, are less certain than &ldquo;followed&rdquo;.
          </li>
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
