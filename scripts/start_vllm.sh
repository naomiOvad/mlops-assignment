#!/usr/bin/env bash
#
# Start vLLM with your chosen configuration.
# Reference: https://docs.vllm.ai/en/latest/serving/openai_compatible_server.html

set -euo pipefail

# H100 / submission — uncomment for final run and comment out local line below:
# MODEL="Qwen/Qwen3-30B-A3B-Instruct-2507"
# Local dev (Phase 1 on Mac):
MODEL="Qwen/Qwen3-0.6B"

# Local dev flags (Mac CPU) — drop or retune on H100:
# CPU defaults max_num_batched_tokens=2048; must be >= max_model_len.
export VLLM_CPU_KVCACHE_SPACE=4

LOCAL_DEV_ARGS=(
  --max-model-len 4096
  --max-num-batched-tokens 4096
  --enforce-eager
)

exec uv run python -m vllm.entrypoints.openai.api_server \
    --model "$MODEL" \
    --host 0.0.0.0 \
    --port 8000 \
    "${LOCAL_DEV_ARGS[@]}"
