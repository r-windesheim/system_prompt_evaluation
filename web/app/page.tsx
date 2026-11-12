import Link from "next/link";
import { RunHeader } from "@/components/run-header";
import { RunView } from "@/components/run-view";
import { fmtDelta } from "@/lib/groups";
import { allSummaries, loadRun } from "@/lib/runs.server";

export default function Home() {
  const runs = allSummaries();
  const featured = runs[0] ? loadRun(runs[0].meta.id) : null;
  return (
    <div>
      <section className="pt-10 pb-10 lg:pt-16 lg:pb-14">
        <h1 className="max-w-[18ch] text-[clamp(34px,5.2vw,58px)] leading-[1.02] font-semibold tracking-[-0.03em] text-balance">
          Which part of the system prompt made it say that?
        </h1>
        <p className="mt-5 max-w-[60ch] text-[16px] leading-relaxed text-graphite">
          SPET takes one section out of a system prompt at a time and replays the same conversations with the same
          sampling seeds. Then it measures which habits change: apologising, hedging, bullet lists, questions back.
          Every effect comes with a confidence interval and a correction for testing many things at once.
        </p>
      </section>

      {featured && (
        <section aria-label="Featured run" className="border-t border-rule pt-10">
          <RunHeader meta={featured.meta} nSections={featured.sections.length} nResponses={featured.responses.length} />
          <div className="mt-10">
            <RunView bundle={featured} withMatrix={false} />
          </div>
          <p className="mt-8 text-[14px]">
            <Link href={`/runs/${featured.meta.id}/`} className="underline decoration-rule-strong underline-offset-4 hover:decoration-ink">
              Open the full run, with every section against every quirk
            </Link>
          </p>
        </section>
      )}

      <section aria-labelledby="runs-h" className="mt-20 border-t border-rule pt-10">
        <h2 id="runs-h" className="text-[17px] font-semibold tracking-tight">All runs</h2>
        <ul className="mt-4">
          {runs.map((r) => (
            <li key={r.meta.id} className="border-t border-rule first:border-t-0">
              <Link href={`/runs/${r.meta.id}/`} className="grid gap-1 py-4 hover:bg-sheet sm:grid-cols-[1fr_auto] sm:gap-6">
                <span>
                  <span className="text-[15px] font-medium">{r.meta.title}</span>
                  {r.meta.fixture && <span className="ml-2 text-[12.5px] text-graphite">synthetic</span>}
                  <span className="mt-0.5 block text-[13px] text-graphite">
                    {r.top.slice(0, 3).map((t) => `${t.sectionLabel} → ${t.detectorLabel} ${fmtDelta(t.delta)}`).join("; ") || "No significant effects"}
                  </span>
                </span>
                <span className="tnum text-[13px] text-graphite">
                  {r.meta.model}, {r.sections.length} sections, {r.nResponses} responses
                </span>
              </Link>
            </li>
          ))}
        </ul>
        <p className="mt-6 max-w-[62ch] text-[13px] text-graphite">
          Runs on a self-hosted open-weights model are next. Until then the only run is synthetic, so you can check
          the method finds what was planted.
        </p>
      </section>
    </div>
  );
}
