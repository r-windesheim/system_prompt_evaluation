"use client";

import { motion, useReducedMotion } from "motion/react";
import Link from "next/link";
import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import { API, api, apiBundleUrl, hasApi, loadBundle, loadStatic, runPath, type RunStatus, type SectionDraft } from "@/lib/api";
import { arrive as arriveAt, instant } from "@/lib/motion";
import {
  atomize, EXAMPLE_ID, groupsOf, labelFrom, ORIGINAL_PROBES, sameSections, sameText, sectionsOf, splitLocally, type Split,
} from "@/lib/parts";
import { indexRun } from "@/lib/run";
import type { RunBundle } from "@/lib/types";
import { Detail } from "./detail";
import { Shell, type ShellButton } from "./shell";

export type ExampleInfo = {
  sections: SectionDraft[];
  queries: string[];
  n: number;
  /** samples where a question was not written for the removed part; null = n everywhere */
  nUntargeted?: number | null;
  model: string;
  created_at: string;
};
type Props =
  /** `onBack`: return to the recorded run the home page opens on */
  | { mode: "home"; example: ExampleInfo; onBack?: () => void }
  /** `recorded`: the run is in the static export, so load it from there and never from the API */
  | { mode: "saved"; id: string; seed?: SectionDraft[]; recorded?: boolean };

type Phase = "edit" | "parts" | "running" | "result";
type Source = "example" | "live" | "saved";
type Model = "checking" | "yes" | "no";

const BASE = process.env.NEXT_PUBLIC_BASE_PATH ?? "";
const STEP_MS = 760;
const shortModel = (m: string) => m.split("/").pop() ?? m;
const dateOf = (iso: string) => new Date(iso).toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" });

export function Tool(props: Props) {
  const reduce = useReducedMotion();
  const arrive = (j: number) => (reduce ? instant : arriveAt(j));
  const home = props.mode === "home";
  const ex = home ? props.example : null;
  const exText = useMemo(() => (ex ? ex.sections.map((s) => s.text).join("\n\n") : ""), [ex]);
  const exSplit = useMemo(() => (ex ? atomize(ex.sections) : null), [ex]);

  const [phase, setPhase] = useState<Phase>(home ? "edit" : "result");
  const [text, setText] = useState(exText);
  const [split, setSplit] = useState<Split | null>(null);
  const [exBundle, setExBundle] = useState<RunBundle | null>(null);
  const [bundle, setBundle] = useState<RunBundle | null>(null);
  const [source, setSource] = useState<Source>(home ? "example" : "saved");
  const [step, setStep] = useState(-1);
  const [status, setStatus] = useState<RunStatus | null>(null);
  const [model, setModel] = useState<Model>(hasApi ? "checking" : "no");
  const [modelName, setModelName] = useState<string | null>(null);
  const [concrete, setConcrete] = useState<string[]>([]);
  const [queries, setQueries] = useState<string[]>(ex ? ex.queries : ORIGINAL_PROBES);
  const [n, setN] = useState(ex ? ex.n : 8);
  const [nText, setNText] = useState(String(ex ? ex.n : 8));
  const [showQs, setShowQs] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loadErr, setLoadErr] = useState<string | null>(null);
  const ta = useRef<HTMLTextAreaElement>(null);

  const run = useMemo(() => (bundle ? indexRun(bundle) : null), [bundle]);
  const [roomy, setRoomy] = useState(!home);
  useEffect(() => {
    if (phase === "edit") return setRoomy(false);
    const f = requestAnimationFrame(() => setRoomy(true));
    return () => cancelAnimationFrame(f);
  }, [phase]);
  const groups = useMemo(() => (split ? groupsOf(split) : []), [split]);
  const drafts = useMemo(() => (split ? sectionsOf(split) : []), [split]);
  const changed = home && !sameText(text, exText);
  const isExample = !!ex && !!split && sameSections(drafts, ex.sections);
  const cleanQs = queries.map((q) => q.trim()).filter(Boolean);
  const sameOpts = !!ex && cleanQs.join("\n") === ex.queries.join("\n") && n === ex.n;
  const replay = isExample && sameOpts;
  const canLive = model === "yes" && groups.length >= 2 && cleanQs.length > 0;

  // ---- loading -------------------------------------------------------------
  useEffect(() => {
    if (!home) return;
    loadStatic<RunBundle>(EXAMPLE_ID).then(setExBundle).catch((e: Error) => setLoadErr(e.message));
  }, [home]);

  useEffect(() => {
    if (!home || !hasApi) return;
    api
      .health()
      .then((h) => {
        setModel(h.ok && h.base_url && h.model ? "yes" : "no");
        setModelName(h.model);
        setConcrete(h.default_queries ?? []);
      })
      .catch(() => setModel("no"));
  }, [home]);

  const savedId = props.mode === "saved" ? props.id : null;
  const recorded = props.mode === "saved" && !!props.recorded;
  useEffect(() => {
    if (!savedId) return;
    let live = true;
    (recorded ? loadStatic<RunBundle>(savedId) : loadBundle<RunBundle>(savedId))
      .then((b) => live && setBundle(b))
      .catch((e: Error) => live && setLoadErr(e.message));
    return () => {
      live = false;
    };
  }, [savedId, recorded]);

  // ---- the textarea grows with its text ---------------------------------------
  useLayoutEffect(() => {
    const el = ta.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${el.scrollHeight}px`;
  }, [text, phase]);

  // ---- actions --------------------------------------------------------------
  async function doSplit() {
    if (!text.trim()) return;
    setError(null);
    if (home && !changed && exSplit) {
      setSplit(exSplit);
      setPhase("parts");
      return;
    }
    if (model === "yes") {
      setBusy(true);
      try {
        const r = await api.split(text);
        setSplit(atomize(r.sections));
        setPhase("parts");
      } catch (e) {
        setError(`Splitting failed: ${(e as Error).message}`);
      } finally {
        setBusy(false);
      }
      return;
    }
    setSplit(splitLocally(text));
    setPhase("parts");
  }

  async function doTest() {
    setError(null);
    if (replay) {
      setSource("example");
      setStep(-1);
      setPhase("running");
      return;
    }
    if (!canLive) return;
    setBusy(true);
    try {
      const r = await api.start({
        title: drafts[0] ? labelFrom(text) : "Untitled prompt",
        sections: drafts,
        queries: cleanQs,
        n_per_query: n,
        temperature: 0.7,
      });
      setSource("live");
      setStatus({ id: r.id, state: "running", done: 0, total: r.total });
      setPhase("running");
    } catch (e) {
      setError(`The run did not start: ${(e as Error).message}`);
    } finally {
      setBusy(false);
    }
  }

  const restore = () => {
    setText(exText);
    if (phase === "parts" && exSplit) setSplit(exSplit);
    setError(null);
  };
  const clear = () => {
    setText("");
    requestAnimationFrame(() => ta.current?.focus());
  };
  const startOver = () => {
    setStep(-1);
    setStatus(null);
    if (source === "live") window.history.replaceState(window.history.state, "", `${BASE}/`);
    else window.history.replaceState(window.history.state, "", window.location.pathname + window.location.search);
    setPhase("edit");
  };
  const toggleBreak = (i: number) => setSplit((s) => (s ? { ...s, breaks: s.breaks.map((v, j) => (j === i ? !v : v)) } : s));

  // ---- running: replay the example, or follow the live run ----------------------
  useEffect(() => {
    if (phase !== "running" || source !== "example") return;
    if (step >= groups.length) {
      if (!exBundle) return; // still loading; the effect re-runs when it arrives
      setBundle(exBundle);
      setPhase("result");
      return;
    }
    const t = setTimeout(() => setStep((s) => s + 1), STEP_MS);
    return () => clearTimeout(t);
  }, [phase, source, step, groups.length, exBundle]);

  const liveId = status?.id;
  const liveRunning = phase === "running" && source === "live" && status?.state === "running";
  useEffect(() => {
    if (!liveRunning || !liveId) return;
    let stop = false;
    const t = setInterval(async () => {
      try {
        const s = await api.status(liveId);
        if (stop) return;
        setStatus(s);
        if (s.state === "done") {
          stop = true;
          clearInterval(t);
          const r = await fetch(apiBundleUrl(liveId));
          if (!r.ok) throw new Error(`HTTP ${r.status}`);
          setBundle(await r.json());
          setPhase("result");
          window.history.replaceState(window.history.state, "", runPath(liveId));
        } else if (s.state === "error") {
          stop = true;
          clearInterval(t);
          setError(`The run stopped: ${s.error ?? "unknown error"}`);
          setPhase("parts");
        }
      } catch (e) {
        setError((e as Error).message);
      }
    }, 400);
    return () => {
      stop = true;
      clearInterval(t);
    };
  }, [liveRunning, liveId]);

  // per part: 0 = not started, (0,1) = being tested, 1 = done
  const frac = (cfg: string) => {
    if (source === "example") return cfg === "full" ? (step >= 0 ? 1 : 0.5) : 0;
    const tot = status?.per_config_total ?? 0;
    return tot ? (status?.per_config?.[cfg] ?? 0) / tot : 0;
  };
  const partState = (gi: number): "idle" | "out" | "done" => {
    if (phase !== "running") return "idle";
    if (source === "example") return gi === step ? "out" : gi < step ? "done" : "idle";
    const f = frac(`without_${gi}`);
    return f >= 1 ? "done" : f > 0 ? "out" : "idle";
  };
  const progress = (() => {
    if (phase !== "running") return 0;
    if (source === "example") return Math.min(1, (step + 1.5) / (groups.length + 1));
    return status?.total ? (status.done ?? 0) / status.total : 0;
  })();

  // ---- words -------------------------------------------------------------------
  const nParts = groups.length;
  let lede: string;
  if (phase === "edit") lede = "Paste a system prompt, or try this example.";
  else if (phase === "parts") lede = "Each part will be tested on its own. Click a line to merge two parts, or a gap to split.";
  else if (phase === "running") {
    let cur = -1;
    if (source === "example") cur = step;
    else for (let i = 0; i < nParts && cur < 0; i++) if (partState(i) === "out") cur = i;
    lede =
      cur < 0
        ? "Asking the questions with the whole prompt first."
        : `Testing part ${cur + 1} of ${nParts}: the same questions, with this part removed.`;
  } else if (run?.meta.fixture) lede = "A synthetic run: a stand-in model with planted habits. Click a part to see the answers.";
  else lede = home ? "Here is what each part changes. Click one to see the answers." : "Here is what each part of this prompt changes. Click one to see the answers.";

  // ---- rows ----------------------------------------------------------------------
  let rows: React.ReactNode;
  if (phase === "edit") {
    rows = (
      <div className="row">
        <span className="num" aria-hidden="true" />
        <div className="text">
          <label htmlFor="prompt" className="sr-only">System prompt</label>
          <textarea
            id="prompt"
            ref={ta}
            className="prose"
            value={text}
            spellCheck={false}
            placeholder="Paste a system prompt here. Leave a blank line between the parts you want tested separately."
            onChange={(e) => setText(e.target.value)}
          />
        </div>
        <div className="note">
          {!changed ? (
            <>
              <span className="label">The example</span>
              <button type="button" className="link note-link" onClick={clear}>Clear it to paste your own</button>
            </>
          ) : model === "no" ? (
            <motion.span className="aside-block" initial={reduce ? false : { opacity: 0 }} animate={{ opacity: 1 }}>
              <span className="says status">Without a model connected, only the example can be tested.</span>
              <button type="button" className="link note-link" onClick={restore}>Restore the example</button>
            </motion.span>
          ) : (
            <>
              <span className="label">Your prompt</span>
              <button type="button" className="link note-link" onClick={restore}>Restore the example</button>
            </>
          )}
        </div>
      </div>
    );
  } else if ((phase === "parts" || phase === "running") && split) {
    const editing = phase === "parts";
    rows = groups.map((g, gi) => {
      const st = partState(gi);
      const label = (split.labels[g[0]] ?? "").trim() || labelFrom(split.atoms[g[0]]);
      return [
        gi > 0 && (
          <div className="gaprow" key={`g${g[0] - 1}`}>
            <Gap i={g[0] - 1} on editing={editing} onToggle={toggleBreak} draw={editing} />
          </div>
        ),
        <div className={`row ${st}`} key={`p${g[0]}`}>
          <span className="num">{gi + 1}</span>
          <div className="text">
            {g.map((ai, j) => [
              j > 0 && <Gap key={`i${ai - 1}`} i={ai - 1} on={false} editing={editing} onToggle={toggleBreak} draw={false} />,
              <span key={`a${ai}`} className="para prose"><span className="strike">{split.atoms[ai]}</span></span>,
            ])}
          </div>
          <div className="note">
            {editing ? (
              <motion.span className="label" initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={arrive(gi)}>{label}</motion.span>
            ) : st === "out" ? (
              <>
                <span className="says status">removed, asking again</span>
                {source === "live" ? (
                  <span className="bar"><i style={{ width: `${Math.round(frac(`without_${gi}`) * 100)}%` }} /></span>
                ) : (
                  <span className="bar busy"><i /></span>
                )}
              </>
            ) : st === "done" ? (
              <span className="says done">tested</span>
            ) : null}
          </div>
        </div>,
      ];
    });
  } else {
    rows = (
      <div className="row" aria-busy="true">
        <span className="num" />
        <div className="text">
          <span className="para prose" style={{ color: "var(--faint)" }}>{loadErr ? `The run didn’t load (${loadErr}). Reload the page to try again.` : "Loading the run…"}</span>
        </div>
      </div>
    );
  }

  // ---- under the sheet ----------------------------------------------------------
  const qn = (model === "yes" ? cleanQs : ex?.queries ?? cleanQs).length;
  let below: React.ReactNode = null;
  if (phase === "edit") {
    below = (
      <div className="actions">
        <button type="button" className="btn" onClick={doSplit} disabled={!text.trim() || busy}>
          {busy ? "Splitting…" : "Split into parts"}
        </button>
        {props.mode === "home" && props.onBack && (
          <button type="button" className="link" onClick={props.onBack}>Back to the Claude prompt</button>
        )}
      </div>
    );
  } else if (phase === "parts") {
    const blocked = !replay && model !== "yes" && model !== "checking";
    below = (
      <>
        <div className="actions">
          <button type="button" className="btn" onClick={doTest} disabled={busy || !(replay || canLive)}>
            {busy ? "Starting…" : `Test ${nParts} part${nParts === 1 ? "" : "s"}`}
          </button>
          <button type="button" className="link" onClick={() => { setPhase("edit"); setError(null); }}>Edit the text</button>
        </div>
        {blocked && !isExample ? (
          <p className="quiet">
            This page has a saved result for the example&rsquo;s {ex?.sections.length} parts only. Testing anything else needs a model
            connected. <button type="button" className="link" onClick={restore}>Restore the example</button>
          </p>
        ) : model === "yes" && nParts < 2 ? (
          <p className="quiet">Add at least one break: with a single part there is nothing to compare.</p>
        ) : (
          <>
            <p className="quiet">
              Each part is removed in turn, and the model answers the same {qn} question{qn === 1 ? "" : "s"},{" "}
              {sameOpts && ex?.nUntargeted != null && ex.nUntargeted !== n
                ? `${n} times each where a question was written for the removed part and ${ex.nUntargeted} time${ex.nUntargeted === 1 ? "" : "s"} otherwise.`
                : `${n} times each.`}{" "}
              <button type="button" className="link" aria-expanded={showQs} aria-controls="questions" onClick={() => setShowQs((v) => !v)}>
                {showQs ? "Hide" : "See"} the questions
              </button>
            </p>
            {showQs &&
              (model === "yes" ? (
                <div className="opts fade-in" id="questions">
                  <div className="sets" role="group" aria-label="Question set">
                    <button type="button" className="link" aria-pressed={cleanQs.join("\n") === ORIGINAL_PROBES.join("\n")} onClick={() => setQueries(ORIGINAL_PROBES)}>
                      Short, vague questions
                    </button>
                    {concrete.length > 0 && (
                      <button type="button" className="link" aria-pressed={cleanQs.join("\n") === concrete.join("\n")} onClick={() => setQueries(concrete)}>
                        Concrete tasks
                      </button>
                    )}
                  </div>
                  <label className="sr-only" htmlFor="qs-edit">Questions, one per line</label>
                  <textarea id="qs-edit" rows={Math.max(4, queries.length + 1)} value={queries.join("\n")} onChange={(e) => setQueries(e.target.value.split("\n"))} />
                  <div className="n">
                    <label htmlFor="n-edit">Times each question is asked</label>
                    <input
                      id="n-edit"
                      type="number"
                      inputMode="numeric"
                      min={2}
                      max={50}
                      value={nText}
                      onChange={(e) => {
                        setNText(e.target.value);
                        const v = Number(e.target.value);
                        if (Number.isInteger(v) && v >= 2 && v <= 50) setN(v);
                      }}
                      onBlur={() => setNText(String(n))}
                    />
                    <span>{((nParts + 1) * cleanQs.length * n).toLocaleString("en")} answers in all, from {modelName ? shortModel(modelName) : "the model"}.</span>
                  </div>
                </div>
              ) : (
                <ul className="qs fade-in" id="questions">
                  {(ex?.queries ?? []).map((q) => <li key={q}>&ldquo;{q}&rdquo;</li>)}
                </ul>
              ))}
          </>
        )}
      </>
    );
  } else if (phase === "running") {
    below = (
      <p className="quiet" aria-live="polite">
        {source === "example"
          ? "Replaying the example’s saved run."
          : `${(status?.done ?? 0).toLocaleString("en")} of ${(status?.total ?? 0).toLocaleString("en")} answers so far.`}
      </p>
    );
  } else if (phase === "result" && run) {
    const m = run.meta;
    below = (
      <>
        <div className="actions">
          {home ? (
            <button type="button" className="link" onClick={startOver}>Start over</button>
          ) : (
            <Link href="/" className="link">Test your own prompt</Link>
          )}
        </div>
        <p className="prov">
          {source === "example"
            ? `Example result, recorded earlier with ${shortModel(m.model)} on ${dateOf(m.created_at)}.`
            : source === "live"
              ? `Run just now with ${shortModel(m.model)}. This page’s address now links to it.`
              : `${m.title.replace(/\s*·\s*/g, ", ")}, run with ${shortModel(m.model)} on ${dateOf(m.created_at)}.`}
          {m.fixture && " The model is a stand-in with planted behaviour, so the method can be checked against a known answer; it is not a measurement of a real model."}
        </p>
      </>
    );
  }

  // ---- the result: one part at a time, in the same shell as a readout run -------------------------------------
  const secs = phase === "result" ? (bundle ? bundle.sections : props.mode === "saved" ? (props.seed ?? []).map((x, i) => ({ ...x, id: i })) : []) : [];
  const buttonFor = useCallback(
    (k: number): ShellButton => {
      if (!run || !secs[k]) return null;
      const n = run.note(secs[k].id);
      return { text: n.says, tone: n.kind === "found" ? "found" : n.kind === "untestable" ? "quiet" : "plain" };
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [run, bundle],
  );
  const focusFor = useCallback((k: number) => (run && secs[k] ? <Detail key={k} run={run} k={secs[k].id} /> : null),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [run, bundle]);
  if (phase === "result" && secs.length > 0)
    return (
      <>
        <Shell
          parts={secs}
          ready={!!run}
          button={buttonFor}
          focus={focusFor}
          head={
            <>
              <h1>Find out what each part of a system prompt actually changes.</h1>
              <p className="lede" aria-live="polite">{run ? lede : "Loading the run…"}</p>
            </>
          }
          below={below}
        />
        {loadErr && <p role="alert" className="alert">The run didn&rsquo;t load ({loadErr}). Reload the page to try again.</p>}
      </>
    );

  return (
    <>
      <div className="head">
        <h1>Find out what each part of a system prompt actually changes.</h1>
        <p className="lede" aria-live="polite">{lede}</p>
      </div>
      <div className={`comp${roomy ? " roomy" : ""}`} data-phase={phase}>
        <div className="paper">
          {phase === "running" && (
            <div className="progress"><i style={{ width: `${progress * 100}%` }} /></div>
          )}
        </div>
        <div className="rows">{rows}</div>
      </div>
      <div className="col">
        {below}
        {error && <p role="alert" className="alert">{error}</p>}
        {hasApi && home && model === "no" && phase === "edit" && changed && API && (
          <p className="quiet">The analysis server at {API} has no model set up, or isn&rsquo;t reachable.</p>
        )}
      </div>
    </>
  );
}

function Gap({
  i, on, editing, onToggle, draw,
}: { i: number; on: boolean; editing: boolean; onToggle: (i: number) => void; draw: boolean }) {
  const reduce = useReducedMotion();
  const line = (
    <motion.span className="line" initial={draw && on && !reduce ? { scaleX: 0 } : false} animate={{ scaleX: 1 }} transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1], delay: 0.04 * i }} />
  );
  if (!editing)
    return (
      <span className={`gap ${on ? "on" : ""}`} aria-hidden="true">
        {line}
      </span>
    );
  return (
    <button
      type="button"
      className={`gap ${on ? "on" : ""}`}
      role="switch"
      aria-checked={on}
      aria-label={`Part break before paragraph ${i + 2}`}
      onClick={() => onToggle(i)}
    >
      {line}
      <span className="hint" aria-hidden="true">{on ? "merge" : "split here"}</span>
    </button>
  );
}
