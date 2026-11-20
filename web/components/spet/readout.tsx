"use client";

// A run with a readout: per part, does the model do what it says, and (only for "followed") is the part the reason.
// The overview comes with the page; a part's sentence, answers and numbers are fetched when it is opened.

import Link from "next/link";
import { useCallback, useMemo, useState } from "react";
import { renderAnswer } from "@/lib/markdown";
import { BUTTON, type Pair, type PartFile, type Reading, type RunView } from "@/lib/view";
import { Chevron } from "./note";
import { Shell, useShell, type Tone } from "./shell";

const BASE = process.env.NEXT_PUBLIC_BASE_PATH ?? "";
const TONE: Record<Reading, Tone> = {
  followed: "found",
  does_it: "plain",
  not_needed: "plain",
  partly_followed: "plain",
  not_followed: "strong",
  unclear: "quiet",
};
/** Answers longer than this start clamped, with one control that shows both in full. */
const LONG = 220;

const files = new Map<string, Promise<PartFile>>();
const got = new Map<string, PartFile>();
function loadPart(id: string, k: number): Promise<PartFile> {
  const key = `${id}/${k}`;
  let p = files.get(key);
  if (!p) {
    p = fetch(`${BASE}/views/${encodeURIComponent(id)}/${k}.json`).then((r) => {
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      return r.json() as Promise<PartFile>;
    });
    p.then((f) => got.set(key, f)).catch(() => files.delete(key));
    files.set(key, p);
  }
  return p;
}

export function Readout({ view, title, below }: { view: RunView; title: string; below?: React.ReactNode }) {
  const parts = view.parts;
  const prepare = useCallback((k: number) => loadPart(view.id, k), [view.id]);
  const prefetch = useCallback((k: number) => void loadPart(view.id, k).catch(() => {}), [view.id]);
  const button = useCallback(
    (k: number) => ({ text: BUTTON[parts[k].reading], tone: TONE[parts[k].reading], dot: parts[k].side }),
    [parts],
  );
  const focus = useCallback((k: number) => <PartView key={k} id={view.id} k={k} parts={parts} />, [view.id, parts]);
  const head = useMemo(
    () => (
      <>
        <h1>{title}</h1>
        <p className="lede">{view.lede}</p>
      </>
    ),
    [title, view.lede],
  );
  return <Shell parts={parts} button={button} focus={focus} prepare={prepare} prefetch={prefetch} head={head} below={below} />;
}

function PartView({ id, k, parts }: { id: string; k: number; parts: RunView["parts"] }) {
  const f = got.get(`${id}/${k}`);
  const { toggle, go } = useShell();
  const [deep, setDeep] = useState(false);
  const [drew, setDrew] = useState(false);
  const [also, setAlso] = useState(false);
  const [whole, setWhole] = useState(false);
  if (!f) return <p className="empty">This part&rsquo;s answers did not load. Reload the page to try again.</p>;

  const ex = also && f.side?.pair ? f.side.pair : f.example;
  return (
    <div className="detail-in">
      <p className="sentence" data-k="s">{f.sentence}</p>
      {f.checks.length > 0 && (
        <ul className="lines" data-k="lines">
          {f.checks.filter((c) => c.shown).map((c) => <li key={c.id}>{c.line}</li>)}
        </ul>
      )}
      {!also && f.example && <PairView pair={f.example} whole={whole} />}
      {f.side && (
        <div className="also" data-k="also">
          <button type="button" className="also-btn" aria-expanded={also} onClick={() => toggle(() => { setAlso((a) => !a); setDrew(false); setWhole(false); })}>
            <span className="dot" aria-hidden="true" />
            <span className="t">It also changes something it never mentions</span>
            <Chevron />
          </button>
          {also && (
            <div className="also-in" data-k="also-in">
              <p className="sentence">{f.side.sentence}</p>
              {f.side.pair && <PairView pair={f.side.pair} whole={whole} about="a question about something else" />}
            </div>
          )}
        </div>
      )}
      <div className="foot" data-k="foot">
        {isLong(ex) && (
          <button type="button" className="more" aria-expanded={whole} onClick={() => toggle(() => setWhole((w) => !w))}>
            {whole ? "Shorten the answers" : "Show the whole answers"}
          </button>
        )}
        <button type="button" className="more" aria-expanded={deep} aria-controls={`deep-${k}`} onClick={() => toggle(() => setDeep((d) => !d))}>
          {deep ? "Less detail" : "More detail"}
        </button>
        {f.drew && ex === f.example && (
          <button type="button" className="more" aria-expanded={drew} aria-controls={`drew-${k}`} onClick={() => toggle(() => setDrew((d) => !d))}>
            {drew ? "Hide what it drew on" : "What it drew on"}
          </button>
        )}
      </div>
      {drew && f.drew && ex === f.example && (
        <div data-k="drew" id={`drew-${k}`}>
          {f.drew.stoodOut ? (
            <>
              <p className="caption">Where the model looked most while reasoning about this question, in separate samples; not proof of cause.</p>
              <ul className="drew">
                {f.drew.rows.map((r) => (
                  <li key={r.k}>
                    <button type="button" className={`d${r.tint}`} disabled={r.k === k} onClick={() => go(r.k)} title={r.k === k ? undefined : `Open part ${r.k + 1}`}>
                      <span className="n">{r.k + 1}</span>
                      <span className="lbl">
                        {parts[r.k].label}
                        {r.k === k && <em> (this part)</em>}
                      </span>
                      <span className="first">{r.first}</span>
                    </button>
                  </li>
                ))}
              </ul>
            </>
          ) : (
            <p className="caption">Nothing stood out: no part drew much more of the model&rsquo;s attention than usual.</p>
          )}
        </div>
      )}
      {deep && (
        <div className="deep" data-k="deep" id={`deep-${k}`}>
          {f.checks.length > 0 && (
            <table>
              <thead>
                <tr>
                  <th scope="col">Statement the judge read</th>
                  <th scope="col">Holds with it</th>
                  <th scope="col">Without</th>
                </tr>
              </thead>
              <tbody>
                {f.checks.map((c) => (
                  <tr key={c.id}>
                    <td>
                      {c.statement}
                      {c.opposite && <span className="flag">Opposite of what the part asks.</span>}
                    </td>
                    <td className="n">{c.withPct}</td>
                    <td className="n">{c.withoutPct}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
          {f.basis.map((x) => <p key={x} className="basis">{x}</p>)}
          {f.hidden > 0 && <p className="basis">{f.hidden} more check{f.hidden === 1 ? "" : "s"} not shown.</p>}
          <p className="basis"><Link href="/method/#measured" className="link">How this is measured</Link></p>
        </div>
      )}
    </div>
  );
}

const isLong = (p: Pair | null | undefined) => !!p && (p.with.words > LONG || p.without.words > LONG);

function PairView({ pair, whole, about = "one of its answers" }: { pair: Pair; whole: boolean; about?: string }) {
  const side = (s: "with" | "without") => {
    const a = pair[s];
    return (
      <section className={`answer ${s}`} aria-label={s === "with" ? "With this part" : "Without it"}>
        <h3>
          {s === "with" ? "With this part" : "Without it"}
          <span>{a.words.toLocaleString("en")} {a.words === 1 ? "word" : "words"}{a.cut ? ", cut off" : ""}</span>
        </h3>
        <div className={`body${a.words > LONG && !whole ? " clamped" : ""}`} dangerouslySetInnerHTML={{ __html: renderAnswer(a.text, [], null) }} />
      </section>
    );
  };
  return (
    <>
      <p className="asked" data-k="asked">
        Asked &ldquo;{pair.question}&rdquo;{pair.from === "confirmation" ? " (new question)" : ""}, {about}:
      </p>
      <div className="pair" data-k="pair">
        {side("with")}
        {side("without")}
      </div>
      {pair.note && <p className="author-note" data-k="note">Author&rsquo;s note: {pair.note}</p>}
    </>
  );
}
