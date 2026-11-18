"use client";

import Link from "next/link";
import { useState } from "react";
import type { RunView } from "@/lib/view";
import { Readout } from "./readout";
import { Tool, type ExampleInfo } from "./tool";

export const HEADLINE = "Find out what each part of a system prompt actually changes.";

/** The footer under a readout run: what to do next, and one quiet line with the size of the run. */
export function ReadoutBelow({ view, action }: { view: RunView; action: React.ReactNode }) {
  return (
    <>
      <div className="actions">{action}</div>
      <p className="prov">
        {view.size} <Link href="/method/" className="link">Method</Link>
      </p>
    </>
  );
}

/**
 * The home page: the recorded Claude prompt run, already in its results. "Test your own prompt" swaps in the live
 * flow (paste, split, run); it mounts only then, so its example run is not fetched before it is wanted.
 */
export function Home({ view, example }: { view: RunView; example: ExampleInfo }) {
  const [trying, setTrying] = useState(false);
  const start = () => {
    window.history.replaceState(window.history.state, "", window.location.pathname + window.location.search);
    setTrying(true);
    window.scrollTo(0, 0);
  };
  const back = () => {
    setTrying(false);
    window.scrollTo(0, 0);
  };
  if (trying) return <Tool mode="home" example={example} onBack={back} />;
  return (
    <Readout
      view={view}
      title={HEADLINE}
      below={<ReadoutBelow view={view} action={<button type="button" className="link" onClick={start}>Test your own prompt</button>} />}
    />
  );
}
