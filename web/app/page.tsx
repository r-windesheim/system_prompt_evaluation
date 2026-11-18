import { Home } from "@/components/spet/home";
import { EXAMPLE_ID, HOME_RUN_ID } from "@/lib/parts";
import { loadRun } from "@/lib/runs.server";
import { buildView } from "@/lib/view.server";

export default function Page() {
  // The page carries only the overview (the prompt and one reading per part); a part's answers are fetched when it opens.
  const view = buildView(HOME_RUN_ID);
  // "Test your own prompt": only what its first paint needs; its example bundle is fetched when it is opened.
  const b = loadRun(EXAMPLE_ID);
  const example = {
    sections: b.sections.map(({ label, text }) => ({ label, text })),
    queries: b.meta.queries,
    n: b.meta.n_per_query,
    nUntargeted: b.meta.n_per_query_untargeted ?? null,
    model: b.meta.model,
    created_at: b.meta.created_at,
  };
  return <Home view={view} example={example} />;
}
