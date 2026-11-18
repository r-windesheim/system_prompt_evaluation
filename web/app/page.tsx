import { Tool } from "@/components/spet/tool";
import { EXAMPLE_ID } from "@/lib/parts";
import { loadRun } from "@/lib/runs.server";

export default function Home() {
  // Only what the first paint needs; the full bundle is fetched after paint.
  const b = loadRun(EXAMPLE_ID);
  const example = {
    sections: b.sections.map(({ label, text }) => ({ label, text })),
    queries: b.meta.queries,
    n: b.meta.n_per_query,
    nUntargeted: b.meta.n_per_query_untargeted ?? null,
    model: b.meta.model,
    created_at: b.meta.created_at,
  };
  return <Tool mode="home" example={example} />;
}
