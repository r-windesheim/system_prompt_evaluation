"use client";

import { useState } from "react";
import { renderAnswer } from "@/lib/markdown";
import { wordCount, type Run } from "@/lib/run";
import { useShell } from "./shell";

/** An opened part of a habit run: one plain sentence, one real answer with the part beside one without it, and "More detail". */
export function Detail({ run, k }: { run: Run; k: number }) {
  const { toggle } = useShell();
  const [deep, setDeep] = useState(false);
  const ex = run.example(k);
  const main = run.note(k).main;
  const hl = main ? run.highlightFor(main.detector) : null;
  const a = ex ? run.response(null, ex.q, ex.s) : undefined;
  const z = ex ? run.response(k, ex.q, ex.s) : undefined;
  const d = run.detail(k);
  const id = `detail-${k + 1}`;

  return (
    <div className="detail-in" id={id}>
      <p className="sentence" data-k="s">{run.sentence(k)}</p>
      {ex && a && z && (
        <>
          <p className="asked" data-k="asked">Asked &ldquo;{run.meta.queries[ex.q]}&rdquo;, one of its answers:</p>
          <div className="pair" data-k="pair">
            <section className="answer with" aria-label="With this part">
              <h3>With this part <span>{wordCount(a.text)} words</span></h3>
              <div className="body" dangerouslySetInnerHTML={{ __html: renderAnswer(a.text, a.spans, hl) }} />
            </section>
            <section className="answer without" aria-label="Without it">
              <h3>Without it <span>{wordCount(z.text)} words</span></h3>
              <div className="body" dangerouslySetInnerHTML={{ __html: renderAnswer(z.text, z.spans, hl) }} />
            </section>
          </div>
        </>
      )}
      <div className="foot" data-k="foot">
        <button type="button" className="more" aria-expanded={deep} aria-controls={`${id}-more`} onClick={() => toggle(() => setDeep((v) => !v))}>
          {deep ? "Less detail" : "More detail"}
        </button>
      </div>
      {deep && (
        <div data-k="deep" id={`${id}-more`}>
          <div className="deep">
            {d.rows.length > 0 && (
              <table>
                <thead>
                  <tr><th scope="col"><span className="sr-only">Habit</span></th><th scope="col">with it</th><th scope="col">without</th></tr>
                </thead>
                <tbody>
                  {d.rows.map((r) => (
                    <tr key={r.label}>
                      <td>
                        {r.label}
                        {r.flags.length > 0 && <span className="flag">{r.flags.join(", ")}</span>}
                      </td>
                      <td>{r.withIt}</td>
                      <td>{r.without}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
            {d.paras.map((p) => <p key={p}>{p}</p>)}
            {d.flagNotes.map((f) => (
              <p key={f.short} className="caveat">{cap(f.short)}: {f.text}</p>
            ))}
            {d.warnings.map((w) => <p key={w}>{w}</p>)}
          </div>
        </div>
      )}
    </div>
  );
}

const cap = (s: string) => s.charAt(0).toUpperCase() + s.slice(1);
