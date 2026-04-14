from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


@dataclass
class EvalRow:
    qid: str
    query: str
    intent: str
    must_include_docs: list[str]
    must_exclude_docs: list[str]
    notes: str = ""


def load_queries(path: Path) -> list[EvalRow]:
    rows: list[EvalRow] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            data = json.loads(line)
            rows.append(
                EvalRow(
                    qid=data["qid"],
                    query=data["query"],
                    intent=data.get("intent", "positive"),
                    must_include_docs=list(data.get("must_include_docs", [])),
                    must_exclude_docs=list(data.get("must_exclude_docs", [])),
                    notes=data.get("notes", ""),
                )
            )
    return rows


def _normalize_docs(items: Iterable[dict]) -> list[str]:
    docs: list[str] = []
    for item in items:
        doc_id = item.get("document_id") or item.get("doc_id")
        if doc_id:
            docs.append(str(doc_id))
    return docs


def _extract_ranked_docs(row: dict) -> list[str]:
    ranked = row.get("ranked_docs")
    if isinstance(ranked, list):
        return _normalize_docs(ranked)
    top_docs = row.get("top_docs")
    if isinstance(top_docs, list):
        return [str(item) for item in top_docs if item]
    return []


def _hit_at_5(expected: list[str], ranked_docs: list[str]) -> int:
    if not expected:
        return 0
    top5 = set(ranked_docs[:5])
    return int(any(doc in top5 for doc in expected))


def _mrr_at_10(expected: list[str], ranked_docs: list[str]) -> float:
    if not expected:
        return 0.0
    for idx, doc_id in enumerate(ranked_docs[:10], start=1):
        if doc_id in expected:
            return 1.0 / idx
    return 0.0


def _noise_at_5(expected: list[str], ranked_docs: list[str]) -> float:
    top5 = ranked_docs[:5]
    if not top5:
        return 0.0
    noisy = sum(1 for doc_id in top5 if doc_id not in expected)
    return noisy / len(top5)


def _empty_rate(ranked_docs: list[str]) -> int:
    return int(len(ranked_docs) == 0)


def evaluate(queries: list[EvalRow], results: list[dict]) -> dict[str, float | int]:
    result_by_qid = {str(item.get("qid")): item for item in results}

    hit_total = 0
    mrr_total = 0.0
    noise_total = 0.0
    empty_total = 0

    for q in queries:
        row = result_by_qid.get(q.qid, {})
        ranked_docs = _extract_ranked_docs(row)
        hit_total += _hit_at_5(q.must_include_docs, ranked_docs)
        mrr_total += _mrr_at_10(q.must_include_docs, ranked_docs)
        noise_total += _noise_at_5(q.must_include_docs, ranked_docs)
        empty_total += _empty_rate(ranked_docs)

    total = max(1, len(queries))
    return {
        "total_queries": len(queries),
        "Hit@5": round(hit_total / total, 4),
        "MRR@10": round(mrr_total / total, 4),
        "Noise@5": round(noise_total / total, 4),
        "EmptyRate": round(empty_total / total, 4),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate retrieval results against eval_queries.jsonl")
    parser.add_argument("--queries", default="backend/tests/eval_queries.jsonl", help="Path to eval_queries.jsonl")
    parser.add_argument(
        "--results",
        default=None,
        help="Path to JSON results file with per-qid ranked_docs / top_docs",
    )
    args = parser.parse_args()

    query_path = Path(args.queries)
    queries = load_queries(query_path)

    if args.results:
        result_path = Path(args.results)
        with result_path.open("r", encoding="utf-8") as f:
            results = json.load(f)
    else:
        results = []

    summary = evaluate(queries, results)

    print("# Retrieval Evaluation Summary")
    print(f"queries: {summary['total_queries']}")
    print("metric\tvalue")
    print(f"Hit@5\t{summary['Hit@5']}")
    print(f"MRR@10\t{summary['MRR@10']}")
    print(f"Noise@5\t{summary['Noise@5']}")
    print(f"EmptyRate\t{summary['EmptyRate']}")


if __name__ == "__main__":
    main()
