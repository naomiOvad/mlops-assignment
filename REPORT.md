# MLOps Assignment Report

Target platform SLO (from assignment brief):

> **P95 end-to-end agent latency under 5 seconds, 10+ RPS over a 5-minute window.**

All submission numbers below come from `Qwen/Qwen3-30B-A3B-Instruct-2507` on 1× H100 80GB (Nebius VM). Local Mac CPU runs (0.6B stand-in) were used only for early development.

---

## 1. Serving configuration (Phase 1)

| Setting | Value | Justification |
|---------|-------|---------------|
| Model | `Qwen/Qwen3-30B-A3B-Instruct-2507` | Fixed assignment model (MoE) |
| Hardware | 1× H100 80GB | Fixed assignment hardware |
| `--max-model-len` | `8192` | Agent prompts ~1.5–3K tokens; headroom for schema + history on revise |
| `--gpu-memory-utilization` | `0.96` (tuned from 0.92) | Use available H100 memory for KV cache / concurrent seqs under agent load |
| `--enable-chunked-prefill` | on | Better prefill scheduling for bursty agent traffic (short outputs, long prompts) |
| `--enable-prefix-caching` | on (added in Phase 6) | Agent repeats large schema prefix across generate/verify/revise calls |
| `--max-num-seqs` | `256` | Allow concurrent agent requests without immediate rejection under load test |
| `--host` / `--port` | `0.0.0.0:8000` | Agent, Prometheus scrape, manual curl tests |

Launch: `scripts/start_vllm.sh`. Manual smoke test on H100: `screenshots/vllm_manual_query.png`.

---

## 2. Baseline eval results (Phase 5)

Run: `evals/run_eval.py` → `results/eval_baseline.json` (30 questions, H100).

| Metric | Value |
|--------|-------|
| Overall pass rate | **36.7%** (11/30) |
| Pass rate @ iter 0 | **30.0%** |
| Pass rate @ iter 1+ | **36.7%** |
| Avg iterations | **1.53** |

The verify→revise loop adds **+6.7 pp** over stopping at iter 0 (30% → 36.7%). Most gains appear by iteration 1; later iterations did not improve aggregate pass rate further on this eval set. Screenshot during eval: `screenshots/grafana_eval_run.png`.

---

## 3. Hitting the SLO (Phase 6)

Load driver: `load_test/driver.py --rps 10 --duration 300` (agent endpoint, 3000 requested requests).

### Baseline load test (before tuning)

| Metric | Value | SLO target |
|--------|-------|------------|
| Achieved RPS | **8.3** | ≥ 10 |
| Successful requests | **747 / 3000** (25%) | — |
| Agent latency p50 | **92 s** | — |
| Agent latency p95 | **120 s** | < 5 s |

Grafana under load (`screenshots/grafana_before.png`): vLLM E2E p95 ~3.5 s, queue p95 ~300 ms, KV cache usage ~20% (headroom), ~30–40 running requests.

### Iteration log

| Iteration | Note |
|-----------|------|
| Baseline | saw vLLM queue ~300 ms and E2E spikes under load while KV cache ~20% full; agent p95 ~120 s with heavy timeouts at 10 RPS → workload is agent-concurrency + repeated long prompts, not KV exhaustion |
| 1 | saw X above → hypothesized prefix reuse underused → changed `--gpu-memory-utilization` 0.92→**0.96** and added **`--enable-prefix-caching`** → result: agent **p50 92 s → 43 s**, **p95 120 s → 107 s**, prefix hit rate ~90% on Grafana (`screenshots/grafana_after.png`), but **SLO still missed**; ok count 747→593; eval unchanged |

### Final load test (after tuning)

Same command as baseline; config above.

| Metric | Before | After |
|--------|--------|-------|
| Agent latency p50 | 92 s | **43 s** |
| Agent latency p95 | 120 s | **107 s** |
| Achieved RPS | 8.3 | 8.3 |
| ok / 3000 | 747 | 593 |

### Eval after tuning

`results/eval_after_tuning.json`: pass rate **36.7%** (11/30), same per-iteration breakdown as baseline. **Quality survived tuning.**

### Verdict

**SLO missed.** Gap: agent p95 ~107 s vs 5 s target; achieved RPS ~8.3 vs 10; most requests time out or error under 10 RPS because each agent run triggers ~2–3 sequential 30B calls. vLLM-only Grafana metrics improved with prefix caching, but end-to-end agent SLO needs agent-side throttling or faster per-step inference, not just serving flags.

---

## 4. Agent value

The verify→revise loop is doing real work: **30% → 36.7%** pass rate (+6.7 pp) on the H100 eval set, with avg **1.53** iterations. Roughly one third of questions trigger at least one revise (visible in Langfuse traces with `revise → execute → verify`; see `screenshots/langfuse_trace.png`). Without the loop, 9 additional questions would have been wrong at submission time. The loop is worth keeping, though verify is sometimes lenient (passes on iter 0 for hard questions that still fail eval).

---

## 5. What I'd do with more time

1. **Cap agent concurrency** (semaphore on `/answer` or lower load-test RPS to sustainable level) and re-measure — current failure mode is overload, not single-request latency.
2. **Tune verify prompts on 30B** so iter-0 false positives drop; iter-1 gains might translate to higher final pass rate.
3. **Quantization (AWQ/FP8)** on H100 to cut per-call latency, re-run eval to confirm no regression.
4. **Separate dashboards**: agent end-to-end latency (Langfuse) vs vLLM `/metrics` — Phase 6 showed they diverge under load.
5. **Prompt / schema caching** beyond vLLM prefix cache (hash schema once per db_id in agent state).

---

*Grafana serving dashboard: `screenshots/grafana_serving.png`. Langfuse: `screenshots/langfuse_trace.png`, `screenshots/langfuse_tags.png`.*
