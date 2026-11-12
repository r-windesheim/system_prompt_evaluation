"use client";

import { motion } from "motion/react";
import { useEffect, useState } from "react";
import { bundleUrl } from "@/lib/api";
import type { RunBundle } from "@/lib/types";
import { RunView } from "./run-view";

/** Fetches the run bundle after first paint, so pages stay small (bundles are ~300 KB of JSON). */
export function RunLoader({
  id,
  sectionLabels = [],
  withMatrix = true,
  onLoad,
}: {
  id: string;
  sectionLabels?: string[];
  withMatrix?: boolean;
  onLoad?: (b: RunBundle) => void;
}) {
  const [bundle, setBundle] = useState<RunBundle | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let live = true;
    fetch(bundleUrl(id))
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`))))
      .then((b: RunBundle) => {
        if (!live) return;
        setBundle(b);
        onLoad?.(b);
      })
      .catch((e: Error) => live && setError(e.message));
    return () => {
      live = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  if (error)
    return (
      <p className="text-[14px] text-graphite">
        The run data didn&apos;t load ({error}). Reload the page to try again.
      </p>
    );

  if (!bundle)
    return (
      <div aria-busy="true" aria-label="Loading run" className="grid min-h-[620px] gap-10 lg:grid-cols-[minmax(250px,300px)_minmax(0,1fr)_minmax(270px,320px)]">
        <ol className="mt-[74px]">
          {sectionLabels.map((l) => (
            <li key={l} className="border-t border-rule py-3 pl-4 text-[14px] text-graphite/60 last:border-b">
              {l}
            </li>
          ))}
        </ol>
        <div className="mt-[74px] h-72 rounded-lg border border-rule bg-sheet" />
      </div>
    );

  return (
    <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ duration: 0.25 }}>
      <RunView bundle={bundle} withMatrix={withMatrix} />
    </motion.div>
  );
}
