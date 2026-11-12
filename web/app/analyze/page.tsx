import type { Metadata } from "next";
import Link from "next/link";
import { AnalyzeFlow } from "@/components/analyze/analyze-flow";
import { hasApi } from "@/lib/api";
import { REPO_URL } from "@/lib/site";

export const metadata: Metadata = { title: "Analyse a prompt" };

export default function Analyze() {
  if (!hasApi)
    return (
      <div className="max-w-[62ch] pt-10">
        <h1 className="text-[28px] font-semibold tracking-[-0.015em]">Analyse your own prompt</h1>
        <p className="mt-3 text-[15px] text-graphite">
          This hosted version only shows recorded runs, because analysing a prompt needs a model to answer hundreds of
          conversations. To analyse your own prompt, run SPET locally and point it at any OpenAI-compatible endpoint.
        </p>
        <pre className="mt-5 overflow-x-auto rounded-md border border-rule bg-sheet p-4 font-mono text-[12.5px] leading-relaxed">
{`git clone ${REPO_URL}
cd system_prompt_evaluation && pip install -e ".[serve]"
SPET_BASE_URL=https://<you>--vllm.modal.run/v1 SPET_MODEL=openai/gpt-oss-20b \\
  python -m spet serve
cd web && NEXT_PUBLIC_SPET_API=http://localhost:8000 npm run dev`}
        </pre>
        <p className="mt-5 text-[14px]">
          <Link href="/" className="underline underline-offset-4">Browse the recorded runs</Link>
        </p>
      </div>
    );
  return (
    <div className="pt-8">
      <AnalyzeFlow />
    </div>
  );
}
