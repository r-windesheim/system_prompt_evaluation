"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import type { RunView } from "@/lib/view";
import { ReadoutBelow } from "./home";
import { Readout } from "./readout";
import { Tool } from "./tool";

const BASE = process.env.NEXT_PUBLIC_BASE_PATH ?? "";

/** A recorded run with a readout is drawn from its small view (never its bundle); anything else, live runs included, as before. */
function ReadoutById({ id }: { id: string }) {
  const [view, setView] = useState<RunView | null>(null);
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => {
    let live = true;
    fetch(`${BASE}/views/${encodeURIComponent(id)}/index.json`)
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json() as Promise<RunView>;
      })
      .then((v) => live && setView(v))
      .catch((e: Error) => live && setErr(e.message));
    return () => {
      live = false;
    };
  }, [id]);
  if (err) return <div className="head"><h1>The run didn&rsquo;t load ({err}).</h1></div>;
  if (!view) return null;
  return <Readout view={view} title={view.title} below={<ReadoutBelow view={view} action={<Link href="/" className="link">Test your own prompt</Link>} />} />;
}

function FromQuery({ readouts }: { readouts: string[] }) {
  const id = useSearchParams().get("id");
  if (!id)
    return (
      <div className="head">
        <h1>No run selected.</h1>
      </div>
    );
  return readouts.includes(id) ? <ReadoutById key={id} id={id} /> : <Tool key={id} mode="saved" id={id} />;
}

export function RunByQuery({ readouts }: { readouts: string[] }) {
  return (
    <Suspense>
      <FromQuery readouts={readouts} />
    </Suspense>
  );
}
