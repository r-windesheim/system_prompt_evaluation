"""Attention pilot and screen: how much do gpt-oss-20b's reasoning and answer tokens attend to each prompt part?

One-shot Modal functions (not a server). Run them from the repo root:

    modal run deploy/modal_attention.py --smoke     # pilot: 1 generation, 300 new tokens, prints timings
    modal run deploy/modal_attention.py            # the 20-generation pilot -> runs_out/attention-pilot.json

    # the screen (spet/screen.py, docs/discovery.md "Attention screen"): every question of a run spec,
    # rendered the way vLLM sends it, N samples each, lift per (part, question)
    modal run deploy/modal_attention.py::screen --smoke     # render all prompts + 1 generation of 300 tokens
    modal run deploy/modal_attention.py::screen             # full screen -> runs_out/<spec id>-screen.json
    modal run deploy/modal_attention.py::screen --spec examples/x.yaml --samples 4 --date 2026-11-20

The screen differs from the pilot in three ways: the prompt is rendered with openai-harmony exactly as vLLM
0.18.1 renders a chat request for gpt-oss (below), questions and parts come from a run spec, and the container
returns only per-layer means over the reasoning and answer tokens, not per-token mass.

The pilot's own notes follow.

Nothing stays deployed: `modal run` starts an ephemeral app and the GPU is released when the
function returns. This app is separate from `spet-vllm` and only reads the same `huggingface-cache`
volume and the same pinned model revision.

Method (all of it runs on the GPU; full attention matrices never leave the container):

1. Prompt. Rendered with the model's own chat template (`apply_chat_template`, system = the full
   joined prompt, user = the question, `reasoning_effort="low"`). The template puts our system text
   in a `developer` block under "# Instructions" after its own system header. vLLM 0.18.1 (the
   engine of the SPET run) renders the same request differently: harmony system header, then our
   text as a second `system` message without the "# Instructions" header. Both stamp today's date.
   The vLLM layout is rendered with openai-harmony and saved for comparison; attention is measured
   on the template layout only.
2. Generation. `model.generate` in batches with left padding, temperature 0.7, top_p 1, top_k 0
   (vLLM applies no top-k by default), one fixed torch seed per batch. Up to 4000 new tokens like
   the run. Weights are MXFP4 dequantized to bf16 (vLLM runs MXFP4 kernels), so these are fresh
   samples from very nearly the same distribution, not replays of the run's answers.
3. Attention. One teacher-forced forward pass per finished sequence, unpadded, with the eager
   attention implementation. With the same tokens this gives the same weights as recording during
   decoding, and it avoids padding and per-step bookkeeping. A forward hook on every layer's
   `self_attn` takes the weights the eager kernel returns, keeps only the query rows of the
   reasoning and answer, averages over heads in fp32, and sums the mass on each key bucket with one
   matmul. gpt-oss has a learned attention sink per head; eager drops the sink column, so each row
   sums to 1 - sink. The sink mass is saved as its own column, so rows sum to 1 with it.

Key buckets (columns, in order): the 16 parts, user question text, reasoning, answer, other
(template/special/separator tokens), sink. A token belongs to a span if its first character lies
inside the span's characters; the blank-line separators between parts count as "other".

Layers alternate: even layers are sliding-window (128 tokens), odd layers attend to the whole
sequence. On sliding layers, tokens more than 128 positions after the prompt cannot see it at all.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import modal

MODEL_NAME = "openai/gpt-oss-20b"
MODEL_REVISION = "d666cf3b67006cf8227666739edf25164aaffdeb"  # same pin as deploy/modal_vllm.py
GPU = "H100"
MINUTES = 60

SCREEN_GEN_BATCH = 16      # 4 questions x 4 samples per generate() call
SCREEN_CHUNK_QUESTIONS = 16  # questions per container call (64 generations at 4 samples)

# The pilot: questions 3-5 (Links and videos, the one part the removal run confirmed) plus seven
# questions written for seven other parts. Two samples each.
PILOT_QUESTIONS = [3, 4, 5, 1, 7, 10, 13, 15, 24, 31]
N_SAMPLES = 2
TEMPERATURE = 0.7
MAX_NEW_TOKENS = 4000
SEED = 0
GEN_BATCH = 10  # sequences per generate() call; bounds prefill memory on one H100

image = (
    modal.Image.debian_slim(python_version="3.12")
    .uv_pip_install(
        "torch==2.8.0",
        "transformers==4.57.1",
        "accelerate==1.10.1",
        "huggingface_hub[hf_transfer]==0.36.0",
        "jinja2>=3.1",
        "openai-harmony==0.0.8",
    )
    .env({"HF_HUB_ENABLE_HF_TRANSFER": "1"})
)

hf_cache = modal.Volume.from_name("huggingface-cache", create_if_missing=False)

app = modal.App("spet-attention")


@app.function(image=image, gpu=GPU, timeout=30 * MINUTES, volumes={"/root/.cache/huggingface": hf_cache})
def attention_pilot(*args, **kwargs) -> str:
    import traceback

    try:
        return json.dumps(_pilot(*args, **kwargs))  # plain JSON: no torch types reach the client
    except Exception:  # torch exception classes can't be unpickled by a torch-less client
        raise RuntimeError(traceback.format_exc()) from None


def _pilot(sections: list[dict], queries: list[str], items: list[list[int]],
           max_new_tokens: int = MAX_NEW_TOKENS, temperature: float = TEMPERATURE,
           seed: int = SEED, gen_batch: int = GEN_BATCH) -> dict:
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer, Mxfp4Config

    t0 = time.time()
    timings: dict[str, float] = {}
    tok = AutoTokenizer.from_pretrained(MODEL_NAME, revision=MODEL_REVISION)
    model = AutoModelForCausalLM.from_pretrained(
        MODEL_NAME, revision=MODEL_REVISION, dtype=torch.bfloat16, device_map="cuda",
        attn_implementation="eager", quantization_config=Mxfp4Config(dequantize=True),
    )
    model.eval()
    timings["load_s"] = time.time() - t0
    cfg = model.config
    assert model.config._attn_implementation == "eager", model.config._attn_implementation

    sp = {name: tok.convert_tokens_to_ids(name) for name in
          ["<|start|>", "<|end|>", "<|message|>", "<|channel|>", "<|return|>", "<|call|>", "<|endoftext|>"]}
    stop_ids = {sp["<|return|>"], sp["<|call|>"], sp["<|endoftext|>"]}
    pad_id = cfg.pad_token_id if cfg.pad_token_id is not None else sp["<|endoftext|>"]

    texts = [s["text"].strip() for s in sections]
    system = "\n\n".join(texts)  # spet.schedule.join_sections
    labels = [s["label"] for s in sections]
    n_parts = len(texts)
    B_USER, B_REASON, B_ANSWER, B_OTHER = n_parts, n_parts + 1, n_parts + 2, n_parts + 3
    columns = labels + ["user", "reasoning", "answer", "other", "sink"]

    # ---- 1. render prompts and locate the parts --------------------------------------------
    def render(query: str) -> dict:
        msgs = [{"role": "system", "content": system}, {"role": "user", "content": query}]
        text = tok.apply_chat_template(msgs, tokenize=False, add_generation_prompt=True, reasoning_effort="low")
        ids_t = tok.apply_chat_template(msgs, tokenize=True, add_generation_prompt=True, reasoning_effort="low")
        if isinstance(ids_t, dict):
            ids_t = ids_t["input_ids"]
        enc = tok(text, add_special_tokens=False, return_offsets_mapping=True)
        ids, offs = enc["input_ids"], enc["offset_mapping"]
        assert ids == list(ids_t), "re-tokenized rendered prompt differs from the template's ids"
        assert "Reasoning: low" in text, "reasoning_effort did not reach the template"
        sys_at = text.find(system)
        assert sys_at >= 0 and text.count(system) == 1, "joined system prompt not found exactly once"
        spans, cursor = [], sys_at
        for k, t in enumerate(texts):
            at = text.find(t, cursor)
            assert at >= 0 and at + len(t) <= sys_at + len(system), f"part {k} not found in its place"
            spans.append((at, at + len(t)))
            cursor = at + len(t)
        q_at = text.find(query, sys_at + len(system))
        assert q_at >= 0, "question not found after the system prompt"
        char_spans = spans + [(q_at, q_at + len(query))]
        bucket = []
        for (a, _b) in offs:
            for j, (s0, s1) in enumerate(char_spans):
                if s0 <= a < s1:
                    bucket.append(j)
                    break
            else:
                bucket.append(B_OTHER)
        counts = [bucket.count(j) for j in range(n_parts + 1)]
        assert all(c > 0 for c in counts), f"empty span: {counts}"
        return {"text": text, "ids": ids, "bucket": bucket, "char_spans": char_spans, "counts": counts}

    rendered = {qi: render(queries[qi]) for qi in sorted({qi for qi, _ in items})}

    vllm_layout = None
    try:  # how vLLM 0.18.1 renders the same request (serve/render/serving.py + harmony_utils.py)
        from openai_harmony import (Conversation, HarmonyEncodingName, Message, ReasoningEffort, Role,
                                    SystemContent, TextContent, load_harmony_encoding)
        enc_h = load_harmony_encoding(HarmonyEncodingName.HARMONY_GPT_OSS)
        sysc = SystemContent.new().with_reasoning_effort(ReasoningEffort.LOW) \
            .with_conversation_start_date(time.strftime("%Y-%m-%d"))
        q0 = queries[items[0][0]]
        conv = Conversation.from_messages([
            Message.from_role_and_content(Role.SYSTEM, sysc),
            Message.from_role_and_contents(Role.SYSTEM, [TextContent(text=system)]),
            Message.from_role_and_contents(Role.USER, [TextContent(text=q0)]),
        ])
        vids = enc_h.render_conversation_for_completion(conv, Role.ASSISTANT)
        vllm_layout = {"query_idx": items[0][0], "text": tok.decode(vids), "n_tokens": len(vids)}
    except Exception as e:  # documentation only; never blocks the pilot
        vllm_layout = {"error": repr(e)}

    # ---- 2. generate --------------------------------------------------------------------
    t1 = time.time()
    torch.manual_seed(seed)
    gens: list[list[int]] = []
    for b0 in range(0, len(items), gen_batch):
        chunk = items[b0:b0 + gen_batch]
        prompts = [rendered[qi]["ids"] for qi, _ in chunk]
        width = max(map(len, prompts))
        input_ids = torch.tensor([[pad_id] * (width - len(p)) + p for p in prompts], device="cuda")
        attn = torch.tensor([[0] * (width - len(p)) + [1] * len(p) for p in prompts], device="cuda")
        with torch.inference_mode():
            out = model.generate(input_ids=input_ids, attention_mask=attn, do_sample=True,
                                 temperature=temperature, top_p=1.0, top_k=0, max_new_tokens=max_new_tokens,
                                 pad_token_id=pad_id, eos_token_id=sorted(stop_ids))
        for row in out[:, width:].tolist():
            cut = next((i for i, t in enumerate(row) if t in stop_ids), None)
            gens.append(row[:cut] + ([row[cut]] if cut is not None else []))
        del out, input_ids, attn
        torch.cuda.empty_cache()
    timings["generate_s"] = time.time() - t1

    # ---- 3. teacher-forced pass with reducing hooks --------------------------------------
    state: dict = {"active": False}

    def hook(module, _inp, output):
        if not state["active"]:
            return None
        w = output[1]
        assert w is not None, "attention weights not returned; is the eager implementation active?"
        r0, r1 = state["rows"]
        x = w[0, :, r0:r1, :].float().mean(0)  # (rows, keys), averaged over heads
        mass = x @ state["onehot"]  # (rows, buckets)
        sink = 1.0 - x.sum(-1, keepdim=True)
        state["out"][module.layer_idx] = torch.cat([mass, sink], -1).cpu()
        return None

    handles = [layer.self_attn.register_forward_hook(hook) for layer in model.model.layers]

    def segments(gen: list[int]) -> dict:
        """Channel -> (start, end) of message content, indices into gen."""
        segs: dict = {}
        i = 0
        while i < len(gen):
            if gen[i] == sp["<|channel|>"]:
                m = next((j for j in range(i + 1, len(gen)) if gen[j] == sp["<|message|>"]), None)
                if m is None:
                    break
                name = tok.decode(gen[i + 1:m]).strip()
                e = next((j for j in range(m + 1, len(gen)) if gen[j] in (sp["<|end|>"], *stop_ids)), len(gen))
                segs.setdefault(name, []).append((m + 1, e))
                i = e
            i += 1
        return segs

    t2 = time.time()
    results = []
    for (qi, si), gen in zip(items, gens):
        r = rendered[qi]
        P = len(r["ids"])
        finished = bool(gen) and gen[-1] in stop_ids
        body = gen[:-1] if finished else gen  # the stop token is never a query
        segs = segments(body)
        reason = segs.get("analysis", [None])[0]
        answer = segs.get("final", [None])[0]
        seq = r["ids"] + body
        L = len(seq)
        bucket = r["bucket"] + [B_OTHER] * len(body)
        if reason:
            for j in range(*reason):
                bucket[P + j] = B_REASON
        if answer:
            for j in range(*answer):
                bucket[P + j] = B_ANSWER
        onehot = torch.zeros(L, n_parts + 4, device="cuda")
        onehot[torch.arange(L), torch.tensor(bucket)] = 1.0
        live = [s for s in (reason, answer) if s and s[1] > s[0]]
        blocks = {"reasoning": None, "answer": None}
        if live:  # one pass; the query rows cover reasoning through answer and are split afterwards
            lo, hi = min(s[0] for s in live), max(s[1] for s in live)
            state.update(active=True, rows=(P + lo, P + hi), onehot=onehot, out={})
            with torch.inference_mode():
                model(input_ids=torch.tensor([seq], device="cuda"), use_cache=False)
            state["active"] = False
            full = torch.stack([state["out"][li] for li in range(cfg.num_hidden_layers)])
        for name, span in (("reasoning", reason), ("answer", answer)):
            if not span or span[1] <= span[0]:
                continue
            arr = full[:, span[0] - lo:span[1] - lo, :]  # (layers, tokens, columns)
            blocks[name] = {
                "n_tokens": span[1] - span[0],
                "tokens": [tok.decode([t]) for t in body[span[0]:span[1]]],
                "row_sum_min": round(float(arr.sum(-1).min()), 4),
                "row_sum_max": round(float(arr.sum(-1).max()), 4),
                "mass": [[[round(float(v), 5) for v in row] for row in layer] for layer in arr.tolist()],
            }
        results.append({
            "query_idx": qi, "sample_idx": si, "target_part": qi // 3,
            "question": queries[qi],
            "finished": finished, "n_prompt_tokens": P, "n_generated_tokens": len(gen),
            "has_reasoning": reason is not None, "has_answer": answer is not None,
            "channels": sorted(segs),
            "reasoning_text": tok.decode(body[reason[0]:reason[1]]) if reason else "",
            "answer_text": tok.decode(body[answer[0]:answer[1]]) if answer else "",
            "bucket_token_counts": {
                "parts": r["counts"][:n_parts], "user": r["counts"][n_parts],
                "reasoning": reason[1] - reason[0] if reason else 0,
                "answer": answer[1] - answer[0] if answer else 0,
                "other": bucket.count(B_OTHER),
            },
            "reasoning": blocks["reasoning"],
            "answer": blocks["answer"],
        })
    for h in handles:
        h.remove()
    timings["attention_s"] = time.time() - t2
    timings["total_s"] = time.time() - t0

    first = rendered[items[0][0]]
    return {
        "pilot": "attention", "model": MODEL_NAME, "model_revision": MODEL_REVISION,
        "settings": {
            "temperature": temperature, "top_p": 1.0, "top_k": 0, "max_new_tokens": max_new_tokens,
            "seed": seed, "seed_scope": f"one torch.manual_seed before generation; batches of {gen_batch}, left-padded",
            "reasoning_effort": "low", "weights": "MXFP4 dequantized to bf16 (vLLM runs MXFP4 kernels)",
            "attn_implementation": "eager", "attention_recorded": "one teacher-forced pass per finished sequence",
            "head_reduction": "mean over 64 heads, fp32, of the eager softmax (computed in bf16)",
            "torch": str(torch.__version__), "transformers": __import__("transformers").__version__,
            "gpu": torch.cuda.get_device_name(0), "peak_mem_gb": round(torch.cuda.max_memory_allocated() / 1e9, 2),
        },
        "layer_types": list(cfg.layer_types), "sliding_window": cfg.sliding_window,
        "columns": columns, "part_labels": labels,
        "rendered_prompt_example": {
            "query_idx": items[0][0], "text": first["text"], "n_tokens": len(first["ids"]),
            "part_char_spans": first["char_spans"][:n_parts], "user_char_span": first["char_spans"][n_parts],
        },
        "vllm_layout_example": vllm_layout,
        "timings": {k: round(v, 1) for k, v in timings.items()},
        "items": results,
    }


@app.local_entrypoint()
def main(smoke: bool = False, out: str = ""):
    import yaml

    root = Path(__file__).resolve().parents[1]
    spec = yaml.safe_load((root / "examples" / "sonnet35-july2024.yaml").read_text())
    sections = [{"label": s["label"], "text": s["text"]} for s in spec["sections"]]
    # the pilot used the first 48 questions (three per part, in part order: target = query_idx // 3); the
    # example has since grown, with questions given as {text, targets}
    spec["queries"] = [q["text"] if isinstance(q, dict) else q for q in spec["queries"][:48]]
    assert len(sections) == 16 and len(spec["queries"]) == 48
    if smoke:
        items, kw = [[3, 0]], {"max_new_tokens": 300}
    else:
        items, kw = [[q, s] for q in PILOT_QUESTIONS for s in range(N_SAMPLES)], {}
    t = time.time()
    res = json.loads(attention_pilot.remote(sections, spec["queries"], items, **kw))
    res["timings"]["client_wall_s"] = round(time.time() - t, 1)
    path = Path(out) if out else root / "runs_out" / ("attention-smoke.json" if smoke else "attention-pilot.json")
    path.write_text(json.dumps(res))
    print(f"wrote {path} ({path.stat().st_size / 1e6:.1f} MB)")
    print("timings:", res["timings"], "peak_mem_gb:", res["settings"]["peak_mem_gb"])
    for it in res["items"]:
        a = it["answer"]
        print(it["query_idx"], it["sample_idx"], "finished" if it["finished"] else "TRUNCATED",
              "channels", it["channels"], "answer_tokens", a and a["n_tokens"],
              "row_sums", a and (a["row_sum_min"], a["row_sum_max"]))



# ======================================================================================================
# Screen
# ======================================================================================================

def make_vllm_renderer(tok, texts: list[str], date: str, reasoning_effort: str | None):
    """render(query) -> ids, text, per-token bucket (part k, user = len(texts), other = len(texts) + 3) and counts,
    for the prompt vLLM 0.18.1 builds from a chat request [system: joined parts, user: query] for gpt-oss.

    vllm/entrypoints/serve/render/serving.py::_make_request_with_harmony: get_system_message(reasoning_effort)
    (SystemContent.new(), the effort if given, conversation start date = the request day unless
    VLLM_SYSTEM_START_DATE is set, which deploy/modal_vllm.py does not do), no developer message without tools,
    then each chat message as Message.from_role_and_contents(role, [TextContent]), so our system text becomes a
    second `system` message, then render_conversation_for_completion(conversation, Role.ASSISTANT).
    Every check is an assert: a layout that differs, or a part that is not found exactly in place, stops the run.
    """
    from openai_harmony import (Conversation, HarmonyEncodingName, Message, ReasoningEffort, Role, SystemContent,
                                TextContent, load_harmony_encoding)

    system = "\n\n".join(texts)  # spet.schedule.join_sections
    n_parts = len(texts)
    B_OTHER = n_parts + 3
    enc_h = load_harmony_encoding(HarmonyEncodingName.HARMONY_GPT_OSS)
    effort = {"low": ReasoningEffort.LOW, "medium": ReasoningEffort.MEDIUM, "high": ReasoningEffort.HIGH}

    def render(query: str) -> dict:
        sysc = SystemContent.new()
        if reasoning_effort is not None:
            sysc = sysc.with_reasoning_effort(effort[reasoning_effort])
        sysc = sysc.with_conversation_start_date(date)
        conv = Conversation.from_messages([
            Message.from_role_and_content(Role.SYSTEM, sysc),
            Message.from_role_and_contents(Role.SYSTEM, [TextContent(text=system)]),
            Message.from_role_and_contents(Role.USER, [TextContent(text=query)]),
        ])
        ids = list(enc_h.render_conversation_for_completion(conv, Role.ASSISTANT))
        text = tok.decode(ids)
        enc = tok(text, add_special_tokens=False, return_offsets_mapping=True)
        assert enc["input_ids"] == ids, "re-tokenized vLLM prompt differs from the harmony ids"
        tail = f"<|end|><|start|>system<|message|>{system}<|end|><|start|>user<|message|>{query}<|end|><|start|>assistant"
        assert text.startswith("<|start|>system<|message|>") and text.endswith(tail), "not the vLLM layout"
        assert f"Current date: {date}" in text and text.count(system) == 1
        if reasoning_effort is not None:
            assert f"Reasoning: {reasoning_effort}" in text
        sys_at = len(text) - len(tail) + len("<|end|><|start|>system<|message|>")
        spans, cursor = [], sys_at
        for k, t in enumerate(texts):
            at = text.find(t, cursor)
            assert at >= 0 and at + len(t) <= sys_at + len(system), f"part {k} not found in its place"
            spans.append((at, at + len(t)))
            cursor = at + len(t)
        q_at = len(text) - len(f"{query}<|end|><|start|>assistant")
        assert text[q_at:q_at + len(query)] == query
        char_spans = spans + [(q_at, q_at + len(query))]
        bucket = []
        for (a, _b) in enc["offset_mapping"]:
            bucket.append(next((j for j, (s0, s1) in enumerate(char_spans) if s0 <= a < s1), B_OTHER))
        counts = [bucket.count(j) for j in range(n_parts + 1)]
        assert all(c > 0 for c in counts), f"empty span: {counts}"
        return {"text": text, "ids": ids, "bucket": bucket, "char_spans": char_spans, "counts": counts}

    return render


@app.function(image=image, gpu=GPU, timeout=60 * MINUTES, volumes={"/root/.cache/huggingface": hf_cache},
              max_containers=4)
def screen_chunk(*args, **kwargs) -> str:
    import traceback

    try:
        return json.dumps(_screen(*args, **kwargs))
    except Exception:
        raise RuntimeError(traceback.format_exc()) from None


def _screen(sections: list[str], queries: list[str], items: list[list[int]], *, date: str,
            reasoning_effort: str | None, max_new_tokens: int, temperature: float, seed: int,
            gen_batch: int = SCREEN_GEN_BATCH, render_all: bool = False) -> dict:
    """Generate ``items`` = [[query_idx, sample_idx], ...] with the full prompt and return, per generation, the
    head-averaged attention mass of the reasoning and answer tokens on each key bucket, averaged over the block's
    tokens, for every full-attention layer. ``render_all`` also renders and checks every question's prompt."""
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer, Mxfp4Config

    t0 = time.time()
    timings: dict[str, float] = {}
    tok = AutoTokenizer.from_pretrained(MODEL_NAME, revision=MODEL_REVISION)
    texts = [t.strip() for t in sections]
    n_parts = len(texts)
    B_OTHER = n_parts + 3
    render = make_vllm_renderer(tok, texts, date, reasoning_effort)

    need = sorted({qi for qi, _ in items})
    rendered = {qi: render(queries[qi]) for qi in (range(len(queries)) if render_all else need)}
    timings["render_s"] = time.time() - t0
    first = rendered[need[0]] if need else rendered[0]
    layout = {"renderer": "openai-harmony, as vLLM 0.18.1 _make_request_with_harmony", "date": date,
              "reasoning_effort": reasoning_effort, "n_rendered": len(rendered),
              "spans_checked": True, "example_query_idx": need[0] if need else 0,
              "example_text": first["text"], "example_n_tokens": len(first["ids"]),
              "example_part_token_counts": first["counts"][:n_parts]}
    if not items:
        return {"layout": layout, "generations": [], "timings": timings}

    model = AutoModelForCausalLM.from_pretrained(
        MODEL_NAME, revision=MODEL_REVISION, dtype=torch.bfloat16, device_map="cuda",
        attn_implementation="eager", quantization_config=Mxfp4Config(dequantize=True),
    )
    model.eval()
    cfg = model.config
    assert cfg._attn_implementation == "eager", cfg._attn_implementation
    full_layers = [i for i, t in enumerate(cfg.layer_types) if t == "full_attention"]
    timings["load_s"] = time.time() - t0 - timings["render_s"]
    sp = {name: tok.convert_tokens_to_ids(name) for name in
          ["<|start|>", "<|end|>", "<|message|>", "<|channel|>", "<|return|>", "<|call|>", "<|endoftext|>"]}
    stop_ids = {sp["<|return|>"], sp["<|call|>"], sp["<|endoftext|>"]}
    pad_id = cfg.pad_token_id if cfg.pad_token_id is not None else sp["<|endoftext|>"]

    # ---- 2. generate (as the pilot) ------------------------------------------------------------
    t1 = time.time()
    gens: list[list[int]] = []
    batch_seeds: list[int] = []
    for b0 in range(0, len(items), gen_batch):
        chunk = items[b0:b0 + gen_batch]
        bseed = seed * 1_000_003 + chunk[0][0] * 1009 + chunk[0][1]
        torch.manual_seed(bseed)
        prompts = [rendered[qi]["ids"] for qi, _ in chunk]
        width = max(map(len, prompts))
        input_ids = torch.tensor([[pad_id] * (width - len(p)) + p for p in prompts], device="cuda")
        attn = torch.tensor([[0] * (width - len(p)) + [1] * len(p) for p in prompts], device="cuda")
        with torch.inference_mode():
            out = model.generate(input_ids=input_ids, attention_mask=attn, do_sample=True,
                                 temperature=temperature, top_p=1.0, top_k=0, max_new_tokens=max_new_tokens,
                                 pad_token_id=pad_id, eos_token_id=sorted(stop_ids))
        for row in out[:, width:].tolist():
            cut = next((i for i, t in enumerate(row) if t in stop_ids), None)
            gens.append(row[:cut] + ([row[cut]] if cut is not None else []))
            batch_seeds.append(bseed)
        del out, input_ids, attn
        torch.cuda.empty_cache()
    timings["generate_s"] = time.time() - t1

    # ---- 3. teacher-forced pass; per full layer, the block means of the bucket masses ----------
    state: dict = {"active": False}

    def hook(module, _inp, output):
        if not state["active"] or module.layer_idx not in state["layers"]:
            return None
        w = output[1]
        assert w is not None, "attention weights not returned; is the eager implementation active?"
        r0, r1 = state["rows"]
        parts = []
        for c0 in range(r0, r1, 1024):  # in row chunks: a 4,000-token answer would otherwise copy GBs to fp32
            x = w[0, :, c0:min(r1, c0 + 1024), :].float().mean(0)  # (rows, keys), mean over heads
            parts.append(torch.cat([x @ state["onehot"], 1.0 - x.sum(-1, keepdim=True)], -1))  # (rows, buckets + sink)
        mass = torch.cat(parts, 0)
        state["out"][module.layer_idx] = {name: mass[a - r0:b - r0].mean(0).cpu() for name, (a, b) in state["blocks"]}
        return None

    handles = [layer.self_attn.register_forward_hook(hook) for layer in model.model.layers]

    def segments(gen: list[int]) -> dict:
        segs: dict = {}
        i = 0
        while i < len(gen):
            if gen[i] == sp["<|channel|>"]:
                m = next((j for j in range(i + 1, len(gen)) if gen[j] == sp["<|message|>"]), None)
                if m is None:
                    break
                name = tok.decode(gen[i + 1:m]).strip()
                e = next((j for j in range(m + 1, len(gen)) if gen[j] in (sp["<|end|>"], *stop_ids)), len(gen))
                segs.setdefault(name, []).append((m + 1, e))
                i = e
            i += 1
        return segs

    t2 = time.time()
    results = []
    for (qi, si), gen, bseed in zip(items, gens, batch_seeds):
        r = rendered[qi]
        P = len(r["ids"])
        finished = bool(gen) and gen[-1] in stop_ids
        body = gen[:-1] if finished else gen
        segs = segments(body)
        reason = segs.get("analysis", [None])[0]
        answer = segs.get("final", [None])[0]
        seq = r["ids"] + body
        L = len(seq)
        bucket = r["bucket"] + [B_OTHER] * len(body)
        for span, b_id in ((reason, n_parts + 1), (answer, n_parts + 2)):
            if span:
                for j in range(*span):
                    bucket[P + j] = b_id
        live = [(name, (P + s[0], P + s[1])) for name, s in (("reasoning", reason), ("answer", answer)) if s and s[1] > s[0]]
        blocks = {"reasoning": None, "answer": None}
        if live:
            onehot = torch.zeros(L, n_parts + 4, device="cuda")
            onehot[torch.arange(L), torch.tensor(bucket)] = 1.0
            lo, hi = min(a for _, (a, _) in live), max(b for _, (_, b) in live)
            state.update(active=True, rows=(lo, hi), onehot=onehot, out={}, layers=set(full_layers), blocks=live)
            with torch.inference_mode():
                model(input_ids=torch.tensor([seq], device="cuda"), use_cache=False)
            state["active"] = False
            for name, (a, b) in live:
                blocks[name] = {"n_tokens": b - a,
                                "mass": [[round(float(v), 6) for v in state["out"][li][name].tolist()] for li in full_layers]}
            del onehot
        results.append({
            "query_idx": qi, "sample_idx": si, "finished": finished, "n_generated_tokens": len(gen),
            "batch_seed": bseed, "n_prompt_tokens": P, "part_token_counts": r["counts"][:n_parts],
            "user_tokens": r["counts"][n_parts], "channels": sorted(segs),
            "reasoning": blocks["reasoning"], "answer": blocks["answer"],
            "reasoning_text": tok.decode(body[reason[0]:reason[1]]) if reason else "",
            "answer_text": tok.decode(body[answer[0]:answer[1]]) if answer else "",
        })
    for h in handles:
        h.remove()
    timings["attention_s"] = time.time() - t2
    timings["total_s"] = time.time() - t0
    return {
        "layout": layout, "layer_types": list(cfg.layer_types), "layers_recorded": full_layers,
        "settings": {
            "temperature": temperature, "top_p": 1.0, "top_k": 0, "max_new_tokens": max_new_tokens, "seed": seed,
            "seed_scope": f"torch.manual_seed per generate() batch of {gen_batch}, left-padded (batch_seed per record)",
            "reasoning_effort": reasoning_effort, "weights": "MXFP4 dequantized to bf16 (vLLM runs MXFP4 kernels)",
            "attn_implementation": "eager", "head_reduction": "mean over heads, fp32",
            "block_reduction": "mean over the block's tokens, per full-attention layer",
            "torch": str(torch.__version__), "transformers": __import__("transformers").__version__,
            "gpu": torch.cuda.get_device_name(0), "peak_mem_gb": round(torch.cuda.max_memory_allocated() / 1e9, 2),
        },
        "timings": {k: round(v, 1) for k, v in timings.items()},
        "generations": results,
    }


@app.local_entrypoint()
def screen(spec: str = "examples/sonnet35-july2024.yaml", samples: int = 4, out: str = "", smoke: bool = False,
           date: str = "", chunk: int = SCREEN_CHUNK_QUESTIONS, gen_batch: int = SCREEN_GEN_BATCH, seed: int = 0):
    import sys

    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root))
    from spet import screen as S  # imported here so the container never needs the package
    from spet.cli import load_spec

    path = Path(spec) if Path(spec).is_absolute() else root / spec
    rs, pcfg = load_spec(path)
    extra = pcfg.get("extra") or {}
    date = date or time.strftime("%Y-%m-%d")
    kw = dict(date=date, reasoning_effort=extra.get("reasoning_effort"), temperature=rs.temperature,
              max_new_tokens=int(pcfg.get("max_tokens", MAX_NEW_TOKENS)), seed=seed, gen_batch=gen_batch)
    head = {"fingerprint": S.fingerprint(rs.sections, rs.queries), "spec_id": rs.id, "model": MODEL_NAME,
            "model_revision": MODEL_REVISION, "n_questions": len(rs.queries), "n_samples": 1 if smoke else samples,
            "part_labels": rs.section_labels}
    t = time.time()
    if smoke:  # every prompt rendered and checked, one short generation through the same code path
        kw["max_new_tokens"] = 300
        res = json.loads(screen_chunk.remote(rs.sections, rs.queries, [[3, 0]], render_all=True, **kw))
        parts = [res]
    else:
        qs = list(range(len(rs.queries)))
        chunks = [[[q, s] for q in qs[i:i + chunk] for s in range(samples)] for i in range(0, len(qs), chunk)]
        # each chunk is saved as it arrives, so a failed chunk does not throw away the others
        part_dir = root / "runs_out" / f"{rs.id}-screen-chunks"
        part_dir.mkdir(parents=True, exist_ok=True)
        parts = []
        for i, x in enumerate(screen_chunk.map([rs.sections] * len(chunks), [rs.queries] * len(chunks), chunks,
                                               kwargs=kw)):
            (part_dir / f"chunk-{i:02d}.json").write_text(x)
            parts.append(json.loads(x))
            print(f"chunk {i + 1}/{len(chunks)} done: {parts[-1]['timings']}")
    layout = dict(parts[0]["layout"], n_rendered=sum(p["layout"]["n_rendered"] for p in parts))
    settings = dict(parts[0]["settings"], peak_mem_gb=max(p["settings"]["peak_mem_gb"] for p in parts),
                    gpu=sorted({p["settings"]["gpu"] for p in parts}))
    raw = {**head, "layer_types": parts[0]["layer_types"], "layers_recorded": parts[0]["layers_recorded"],
           "settings": settings, "layout": layout,
           "timings": {"chunks": [p["timings"] for p in parts], "client_wall_s": round(time.time() - t, 1)},
           "generations": [g for p in parts for g in p["generations"]]}
    out_p = Path(out) if out else root / "runs_out" / (f"{rs.id}-screen-smoke.json" if smoke else f"{rs.id}-screen.json")
    data = S.build(raw, rs.query_targets)
    out_p.write_text(json.dumps(data))
    print(f"wrote {out_p} ({out_p.stat().st_size / 1e6:.1f} MB)")
    print("layout:", {k: v for k, v in raw["layout"].items() if k != "example_text"})
    print("timings:", raw["timings"])
    gpu_s = sum(p["timings"].get("total_s", 0) for p in parts)
    print(f"GPU time inside the function(s): {gpu_s / 60:.1f} min (plus container start per call)")
    for g in raw["generations"][:5]:
        print(g["query_idx"], g["sample_idx"], "finished" if g["finished"] else "TRUNCATED", "channels", g["channels"],
              "reasoning", g["reasoning"] and g["reasoning"]["n_tokens"], "answer", g["answer"] and g["answer"]["n_tokens"])
