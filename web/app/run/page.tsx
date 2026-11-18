import { RunByQuery } from "@/components/spet/run-by-query";
import { readoutIds } from "@/lib/view.server";

export default function RunPage() {
  // which recorded runs have a readout is known at build time, so no request is made to find out
  return <RunByQuery readouts={readoutIds()} />;
}
