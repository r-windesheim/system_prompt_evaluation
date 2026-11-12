import type { Meta } from "@/lib/types";

export function RunHeader({ meta, nSections, nResponses }: { meta: Meta; nSections: number; nResponses: number }) {
  const date = new Date(meta.created_at).toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" });
  return (
    <div className="max-w-[70ch]">
      {meta.fixture && (
        <p className="mb-3 inline-flex items-center gap-2 rounded-full border border-rule-strong px-3 py-0.5 text-[12.5px] text-graphite">
          <span className="size-1.5 rounded-full bg-graphite" />
          Synthetic run: known ground truth, not a real model
        </p>
      )}
      <h1 className="text-[28px] leading-tight font-semibold tracking-[-0.015em] text-balance">{meta.title}</h1>
      <p className="tnum mt-2 text-[14px] text-graphite">
        {meta.model} on {date}. {nSections} sections, {meta.queries.length} user messages, {meta.n_per_query} samples
        each at temperature {meta.temperature}: {nResponses.toLocaleString("en")} responses.
      </p>
      {meta.notes && <p className="mt-2 text-[14px] text-graphite">{meta.notes}</p>}
    </div>
  );
}
