import type { Metadata } from "next";
import Link from "next/link";
import { allSummaries } from "@/lib/runs.server";

export const metadata: Metadata = { title: "Runs" };

const fmtDelta = (d: number) => `${d > 0 ? "+" : d < 0 ? "−" : ""}${Math.abs(d).toFixed(2)}`;

export default function Runs() {
  const runs = allSummaries();
  return (
    <div className="page col">
      <h1>Runs</h1>
      <p className="lede">Every recorded run. Open one to see what each part of its prompt changes.</p>
      <ul className="runlist">
        {runs.map((r) => (
          <li key={r.meta.id}>
            <Link href={`/run/?id=${r.meta.id}`}>
              <span className="t">
                {r.meta.title}
                {r.meta.fixture && <span className="m"> synthetic</span>}
              </span>
              <span className="s">
                {r.top.slice(0, 3).map((t) => `${t.sectionLabel}: ${t.detectorLabel.toLowerCase()} ${fmtDelta(t.delta)}`).join("; ") || "No significant effects"}
              </span>
              <span className="m">
                {r.meta.model}, {r.sections.length} parts, {r.nResponses.toLocaleString("en")} answers
              </span>
            </Link>
          </li>
        ))}
      </ul>
      <p className="quiet">
        Runs on a self-hosted open-weights model are next. Until then, besides the example there is one synthetic run, so you
        can check the method finds what was planted.
      </p>
    </div>
  );
}
