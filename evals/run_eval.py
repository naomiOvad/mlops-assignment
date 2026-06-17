"""Eval runner using execution accuracy.

Reads evals/eval_set.jsonl, calls the agent at AGENT_URL on each question,
then compares the agent's SQL output to the gold SQL by *executed rows*
(canonicalized: sorted, stringified, None-coerced to empty).

Helpers (run_sql / canonicalize / matches) are provided. You implement
eval_one() and summarize().

Run:
    uv run python evals/run_eval.py --out results/eval_baseline.json
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_EVAL_FILE = ROOT / "evals" / "eval_set.jsonl"
DEFAULT_OUT_FILE = ROOT / "results" / "eval_baseline.json"
DB_DIR = ROOT / "data" / "bird"
AGENT_URL_DEFAULT = "http://localhost:8001/answer"


# ---------- Helpers (provided) -----------------------------------------

def run_sql(db_id: str, sql: str, timeout: float = 5.0) -> tuple[bool, list[tuple] | None, str | None]:
    """Run sql against db_id in read-only mode. Returns (ok, rows, error)."""
    path = DB_DIR / f"{db_id}.sqlite"
    try:
        with sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=timeout) as conn:
            cur = conn.execute(sql)
            rows = cur.fetchall()
            return True, rows, None
    except Exception as e:  # noqa: BLE001
        return False, None, f"{type(e).__name__}: {e}"


def canonicalize(rows: list[tuple] | None) -> list[tuple] | None:
    """Sort rows; coerce cells to str; None -> ''."""
    if rows is None:
        return None
    return sorted(tuple("" if c is None else str(c) for c in row) for row in rows)


def matches(gold_rows: list[tuple] | None, pred_rows: list[tuple] | None) -> bool:
    if gold_rows is None or pred_rows is None:
        return False
    return canonicalize(gold_rows) == canonicalize(pred_rows)


# Track pass rate after attempt 0..MAX_ITERATIONS (README: iter 0 vs iter 3).
MAX_ITERATION_INDEX = 3


def _sql_attempts(history: list[dict]) -> list[str]:
    """Ordered SQL candidates from generate_sql / revise history entries."""
    attempts: list[str] = []
    for entry in history:
        if entry.get("node") in ("generate_sql", "revise") and entry.get("sql"):
            attempts.append(entry["sql"])
    return attempts


def _per_iteration_correct(
    db_id: str, gold_rows: list[tuple] | None, attempts: list[str]
) -> list[bool]:
    """Execution-accuracy correctness for each SQL attempt."""
    if gold_rows is None:
        return [False] * len(attempts)
    correct: list[bool] = []
    for sql in attempts:
        ok, rows, _ = run_sql(db_id, sql)
        correct.append(matches(gold_rows, rows) if ok else False)
    return correct


def eval_one(question: dict, agent_url: str) -> dict:
    """Score one question. Return a dict capturing per-iteration correctness."""
    db_id = question["db_id"]
    gold_ok, gold_rows, gold_error = run_sql(db_id, question["gold_sql"])

    payload = {
        "question": question["question"],
        "db": db_id,
        "tags": {"run_type": "eval", "db_id": db_id},
    }
    try:
        resp = httpx.post(agent_url, json=payload, timeout=300.0)
        resp.raise_for_status()
        agent = resp.json()
    except Exception as e:  # noqa: BLE001
        return {
            "question": question["question"],
            "db_id": db_id,
            "gold_ok": gold_ok,
            "gold_error": gold_error,
            "agent_error": f"{type(e).__name__}: {e}",
            "iterations": 0,
            "final_correct": False,
            "per_iteration_correct": [],
        }

    attempts = _sql_attempts(agent.get("history", []))
    if not attempts and agent.get("sql"):
        attempts = [agent["sql"]]

    per_iter = _per_iteration_correct(db_id, gold_rows if gold_ok else None, attempts)
    final_correct = bool(per_iter[-1]) if per_iter else False

    return {
        "question": question["question"],
        "db_id": db_id,
        "gold_ok": gold_ok,
        "gold_error": gold_error,
        "agent_ok": agent.get("ok"),
        "agent_error": agent.get("error"),
        "iterations": agent.get("iterations", 0),
        "final_sql": agent.get("sql", ""),
        "final_correct": final_correct,
        "per_iteration_correct": per_iter,
    }


def summarize(results: list[dict]) -> dict:
    """Aggregate per-question results.

    Per-iteration carry-forward: if the agent terminated at iteration j < k
    (verify said ok at j, or it hit MAX_ITERATIONS at j < k), treat the
    question's iteration-k result as identical to its iteration-j result.
    The agent stopped emitting; whatever it had at termination is what
    would have been served had we polled at iteration k.
    """
    n = len(results)
    if n == 0:
        return {
            "total": 0,
            "final_correct": 0,
            "pass_rate": 0.0,
            "per_iteration_pass_rate": {},
            "avg_iterations": 0.0,
        }

    final_correct = sum(1 for r in results if r.get("final_correct"))
    avg_iterations = sum(r.get("iterations", 0) for r in results) / n

    per_iteration_pass_rate: dict[str, float] = {}
    for k in range(MAX_ITERATION_INDEX + 1):
        correct_at_k = 0
        for r in results:
            per = r.get("per_iteration_correct") or []
            if not per:
                continue
            idx = min(k, len(per) - 1)
            if per[idx]:
                correct_at_k += 1
        per_iteration_pass_rate[str(k)] = correct_at_k / n

    return {
        "total": n,
        "final_correct": final_correct,
        "pass_rate": final_correct / n,
        "per_iteration_pass_rate": per_iteration_pass_rate,
        "avg_iterations": avg_iterations,
    }


# ---------- Main (provided) --------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--eval-set", type=Path, default=DEFAULT_EVAL_FILE)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT_FILE)
    parser.add_argument("--agent-url", default=AGENT_URL_DEFAULT)
    args = parser.parse_args()

    questions = [json.loads(line) for line in args.eval_set.read_text().splitlines() if line.strip()]
    print(f"Loaded {len(questions)} eval questions from {args.eval_set}")

    results: list[dict] = []
    t0 = time.monotonic()
    for i, q in enumerate(questions, 1):
        print(f"[{i}/{len(questions)}] {q['db_id']}: {q['question'][:60]}...", flush=True)
        results.append(eval_one(q, args.agent_url))
    elapsed = time.monotonic() - t0

    summary = summarize(results)
    out = {
        "summary": summary,
        "wall_clock_seconds": elapsed,
        "results": results,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(out, indent=2))
    print(f"Wrote {args.out}")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
