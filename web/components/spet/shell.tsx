"use client";

// One part at a time. The overview is the prompt on one sheet, each part cut to two lines with one button beside it.
// Opening a part replaces the sheet with that part alone: where you are, its full text, and what the caller renders
// under it. Arrow keys move between parts, Escape goes back, and the URL hash (#part=N) is kept.
//
// Motion: every change is one View Transition, so only transform and opacity animate (on the browser's snapshots).
//   open / close: the part's number, text and button glide between the list and the focused sheet; the rest fades.
//   step (Previous / Next): the sheet's contents cross-fade with a small shift in the direction of travel.
//   toggle (More detail, What it drew on, ...): blocks that stay glide; new ones fade in.
// Without the API, or under reduced motion: an instant swap.

import { createContext, useCallback, useContext, useEffect, useLayoutEffect, useRef, useState } from "react";
import { flushSync } from "react-dom";
import { Chevron } from "./note";

export type Tone = "found" | "plain" | "strong" | "quiet";
/** the class for a tone ("quiet" is taken by a paragraph style) */
const toneClass = (t: Tone) => (t === "quiet" ? "dim" : t);
export type ShellButton = { text: string; tone: Tone; dot?: boolean; dotLabel?: string } | null;

type Kind = "morph" | "step" | "toggle";
type VT = { finished: Promise<void>; ready: Promise<void>; updateCallbackDone: Promise<void>; skipTransition: () => void };

// ---- the transition, outside React: it names elements, snapshots, then lets React render synchronously ----------
let vt: VT | null = null;
const tagged: HTMLElement[] = [];
const name = (el: Element | null | undefined, n: string) => {
  if (!(el instanceof HTMLElement)) return;
  el.style.viewTransitionName = n;
  tagged.push(el);
};
const unname = () => tagged.splice(0).forEach((el) => (el.style.viewTransitionName = ""));
const reduced = () => typeof window !== "undefined" && window.matchMedia("(prefers-reduced-motion: reduce)").matches;

function nameSheet(root: HTMLElement | null, phase: "old" | "new", kind: Kind) {
  if (!root) return;
  name(root.querySelector(".paper"), "p-sheet");
  name(root.querySelector(".rows"), kind === "toggle" ? "p-rows" : phase === "old" ? "p-rows-old" : "p-rows-new");
}
function nameRow(root: HTMLElement | null, k: number) {
  const row = root?.querySelector(`.row[data-part="${k}"]`);
  if (!row) return;
  name(row.querySelector(".num"), "p-num");
  name(row.querySelector(".para"), "p-text");
  name(row.querySelector(".note"), "p-pill");
}
/** For a toggle each block of the opened part is its own layer, keyed by what it is. */
function nameFocus(root: HTMLElement | null, k: number | null) {
  if (!root || k === null) return;
  nameRow(root, k);
  root.querySelectorAll<HTMLElement>(".rows [data-k]").forEach((el) => name(el, `k-${el.dataset.k}`));
}

/**
 * The header is its own layer so it stays put. When the page is scrolled past it at either end of a transition, it
 * would fly in from off screen instead, so it then joins the page and simply fades.
 */
const HEADER_OFF = 40;
let header: HTMLElement | null = null;
const holdHeader = () => {
  header = document.querySelector<HTMLElement>(".top");
  if (header) header.style.viewTransitionName = "none";
};
const releaseHeader = () => {
  if (header) header.style.viewTransitionName = "";
  header = null;
};

function transition(
  root: HTMLElement | null,
  kind: Kind,
  update: () => void,
  opts: { before?: () => void; after?: () => void; dir?: "next" | "prev"; scrolledTo?: () => number } = {},
) {
  const doc = document as Document & { startViewTransition?: (cb: () => void) => VT };
  if (!doc.startViewTransition || reduced()) {
    flushSync(update);
    return;
  }
  if (vt) {
    // one already running: finish it at once, no queue, no stutter
    vt.skipTransition();
    unname();
    releaseHeader();
    flushSync(update);
    return;
  }
  const html = document.documentElement;
  html.dataset.vt = kind;
  if (opts.dir) html.dataset.dir = opts.dir;
  nameSheet(root, "old", kind);
  opts.before?.();
  if (window.scrollY > HEADER_OFF) holdHeader();
  const t = doc.startViewTransition(() => {
    unname();
    flushSync(update);
    if (window.scrollY > HEADER_OFF) holdHeader();
    nameSheet(root, "new", kind);
    opts.after?.();
  });
  vt = t;
  const quiet = (e: unknown) => {
    if (process.env.NODE_ENV !== "production" && !(e instanceof DOMException && e.name === "AbortError")) console.warn("view transition:", e);
  };
  t.ready.catch(quiet);
  t.updateCallbackDone.catch(quiet);
  t.finished.catch(() => {}).finally(() => {
    if (vt === t) vt = null;
    unname();
    releaseHeader();
    delete html.dataset.vt;
    delete html.dataset.dir;
  });
}

// ---- what the opened part's content can use ------------------------------------------------------------------
type ShellApi = {
  /** change something inside the opened part (a disclosure), as one short cross-fade */
  toggle: (change: () => void) => void;
  /** move to another part */
  go: (k: number) => void;
};
const Ctx = createContext<ShellApi>({ toggle: (f) => f(), go: () => {} });
export const useShell = () => useContext(Ctx);

const hashPart = (n: number) => {
  const m = window.location.hash.match(/part=(\d+)/);
  const k = m ? Number(m[1]) - 1 : null;
  return k !== null && k >= 0 && k < n ? k : null;
};
const setHash = (k: number | null) => {
  const h = k === null ? "" : `#part=${k + 1}`;
  if (window.location.hash !== h) window.history.replaceState(window.history.state, "", window.location.pathname + window.location.search + h);
};

// Before hydration: if the address opens a part, hide the overview so it never flashes.
const PENDING = `(function(){try{if(/part=\\d+/.test(location.hash))document.documentElement.classList.add("spet-pending")}catch(e){}})()`;

export function Shell({
  parts, button, focus, prepare, prefetch, head, below, ready = true,
}: {
  parts: { label: string; text: string }[];
  button: (k: number) => ShellButton;
  /** what the opened part shows under its text */
  focus: (k: number) => React.ReactNode;
  /** load what the part needs before it is shown (its answers); resolves when ready */
  prepare?: (k: number) => Promise<unknown>;
  /** start loading early (hover, focus, neighbours) */
  prefetch?: (k: number) => void;
  head: React.ReactNode;
  below?: React.ReactNode;
  /** false while the run loads: rows are drawn but cannot be opened */
  ready?: boolean;
}) {
  const n = parts.length;
  const [cur, setCur] = useState<number | null>(null);
  const curRef = useRef<number | null>(null);
  const seq = useRef(0);
  const root = useRef<HTMLDivElement>(null);
  const listScroll = useRef<{ k: number | null; y: number }>({ k: null, y: 0 });
  const focusAfter = useRef<"where" | number | null>(null);

  const show = useCallback((k: number | null) => {
    curRef.current = k;
    setCur(k);
    setHash(k);
  }, []);

  const wait = useCallback(async (k: number) => {
    const my = ++seq.current;
    try {
      await prepare?.(k);
    } catch {
      /* the part still opens; its content says what is missing */
    }
    return my === seq.current;
  }, [prepare]);

  const open = useCallback(async (k: number) => {
    if (!ready || k < 0 || k >= n) return;
    if (!(await wait(k))) return;
    listScroll.current = { k, y: window.scrollY };
    focusAfter.current = "where";
    const r = root.current;
    transition(r, "morph", () => {
      show(k);
      window.scrollTo(0, 0);
    }, { before: () => nameRow(r, k), after: () => nameRow(r, k) });
  }, [ready, n, wait, show]);

  const close = useCallback(() => {
    const k = curRef.current;
    if (k === null) return;
    seq.current++;
    const r = root.current;
    const para = r?.querySelector(".focus .para");
    const textTop = para ? para.getBoundingClientRect().top : 120;
    focusAfter.current = k;
    transition(r, "morph", () => {
      show(null);
      const row = r?.querySelector(`.row[data-part="${k}"] .para`);
      // back to where the list was; if you moved to another part, put that part where its text just was
      const y = listScroll.current.k === k ? listScroll.current.y : row ? row.getBoundingClientRect().top + window.scrollY - textTop : 0;
      window.scrollTo(0, Math.max(0, y));
    }, { before: () => nameRow(r, k), after: () => nameRow(r, k) });
  }, [show]);

  const go = useCallback(async (k: number) => {
    const from = curRef.current;
    if (from === null || k < 0 || k >= n || k === from) return;
    if (!(await wait(k))) return;
    focusAfter.current = "where";
    transition(root.current, "step", () => {
      show(k);
      window.scrollTo(0, 0);
    }, { dir: k > from ? "next" : "prev" });
  }, [n, wait, show]);

  const toggle = useCallback((change: () => void) => {
    const r = root.current;
    transition(r, "toggle", change, { before: () => nameFocus(r, curRef.current), after: () => nameFocus(r, curRef.current) });
  }, []);

  // focus follows the view, without scrolling it
  useLayoutEffect(() => {
    const f = focusAfter.current;
    if (f === null) return;
    focusAfter.current = null;
    const el = f === "where" ? root.current?.querySelector<HTMLElement>(".where .here") : root.current?.querySelector<HTMLElement>(`.row[data-part="${f}"] .text-btn`);
    el?.focus({ preventScroll: true });
  }, [cur]);

  // neighbours load in the background
  useEffect(() => {
    if (cur === null || !prefetch) return;
    if (cur > 0) prefetch(cur - 1);
    if (cur < n - 1) prefetch(cur + 1);
  }, [cur, n, prefetch]);

  // the address opens a part; back and forward in the hash too
  useEffect(() => {
    if (!ready) return;
    const html = document.documentElement;
    const k = hashPart(n);
    if (k === null) html.classList.remove("spet-pending");
    else
      wait(k).then(() => {
        flushSync(() => show(k));
        html.classList.remove("spet-pending");
      });
    const onHash = () => {
      const h = hashPart(n);
      if (h !== curRef.current) wait(h ?? 0).then(() => show(h));
    };
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, [ready, n, wait, show]);

  // a stuck pending class never hides the page for long
  useEffect(() => {
    const t = setTimeout(() => document.documentElement.classList.remove("spet-pending"), 3000);
    return () => clearTimeout(t);
  }, []);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const k = curRef.current;
      if (k === null || e.metaKey || e.ctrlKey || e.altKey || e.shiftKey) return;
      const t = e.target as HTMLElement | null;
      if (t && (t.closest("input, textarea, select, [contenteditable=true]"))) return;
      if (e.key === "ArrowRight") { e.preventDefault(); go(k + 1); }
      else if (e.key === "ArrowLeft") { e.preventDefault(); go(k - 1); }
      else if (e.key === "Escape") { e.preventDefault(); close(); }
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [go, close]);

  const anyDot = parts.some((_, k) => button(k)?.dot);

  const rowFor = (k: number, inFocus: boolean) => {
    const b = button(k);
    const p = parts[k];
    const dot = b?.dot ? <span className="dot" role="img" aria-label={b.dotLabel ?? "Also changes something it never mentions"} /> : null;
    if (inFocus)
      return (
        <div className={`row${b?.tone === "found" ? " found" : ""}`} data-part={k} key={`f${k}`}>
          <span className="num" aria-hidden="true">{k + 1}</span>
          <div className="text"><p className="para prose">{p.text}</p></div>
          <div className="note">
            {b && (
              <button type="button" className={`pill ${toneClass(b.tone)}`} onClick={close} aria-label={`${b.text}. Back to all parts`}>
                {b.text}
                <Chevron />
              </button>
            )}
            {dot}
          </div>
          <div className="detail">{focus(k)}</div>
        </div>
      );
    const live = ready && !!b;
    return (
      <div
        className={`row${live ? " result" : ""}${b?.tone === "found" ? " found" : ""}`}
        data-part={k}
        key={`o${k}`}
        id={`part-${k + 1}`}
        onClick={live ? () => open(k) : undefined}
        onPointerEnter={live && prefetch ? () => prefetch(k) : undefined}
      >
        <span className="num" aria-hidden="true">{k + 1}</span>
        {live ? (
          <button
            type="button"
            className="text text-btn"
            onClick={(e) => { e.stopPropagation(); open(k); }}
            onFocus={prefetch ? () => prefetch(k) : undefined}
            aria-label={`Part ${k + 1}, ${p.label}: ${b!.text}${b!.dot ? ", and a side effect" : ""}. Open`}
          >
            <span className="para prose">{p.text}</span>
          </button>
        ) : (
          <div className="text"><span className="para prose">{p.text}</span></div>
        )}
        <div className="note" aria-hidden={live ? true : undefined}>
          {b && (
            <span className={`pill ${toneClass(b.tone)}`}>
              {b.text}
              <Chevron />
            </span>
          )}
          {dot}
        </div>
      </div>
    );
  };

  const api = { toggle, go };
  return (
    <Ctx.Provider value={api}>
      <script dangerouslySetInnerHTML={{ __html: PENDING }} />
      <div ref={root} className={`shell${cur !== null ? " focused" : ""}`}>
        <div className="head">
          {head}
          {anyDot && cur === null && (
            <p className="legend"><span className="dot" aria-hidden="true" /> means the part also changes something it never mentions.</p>
          )}
        </div>
        <div className="comp">
          <div className="paper" />
          {cur === null ? (
            <div className="rows overview">
              {parts.map((_, k) => [
                k > 0 && <div className="gaprow" aria-hidden="true" key={`g${k}`}><span className="line" /></div>,
                rowFor(k, false),
              ])}
            </div>
          ) : (
            <div className="rows focus">
              <div className="where" data-k="where">
                <div className="in">
                  <span className="here" tabIndex={-1}>
                    Part {cur + 1} of {n}: <span className="label">{parts[cur].label}</span>
                  </span>
                  <nav aria-label="Parts">
                    <button type="button" onClick={() => go(cur - 1)} disabled={cur === 0} title="Left arrow key">Previous</button>
                    <button type="button" onClick={() => go(cur + 1)} disabled={cur === n - 1} title="Right arrow key">Next</button>
                    <button type="button" onClick={close} title="Escape key">All parts</button>
                  </nav>
                </div>
              </div>
              {rowFor(cur, true)}
            </div>
          )}
        </div>
        {below && <div className="below">{below}</div>}
      </div>
    </Ctx.Provider>
  );
}
