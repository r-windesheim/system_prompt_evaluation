import type { Metadata } from "next";
import Link from "next/link";
import { allSummaries } from "@/lib/runs.server";
import { BUTTON } from "@/lib/view";
import { buildView, readoutIds } from "@/lib/view.server";

export const metadata: Metadata = { title: "Runs" };

const fmtDelta = (d: number) => `${d > 0 ? "+" : d < 0 ? "−" : ""}${Math.abs(d).toFixed(2)}`;

export default function Runs() {
  const runs = allSummaries();
  const readouts = new Set(readoutIds());
  /** For a run with a readout: the parts it follows, in plain words */
  const said = (id: string) => {
    const v = buildView(id);
    const f = v.parts.filter((p) => p.reading === "followed").map((p) => p.label);
    return `${BUTTON.followed}: ${f.length ? f.join(", ") : "none"}. ${v.parts.length} parts, each checked for whether the model does what it asks.`;
  };
  return (
    <div className="page col">
      <h1>Runs</h1>
      <p className="lede">Every recorded run. Open one to see what each part of its prompt changes.</p>
      <ul className="runlist">
        {runs.map((r) => (
          <li key={r.meta.id}>
            <Link href={readouts.has(r.meta.id) ? `/runs/${r.meta.id}/` : `/run/?id=${r.meta.id}`}>
              <span className="t">
                {r.meta.title.replace(/\s*·\s*/g, ", ")}
                {r.meta.fixture && <span className="m"> synthetic</span>}
              </span>
              <span className="s">
                {readouts.has(r.meta.id) ? said(r.meta.id) : r.top.slice(0, 3).map((t) => `${t.sectionLabel}: ${t.detectorLabel.toLowerCase()} ${fmtDelta(t.delta)}`).join("; ") || "No significant effects"}
              </span>
              <span className="m">
                {r.meta.model}, {r.sections.length} parts, {r.nResponses.toLocaleString("en")} answers
              </span>
            </Link>
          </li>
        ))}
      </ul>
      <p className="quiet">
        One run is synthetic: a stand-in model with planted habits, so you can check the method finds what was planted.
      </p>
    </div>
  );
}
