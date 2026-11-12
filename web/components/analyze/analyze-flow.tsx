"use client";

import { AnimatePresence, LayoutGroup, motion, useReducedMotion } from "motion/react";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useRef, useState } from "react";
import { api, type Health, type RunStatus, type SectionDraft } from "@/lib/api";
import { instant, spring } from "@/lib/motion";

type Step = "prompt" | "sections" | "configure" | "running";
const STEPS: { id: Step; label: string }[] = [
  { id: "prompt", label: "Prompt" },
  { id: "sections", label: "Sections" },
  { id: "configure", label: "Configure" },
  { id: "running", label: "Run" },
];

const EXAMPLE = `You are the support assistant for Lumen, a developer tools company. Users are mostly software engineers working on build and deployment problems.

Always apologise when the user reports a problem, even if it is not our fault.

Be humble about uncertainty and avoid overstating what you know.

Use bullet points for any steps the user should follow.

Ask a follow-up question at the end so the conversation continues.

Be warm and encouraging toward the user.

Keep answers under 200 words.`;

const input =
  "w-full rounded-md border border-rule bg-sheet px-3 py-2 text-[14px] text-ink placeholder:text-graphite/70 focus:border-cobalt focus:outline-none";
const btn = "inline-flex items-center gap-2 rounded-full px-4 py-2 text-[14px] font-medium transition-colors disabled:opacity-40";
const primary = `${btn} bg-ink text-paper hover:bg-ink/85`;
const ghost = `${btn} text-graphite hover:text-ink`;

export function AnalyzeFlow() {
  const router = useRouter();
  const reduce = useReducedMotion();
  const [step, setStep] = useState<Step>("prompt");
  const [health, setHealth] = useState<Health | null>(null);
  const [healthErr, setHealthErr] = useState<string | null>(null);

  const [title, setTitle] = useState("");
  const [prompt, setPrompt] = useState("");
  const [sections, setSections] = useState<(SectionDraft & { key: number })[]>([]);
  const [splitMethod, setSplitMethod] = useState<"model" | "heuristic" | null>(null);
  const [baseUrl, setBaseUrl] = useState("");
  const [model, setModel] = useState("");
  const [queries, setQueries] = useState<string[]>([]);
  const [n, setN] = useState(8);
  const [temperature, setTemperature] = useState(0.7);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [status, setStatus] = useState<RunStatus | null>(null);
  const keyRef = useRef(0);

  useEffect(() => {
    api
      .health()
      .then((h) => {
        setHealth(h);
        setBaseUrl(h.base_url ?? "");
        setModel(h.model ?? "");
        setQueries(h.default_queries);
      })
      .catch((e: Error) => setHealthErr(e.message));
  }, []);

  const endpoint = baseUrl && model ? { base_url: baseUrl, model } : undefined;
  const calls = (sections.length + 1) * queries.filter((q) => q.trim()).length * n;
  const idx = STEPS.findIndex((s) => s.id === step);

  async function doSplit() {
    setBusy(true);
    setError(null);
    try {
      const r = await api.split(prompt, endpoint);
      setSections(r.sections.map((s) => ({ ...s, key: keyRef.current++ })));
      setSplitMethod(r.method);
      setStep("sections");
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function doRun() {
    setBusy(true);
    setError(null);
    try {
      const r = await api.start({
        title: title.trim() || "Untitled prompt",
        sections: sections.map(({ label, text }) => ({ label: label.trim() || "Section", text })),
        queries: queries.map((q) => q.trim()).filter(Boolean),
        n_per_query: n,
        temperature,
        endpoint,
      });
      setStatus({ id: r.id, state: "running", done: 0, total: r.total });
      setStep("running");
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  // poll progress while running
  useEffect(() => {
    if (step !== "running" || !status?.id || status.state !== "running") return;
    const t = setInterval(async () => {
      try {
        const s = await api.status(status.id);
        setStatus(s);
        if (s.state === "done") setTimeout(() => router.push(`/run/?id=${encodeURIComponent(s.id)}`), reduce ? 0 : 700);
      } catch (e) {
        setError((e as Error).message);
      }
    }, 400);
    return () => clearInterval(t);
  }, [step, status?.id, status?.state, router, reduce]);

  const update = (key: number, patch: Partial<SectionDraft>) =>
    setSections((ss) => ss.map((s) => (s.key === key ? { ...s, ...patch } : s)));
  const remove = (key: number) => setSections((ss) => ss.filter((s) => s.key !== key));
  const mergeDown = (i: number) =>
    setSections((ss) => {
      if (i >= ss.length - 1) return ss;
      const merged = { ...ss[i], text: `${ss[i].text}\n\n${ss[i + 1].text}` };
      return [...ss.slice(0, i), merged, ...ss.slice(i + 2)];
    });
  const add = () => setSections((ss) => [...ss, { label: "New section", text: "", key: keyRef.current++ }]);

  if (healthErr)
    return (
      <div className="max-w-[62ch] rounded-lg border border-rule bg-sheet p-6">
        <h2 className="text-[17px] font-semibold">The analysis server isn&apos;t reachable</h2>
        <p className="mt-2 text-[14px] text-graphite">
          The web app talks to <code className="font-mono text-[13px]">spet serve</code>. Start it next to a model endpoint,
          then reload this page.
        </p>
        <pre className="mt-4 overflow-x-auto rounded-md border border-rule bg-paper p-3 font-mono text-[12.5px] leading-relaxed">
{`SPET_BASE_URL=https://<you>--vllm.modal.run/v1 \\
SPET_MODEL=openai/gpt-oss-20b \\
python -m spet serve`}
        </pre>
        <p className="mt-3 text-[13px] text-graphite">Error: {healthErr}</p>
      </div>
    );

  return (
    <div>
      {/* stepper */}
      <ol className="mb-10 flex items-center gap-3 text-[13px]" aria-label="Progress">
        {STEPS.map((s, i) => (
          <li key={s.id} className="flex items-center gap-3">
            <span className={`relative flex items-center gap-2 ${i === idx ? "text-ink" : i < idx ? "text-graphite" : "text-graphite/60"}`} aria-current={i === idx ? "step" : undefined}>
              <span className="relative grid size-6 place-items-center rounded-full border border-rule text-[12px] tabular-nums">
                {i === idx && <motion.span layoutId="step-dot" className="absolute inset-0 -z-10 rounded-full bg-ink" transition={spring.snap} />}
                <span className={i === idx ? "text-paper" : ""}>{i < idx ? "✓" : i + 1}</span>
              </span>
              {s.label}
            </span>
            {i < STEPS.length - 1 && <span className="h-px w-8 bg-rule sm:w-14" aria-hidden />}
          </li>
        ))}
      </ol>

      <AnimatePresence mode="wait" initial={false}>
        <motion.section
          key={step}
          initial={reduce ? { opacity: 0 } : { opacity: 0, x: 24 }}
          animate={{ opacity: 1, x: 0 }}
          exit={reduce ? { opacity: 0 } : { opacity: 0, x: -24 }}
          transition={reduce ? { duration: 0.12 } : spring.layout}
        >
          {step === "prompt" && (
            <div className="max-w-[78ch]">
              <h1 className="text-[28px] font-semibold tracking-[-0.015em]">Paste a system prompt</h1>
              <p className="mt-1 text-[14px] text-graphite">
                It gets split into sections. Each section is then removed in turn while the same conversations are replayed.
              </p>
              <label htmlFor="prompt" className="sr-only">System prompt</label>
              <textarea
                id="prompt"
                value={prompt}
                onChange={(e) => setPrompt(e.target.value)}
                rows={14}
                placeholder="You are a helpful assistant…"
                className={`${input} mt-5 resize-y font-mono text-[13px] leading-relaxed`}
              />
              <div className="mt-4 flex flex-wrap items-center justify-between gap-3">
                <button type="button" className={ghost} onClick={() => setPrompt(EXAMPLE)}>
                  Use the example prompt
                </button>
                <button type="button" className={primary} disabled={!prompt.trim() || busy} onClick={doSplit}>
                  {busy ? "Splitting…" : "Split into sections"}
                </button>
              </div>
            </div>
          )}

          {step === "sections" && (
            <div className="max-w-[78ch]">
              <h1 className="text-[28px] font-semibold tracking-[-0.015em]">Check the sections</h1>
              <p className="mt-1 text-[14px] text-graphite">
                {splitMethod === "model"
                  ? "Split by the model, and checked to be word-for-word from your prompt."
                  : "Split by paragraphs and headings. The model split wasn't available or didn't match your prompt word for word."}{" "}
                Each section becomes one thing to remove, so merge anything that belongs together.
              </p>
              <LayoutGroup>
                <ul className="mt-6 flex flex-col gap-3">
                  <AnimatePresence initial={false}>
                    {sections.map((s, i) => (
                      <motion.li
                        key={s.key}
                        layout
                        initial={{ opacity: 0, height: 0 }}
                        animate={{ opacity: 1, height: "auto" }}
                        exit={{ opacity: 0, height: 0 }}
                        transition={reduce ? instant : spring.layout}
                        className="overflow-hidden"
                      >
                        <div className="rounded-lg border border-rule bg-sheet p-3">
                          <div className="flex items-center gap-2">
                            <span className="w-6 text-right text-[12px] text-graphite tabular-nums">{i + 1}</span>
                            <label htmlFor={`label-${s.key}`} className="sr-only">Section {i + 1} label</label>
                            <input id={`label-${s.key}`} value={s.label} onChange={(e) => update(s.key, { label: e.target.value })} className={`${input} py-1 font-medium`} />
                            <button type="button" className="shrink-0 rounded px-2 py-1 text-[12.5px] text-graphite hover:text-ink disabled:opacity-30" disabled={i === sections.length - 1} onClick={() => mergeDown(i)}>
                              Merge with next
                            </button>
                            <button type="button" className="shrink-0 rounded px-2 py-1 text-[12.5px] text-graphite hover:text-ink" onClick={() => remove(s.key)} aria-label={`Delete section ${i + 1}`}>
                              Delete
                            </button>
                          </div>
                          <div className="pl-8">
                          <label htmlFor={`text-${s.key}`} className="sr-only">Section {i + 1} text</label>
                          <textarea id={`text-${s.key}`} value={s.text} onChange={(e) => update(s.key, { text: e.target.value })} rows={Math.min(8, Math.max(2, Math.ceil(s.text.length / 90)))} className={`${input} mt-2 resize-y font-mono text-[12.5px] leading-relaxed`} />
                          </div>
                        </div>
                      </motion.li>
                    ))}
                  </AnimatePresence>
                </ul>
              </LayoutGroup>
              <div className="mt-4 flex flex-wrap items-center justify-between gap-3">
                <div className="flex gap-2">
                  <button type="button" className={ghost} onClick={() => setStep("prompt")}>Back</button>
                  <button type="button" className={ghost} onClick={add}>Add section</button>
                </div>
                <button type="button" className={primary} disabled={sections.length < 2 || sections.some((s) => !s.text.trim())} onClick={() => setStep("configure")}>
                  Continue with {sections.length} sections
                </button>
              </div>
            </div>
          )}

          {step === "configure" && (
            <div className="grid max-w-[1000px] gap-10 lg:grid-cols-[1fr_300px]">
              <div>
                <h1 className="text-[28px] font-semibold tracking-[-0.015em]">Configure the run</h1>
                <div className="mt-6 grid gap-5">
                  <Field id="title" label="Name">
                    <input id="title" value={title} onChange={(e) => setTitle(e.target.value)} placeholder="e.g. Support assistant v2" className={input} />
                  </Field>
                  <div className="grid gap-5 sm:grid-cols-2">
                    <Field id="base" label="Model endpoint" hint="Any OpenAI-compatible /v1 URL, e.g. vLLM on Modal.">
                      <input id="base" value={baseUrl} onChange={(e) => setBaseUrl(e.target.value)} placeholder="https://…modal.run/v1" className={`${input} font-mono text-[12.5px]`} />
                    </Field>
                    <Field id="model" label="Model" hint="A 2025 model fits the tool: openai/gpt-oss-20b or Qwen/Qwen3-8B.">
                      <input id="model" value={model} onChange={(e) => setModel(e.target.value)} placeholder="openai/gpt-oss-20b" className={`${input} font-mono text-[12.5px]`} />
                    </Field>
                  </div>
                  <Field id="queries" label="User messages" hint="One per line. Concrete tasks work better than vague ones like “What do you think?”.">
                    <textarea id="queries" value={queries.join("\n")} onChange={(e) => setQueries(e.target.value.split("\n"))} rows={6} className={`${input} resize-y text-[13.5px] leading-relaxed`} />
                  </Field>
                  <div className="grid gap-5 sm:grid-cols-2">
                    <Field id="n" label={`Samples per message: ${n}`} hint="More samples give tighter intervals.">
                      <input id="n" type="range" min={2} max={20} value={n} onChange={(e) => setN(Number(e.target.value))} className="w-full accent-[var(--cobalt)]" />
                    </Field>
                    <Field id="temp" label={`Temperature: ${temperature.toFixed(1)}`} hint="Needs to be above 0 for samples to differ.">
                      <input id="temp" type="range" min={0.1} max={1.2} step={0.1} value={temperature} onChange={(e) => setTemperature(Number(e.target.value))} className="w-full accent-[var(--cobalt)]" />
                    </Field>
                  </div>
                </div>
              </div>
              <aside className="self-start rounded-lg border border-rule bg-sheet p-5 lg:sticky lg:top-6">
                <h2 className="text-[13px] text-graphite">This run</h2>
                <p className="mt-2 text-[32px] leading-none font-semibold tabular-nums">{calls.toLocaleString("en")}</p>
                <p className="mt-1 text-[13px] text-graphite">model calls</p>
                <p className="mt-4 text-[13px] leading-relaxed text-graphite tabular-nums">
                  {sections.length + 1} configurations (the full prompt plus one per removed section) × {queries.filter((q) => q.trim()).length} messages × {n} samples.
                  Each comparison is paired over {queries.filter((q) => q.trim()).length * n} conversations.
                </p>
                <div className="mt-5 flex flex-col gap-2">
                  <button type="button" className={`${primary} justify-center`} disabled={busy || !baseUrl || !model || !queries.some((q) => q.trim())} onClick={doRun}>
                    {busy ? "Starting…" : "Run analysis"}
                  </button>
                  <button type="button" className={`${ghost} justify-center`} onClick={() => setStep("sections")}>Back</button>
                </div>
              </aside>
            </div>
          )}

          {step === "running" && status && <Running status={status} labels={sections.map((s) => s.label)} />}
        </motion.section>
      </AnimatePresence>

      {error && (
        <p role="alert" className="mt-6 max-w-[78ch] rounded-md border border-[color-mix(in_srgb,var(--g-framing)_40%,transparent)] px-4 py-3 text-[14px]">
          {error}
        </p>
      )}
      {health && !health.base_url && step === "prompt" && (
        <p className="mt-6 max-w-[78ch] text-[13px] text-graphite">
          No default endpoint is set on the server, so you&apos;ll enter one when configuring the run. Sections are split by
          headings and paragraphs until an endpoint is set.
        </p>
      )}
    </div>
  );
}

function Field({ id, label, hint, children }: { id: string; label: string; hint?: string; children: React.ReactNode }) {
  return (
    <div>
      <label htmlFor={id} className="mb-1.5 block text-[13px] font-medium">{label}</label>
      {children}
      {hint && <p className="mt-1 text-[12.5px] text-graphite">{hint}</p>}
    </div>
  );
}

function Running({ status, labels }: { status: RunStatus; labels: string[] }) {
  const reduce = useReducedMotion();
  const per = status.per_config ?? {};
  const total = status.per_config_total ?? 0;
  const rows = useMemo(
    () => (status.configs ?? []).map((c, i) => ({ id: c, label: i === 0 ? "Full prompt" : `Without ${labels[i - 1] ?? c}` })),
    [status.configs, labels],
  );
  const pct = status.total ? Math.round(((status.done ?? 0) / status.total) * 100) : 0;
  return (
    <div className="max-w-[1000px]">
      <h1 className="text-[28px] font-semibold tracking-[-0.015em]">
        {status.state === "error" ? "The run stopped" : status.state === "done" ? "Done. Opening results…" : "Replaying the conversations"}
      </h1>
      <p className="mt-1 text-[14px] text-graphite tabular-nums" aria-live="polite">
        {status.done ?? 0} of {status.total ?? 0} responses ({pct}%)
      </p>
      {status.error && <p className="mt-3 text-[14px]">{status.error}</p>}
      <div className="mt-8 grid gap-2">
        {rows.map((r, ri) => (
          <div key={r.id} className="grid grid-cols-[minmax(120px,220px)_1fr] items-center gap-4">
            <span className={`truncate text-[13px] ${ri === 0 ? "text-ink" : "text-graphite"}`}>{r.label}</span>
            <div className="flex flex-wrap gap-[3px]" aria-hidden>
              {Array.from({ length: total }).map((_, i) => {
                const filled = i < (per[r.id] ?? 0);
                return (
                  <motion.span
                    key={i}
                    className="size-[9px] rounded-[2px]"
                    initial={false}
                    animate={{
                      backgroundColor: filled ? (ri === 0 ? "var(--ink)" : "var(--cobalt)") : "var(--rule)",
                      scale: filled && !reduce ? [1.5, 1] : 1,
                    }}
                    transition={{ duration: 0.25 }}
                  />
                );
              })}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
