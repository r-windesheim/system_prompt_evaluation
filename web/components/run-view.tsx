"use client";

import { useRef, useState } from "react";
import type { RunBundle } from "@/lib/types";
import { useRunIndex } from "@/lib/use-run";
import { Bench, type BenchState } from "./bench";
import { EffectMatrix } from "./effect-matrix";

export function RunView({ bundle, withMatrix = true }: { bundle: RunBundle; withMatrix?: boolean }) {
  const run = useRunIndex(bundle);
  const [state, setState] = useState<BenchState>({ removed: null, query: 0, sample: 0, focus: null });
  const benchRef = useRef<HTMLDivElement>(null);

  return (
    <>
      <div ref={benchRef} className="scroll-mt-6">
        <Bench run={run} state={state} setState={setState} />
      </div>
      {withMatrix && (
        <div className="mt-20 border-t border-rule pt-10">
          <EffectMatrix
            run={run}
            removed={state.removed}
            focus={state.focus}
            onPick={(k, d) => {
              setState((s) => ({ ...s, removed: k, focus: d }));
              benchRef.current?.scrollIntoView({ behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth" });
            }}
          />
        </div>
      )}
    </>
  );
}
