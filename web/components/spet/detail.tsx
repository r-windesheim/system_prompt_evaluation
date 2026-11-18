"use client";

import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import { renderAnswer } from "@/lib/markdown";
import { instant, unfold } from "@/lib/motion";
import { wordCount, type Run } from "@/lib/run";

/** An opened part: one plain sentence, one real answer with the part beside one without it, and "More detail". */
export function Detail({
  run, k, deep, onDeep, onClose, id,
}: { run: Run; k: number; deep: boolean; onDeep: () => void; onClose: () => void; id: string }) {
  const reduce = useReducedMotion();
  const t = reduce ? instant : unfold;
  const ex = run.example(k);
  const main = run.note(k).main;
  const hl = main ? run.highlightFor(main.detector) : null;
  const a = ex ? run.response(null, ex.q, ex.s) : undefined;
  const z = ex ? run.response(k, ex.q, ex.s) : undefined;
  const d = run.detail(k);

  return (
    <motion.div
      className="detail"
      id={id}
      initial={{ height: 0, opacity: 0 }}
      animate={{ height: "auto", opacity: 1 }}
      exit={{ height: 0, opacity: 0 }}
      transition={t}
      style={{ overflow: "hidden" }}
    >
      <div className="detail-in">
        <p className="sentence">{run.sentence(k)}</p>
        {ex && a && z && (
          <>
            <p className="asked">Asked &ldquo;{run.meta.queries[ex.q]}&rdquo;, one of its answers:</p>
            <div className="pair">
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
        <div className="foot">
          <button type="button" className="more" aria-expanded={deep} aria-controls={`${id}-more`} onClick={onDeep}>
            {deep ? "Less detail" : "More detail"}
          </button>
          <button type="button" className="close" onClick={onClose}>Close</button>
        </div>
        <AnimatePresence initial={false}>
          {deep && (
            <motion.div
              key="deep"
              id={`${id}-more`}
              initial={{ height: 0, opacity: 0 }}
              animate={{ height: "auto", opacity: 1 }}
              exit={{ height: 0, opacity: 0 }}
              transition={t}
              style={{ overflow: "hidden" }}
            >
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
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </motion.div>
  );
}

const cap = (s: string) => s.charAt(0).toUpperCase() + s.slice(1);
