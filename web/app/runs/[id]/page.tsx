import type { Metadata } from "next";
import { Tool } from "@/components/spet/tool";
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
  return <Tool mode="saved" id={id} recorded seed={b.sections.map(({ label, text }) => ({ label, text }))} />;
}
