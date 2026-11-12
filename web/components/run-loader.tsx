"use client";

import { motion } from "motion/react";
import { useEffect, useState } from "react";
import { bundleUrl } from "@/lib/api";
import type { RunBundle } from "@/lib/types";
import { DrillDown } from "./drilldown/drilldown";

/** Fetches the run bundle after first paint, so pages stay small (bundles are ~300 KB of JSON). */
export function RunLoader({
  id,
  sectionLabels = [],
  onLoad,
}: {
  id: string;
  sectionLabels?: string[];
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
      <div aria-busy="true" aria-label="Loading run" className="grid min-h-[620px] max-w-[760px] gap-2.5">
        {sectionLabels.map((l) => (
          <div key={l} className="h-[104px] rounded-xl border border-rule bg-sheet px-5 py-4 font-semibold text-graphite/50">{l}</div>
        ))}
      </div>
    );

  return (
    <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ duration: 0.25 }}>
      <DrillDown bundle={bundle} />
    </motion.div>
  );
}
