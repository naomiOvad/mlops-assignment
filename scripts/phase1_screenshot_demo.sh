#!/usr/bin/env bash
# Compact output for screenshots/vllm_manual_query.png (Phase 1 local dev).
set -euo pipefail
cd "$(dirname "$0")/.."

echo "=== vLLM serving ==="
curl -s http://localhost:8000/v1/models | python3 -c "
import json, sys
d = json.load(sys.stdin)
print('model:', d['data'][0]['id'])
print('max_model_len:', d['data'][0]['max_model_len'])
"

echo
echo "=== Manual query (eval_set.jsonl) ==="
echo "Question: List down Ajax's superpowers."
echo

uv run python -c "
import json, urllib.request
from agent.schema import render_schema

question = \"List down Ajax's superpowers.\"
schema = render_schema('superhero')
prompt = f'''You are a SQL expert. Given the schema below, write a single SQLite query.

Schema:
{schema}

Question: {question}

Reply with only the SQL query, no explanation.'''

body = json.dumps({
    'model': 'Qwen/Qwen3-0.6B',
    'messages': [{'role': 'user', 'content': prompt}],
    'max_tokens': 256,
    'temperature': 0,
    'chat_template_kwargs': {'enable_thinking': False},
}).encode()

req = urllib.request.Request(
    'http://localhost:8000/v1/chat/completions',
    data=body,
    headers={'Content-Type': 'application/json'},
)
with urllib.request.urlopen(req) as resp:
    data = json.load(resp)

sql = data['choices'][0]['message']['content']
print('=== SQL response ===')
print(sql)
"
