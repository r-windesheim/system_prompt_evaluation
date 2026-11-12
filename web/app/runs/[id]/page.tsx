import type { Metadata } from "next";
import { RunHeader } from "@/components/run-header";
import { RunView } from "@/components/run-view";
import { loadRun, runIds } from "@/lib/runs.server";

export const dynamicParams = false;

export function generateStaticParams() {
  return runIds().map((id) => ({ id }));
}

export async function generateMetadata({ params }: { params: Promise<{ id: string }> }): Promise<Metadata> {
  const { id } = await params;
  return { title: loadRun(id).meta.title };
}

export default async function RunPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const b = loadRun(id);
  return (
    <div className="pt-8">
      <RunHeader meta={b.meta} nSections={b.sections.length} nResponses={b.responses.length} />
      <div className="mt-10">
        <RunView bundle={b} />
      </div>
    </div>
  );
}
