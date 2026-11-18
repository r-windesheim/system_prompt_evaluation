import type { Metadata } from "next";
import Link from "next/link";
import { ReadoutBelow } from "@/components/spet/home";
import { Readout } from "@/components/spet/readout";
import { Tool } from "@/components/spet/tool";
import { loadRun, runIds } from "@/lib/runs.server";
import { buildView, hasReadout } from "@/lib/view.server";

export const dynamicParams = false;

export function generateStaticParams() {
  return runIds().map((id) => ({ id }));
}

export async function generateMetadata({ params }: { params: Promise<{ id: string }> }): Promise<Metadata> {
  const { id } = await params;
  return { title: loadRun(id).meta.title.replace(/\s*·\s*/g, ", ") };
}

export default async function RunPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  if (hasReadout(id)) {
    // a readout run is shown from its small view; the bundle itself is never sent
    const view = buildView(id);
    return <Readout view={view} title={view.title} below={<ReadoutBelow view={view} action={<Link href="/" className="link">Test your own prompt</Link>} />} />;
  }
  const b = loadRun(id);
  return <Tool mode="saved" id={id} recorded seed={b.sections.map(({ label, text }) => ({ label, text }))} />;
}
