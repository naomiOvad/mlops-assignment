# MLOps Assignment Report

Target platform SLO (from assignment brief):

> **P95 end-to-end agent latency under 5 seconds, 10+ RPS over a 5-minute window.**

Final numbers for eval pass rate, latency, and SLO verdict **must** come from `Qwen/Qwen3-30B-A3B-Instruct-2507` on 1× H100 80GB. Local Mac CPU runs below are for development only.

---

## 1. Serving configuration (Phase 1)

### Local dev (Mac CPU — stand-in model)

Used to validate vLLM startup, manual text-to-SQL smoke tests (Phases 1–3), and Grafana panel wiring (Phase 2). Absolute latency and throughput here are not representative of submission.

| Setting | Value | Justification |
|---------|-------|---------------|
| Model | `Qwen/Qwen3-0.6B` | CPU-friendly stand-in; same OpenAI-compatible API as production model |
| `VLLM_CPU_KVCACHE_SPACE` | `4` | CPU KV cache budget (GB) for local inference |
| `--max-model-len` | `4096` | Fits local memory; agent prompts are ~1.5–3K tokens per call |
| `--max-num-batched-tokens` | `4096` | CPU vLLM requires this ≥ `--max-model-len` |
| `--enforce-eager` | on | Avoids CUDA-graph path; stable on Mac CPU backend |
| `--host` / `--port` | `0.0.0.0:8000` | Standard endpoint for agent, curl smoke tests, and Prometheus scrape |

Launch script: `scripts/start_vllm.sh` (local block active; H100 block commented).

Manual smoke test: one question from `evals/eval_set.jsonl` returned SQL — see `screenshots/vllm_manual_query.png` (**local screenshot**).

### Final submission (H100 VM) — **TODO: update on server**

**Update before grading:** switch `scripts/start_vllm.sh` and `.env` (`VLLM_MODEL`) to 30B, tune flags for the agent workload (~2–3 dependent vLLM calls per request, 1.5–3K-token prompts, short structured SQL outputs), re-run manual queries, and replace `screenshots/vllm_manual_query.png` with an H100 capture.

| Setting | Value | Justification |
|---------|-------|---------------|
| Model | `Qwen/Qwen3-30B-A3B-Instruct-2507` | Fixed assignment model (MoE) |
| Hardware | 1× H100 80GB | Fixed assignment hardware |
| *(flags TBD on H100)* | — | Choose for MoE + prompt shape + latency target; document each flag here with one-line rationale (batching, KV cache, max seq len, quantization if used, etc.) |

---

## 2. Baseline eval results (Phase 5) — **TODO: H100 only**

Run `evals/run_eval.py` against the agent on the **30B H100** endpoint.

- Overall pass rate: TBD
- Per-iteration / per-step commentary: TBD
- Screenshot: `screenshots/grafana_eval_run.png`

---

## 3. Hitting the SLO (Phase 6) — **TODO: H100 only**

Baseline load-test numbers vs. the platform SLO above. Iteration log (one line per iteration):

> *saw X → hypothesized Y → changed Z → result was W*

| Iteration | Note |
|-----------|------|
| Baseline | TBD |
| 1 | TBD |
| … | TBD |

Final numbers, whether eval quality survived tuning, and honest verdict (SLO hit or missed with gap quantified): **TBD**

Screenshots: `screenshots/grafana_before.png`, `screenshots/grafana_after.png`

---

## 4. Agent value (Phase 7) — **TODO**

Did the verify → revise loop improve outcomes? Cite per-iteration pass rates from Phase 5 eval runs.

---

## 5. What I'd do with more time (Phase 7) — **TODO**

Be specific (e.g., prompt caching for repeated schema prefix, concurrency limits from Grafana queue metrics, eval subset for faster iteration). Avoid generic infra wishlists.

---

*Keep this document ≤ 3 pages when complete (Phase 7).*
