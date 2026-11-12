"use client";

import { useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";
import { RunHeader } from "@/components/run-header";
import { RunLoader } from "@/components/run-loader";
import type { RunBundle } from "@/lib/types";

function RunById() {
  const id = useSearchParams().get("id");
  const [b, setB] = useState<RunBundle | null>(null);
  if (!id) return <p className="pt-10 text-graphite">No run selected.</p>;
  return (
    <div className="pt-8">
      {b && <RunHeader meta={b.meta} nSections={b.sections.length} nResponses={b.responses.length} />}
      <div className="mt-10">
        <RunLoader key={id} id={id} onLoad={setB} />
      </div>
    </div>
  );
}

export default function RunPage() {
  return (
    <Suspense>
      <RunById />
    </Suspense>
  );
}
