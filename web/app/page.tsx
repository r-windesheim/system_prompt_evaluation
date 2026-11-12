import Link from "next/link";
import { RunHeader } from "@/components/run-header";
import { RunLoader } from "@/components/run-loader";
import { fmtDelta } from "@/lib/groups";
import { allSummaries } from "@/lib/runs.server";

export default function Home() {
  const runs = allSummaries();
  const featured = runs[0] ?? null;
  return (
    <div>
      <section className="pt-10 pb-10 lg:pt-16 lg:pb-14">
        <h1 className="max-w-[18ch] text-[clamp(34px,5.2vw,58px)] leading-[1.02] font-semibold tracking-[-0.03em] text-balance">
          Which part of the system prompt made it say that?
        </h1>
        <p className="mt-5 max-w-[60ch] text-[16px] leading-relaxed text-graphite">
          SPET takes one part of a system prompt out at a time and asks the model the same questions again. Then it
          measures which habits change, such as apologising, hedging, bullet lists or questions back. A change is only
          reported if it clearly beats chance after correcting for testing many things at once.
        </p>
        <p className="mt-7 flex flex-wrap items-center gap-4">
          <Link href="/analyze/" className="inline-flex items-center rounded-full bg-ink px-5 py-2.5 text-[15px] font-medium text-paper hover:bg-ink/85">
            Analyse a prompt
          </Link>
          <a href="#featured" className="text-[14px] text-graphite underline-offset-4 hover:text-ink hover:underline">
            or try the demo below
          </a>
        </p>
      </section>

      {featured && (
        <section id="featured" aria-label="Featured run" className="scroll-mt-6 border-t border-rule pt-10">
          <RunHeader meta={featured.meta} nSections={featured.sections.length} nResponses={featured.nResponses} />
          <div className="mt-10">
            <RunLoader id={featured.meta.id} sectionLabels={featured.sections.map((s) => s.label)} />
          </div>
          <p className="mt-8 text-[14px]">
            <Link href={`/run/?id=${featured.meta.id}`} className="underline decoration-rule-strong underline-offset-4 hover:decoration-ink">
              Open this run on its own page
            </Link>
          </p>
        </section>
      )}

      <section aria-labelledby="runs-h" className="mt-20 border-t border-rule pt-10">
        <h2 id="runs-h" className="text-[17px] font-semibold tracking-tight">All runs</h2>
        <ul className="mt-4">
          {runs.map((r) => (
            <li key={r.meta.id} className="border-t border-rule first:border-t-0">
              <Link href={`/run/?id=${r.meta.id}`} className="grid gap-1 py-4 hover:bg-sheet sm:grid-cols-[1fr_auto] sm:gap-6">
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
