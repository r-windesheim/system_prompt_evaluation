// Static JSON per readout run, written into the export at build time:
//   /views/<id>/index.json  the overview (what /run/?id= needs before it can draw a readout run)
//   /views/<id>/<k>.json    one part's example answers and attention rows, fetched when the part is opened
import { buildPart, buildView, readoutIds } from "@/lib/view.server";

export const dynamic = "force-static";
export const dynamicParams = false;

export function generateStaticParams() {
  return readoutIds().flatMap((id) => {
    const n = buildView(id).parts.length;
    return [{ id, file: "index.json" }, ...Array.from({ length: n }, (_, k) => ({ id, file: `${k}.json` }))];
  });
}

export async function GET(_req: Request, { params }: { params: Promise<{ id: string; file: string }> }) {
  const { id, file } = await params;
  const body = file === "index.json" ? buildView(id) : buildPart(id, Number(file.replace(/\.json$/, "")));
  return Response.json(body);
}
