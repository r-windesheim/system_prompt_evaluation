"use client";

import { useSearchParams } from "next/navigation";
import { Suspense } from "react";
import { Tool } from "@/components/spet/tool";

function RunById() {
  const id = useSearchParams().get("id");
  if (!id)
    return (
      <div className="head">
        <h1>No run selected.</h1>
      </div>
    );
  return <Tool key={id} mode="saved" id={id} />;
}

export default function RunPage() {
  return (
    <Suspense>
      <RunById />
    </Suspense>
  );
}
