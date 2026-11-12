"""Serve gpt-oss-20b on Modal with vLLM (OpenAI-compatible) for SPET runs.

Adapted from Modal's gpt-oss example (modal.com/docs/examples/gpt_oss_inference),
changed to one H100 (cheaper than B200; 20B fits easily), no speculative decoding,
and an API key so the public URL can't spend your credits.

One-time setup:
    modal token new
    modal secret create spet-vllm VLLM_API_KEY=<random string>

Deploy and smoke-test:
    modal deploy deploy/modal_vllm.py
    modal run deploy/modal_vllm.py          # health check + one request

Then point SPET at it:
    SPET_BASE_URL=<printed url>/v1 SPET_MODEL=openai/gpt-oss-20b SPET_API_KEY=<same key> \\
        python -m spet serve

The container scales to zero after SCALEDOWN minutes idle, so credits are only
used while a run is going (plus a cold start of a few minutes on first request).
"""

import json

import modal

MODEL_NAME = "openai/gpt-oss-20b"
MODEL_REVISION = "d666cf3b67006cf8227666739edf25164aaffdeb"  # pinned as in Modal's example
GPU = "H100"
VLLM_PORT = 8000
MINUTES = 60
SCALEDOWN = 5  # minutes idle before the GPU is released
MAX_INPUTS = 32  # concurrent requests per replica

image = (
    modal.Image.from_registry("nvidia/cuda:12.8.1-devel-ubuntu22.04", add_python="3.12")
    .entrypoint([])
    .uv_pip_install("vllm==0.18.1", "huggingface_hub[hf_transfer]==0.36.0")
    .env({"HF_HUB_ENABLE_HF_TRANSFER": "1"})
)

hf_cache = modal.Volume.from_name("huggingface-cache", create_if_missing=True)
vllm_cache = modal.Volume.from_name("vllm-cache", create_if_missing=True)

app = modal.App("spet-vllm")


@app.function(
    image=image,
    gpu=GPU,
    scaledown_window=SCALEDOWN * MINUTES,
    timeout=30 * MINUTES,
    volumes={"/root/.cache/huggingface": hf_cache, "/root/.cache/vllm": vllm_cache},
    secrets=[modal.Secret.from_name("spet-vllm")],
)
@modal.concurrent(max_inputs=MAX_INPUTS)
@modal.web_server(port=VLLM_PORT, startup_timeout=30 * MINUTES)
def serve():
    import os
    import subprocess

    cmd = [
        "vllm", "serve", MODEL_NAME,
        "--revision", MODEL_REVISION,
        "--served-model-name", MODEL_NAME,
        "--host", "0.0.0.0",
        "--port", str(VLLM_PORT),
        "--api-key", os.environ["VLLM_API_KEY"],
        "--max-model-len", "16384",
        "--max-num-seqs", str(MAX_INPUTS),
        "--compilation-config", json.dumps({"pass_config": {"eliminate_noops": True}}),
    ]
    print(*[c if c != os.environ["VLLM_API_KEY"] else "***" for c in cmd])
    subprocess.Popen(cmd)


@app.local_entrypoint()
def test():
    import os
    import urllib.request

    url = serve.get_web_url()
    key = os.environ.get("VLLM_API_KEY") or input("VLLM_API_KEY: ")
    print(f"url: {url}\nwaiting for health (first start downloads ~13 GB, can take several minutes)…")
    req = urllib.request.Request(f"{url}/health")
    urllib.request.urlopen(req, timeout=30 * MINUTES)
    body = json.dumps({
        "model": MODEL_NAME,
        "messages": [
            {"role": "system", "content": "Always apologise when the user reports a problem."},
            {"role": "user", "content": "My build fails with a missing module."},
        ],
        "temperature": 0.7, "seed": 1, "max_tokens": 400, "reasoning_effort": "low",
    }).encode()
    req = urllib.request.Request(f"{url}/v1/chat/completions", data=body,
                                 headers={"content-type": "application/json", "authorization": f"Bearer {key}"})
    out = json.load(urllib.request.urlopen(req, timeout=10 * MINUTES))
    print("\n--- answer ---\n" + (out["choices"][0]["message"].get("content") or "<empty content>"))
    print(f"\nSPET_BASE_URL={url}/v1")
