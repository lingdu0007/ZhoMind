from __future__ import annotations

from scripts.eval_runner import evaluate, load_queries


def test_eval_runner_metrics(tmp_path):
    query_path = tmp_path / "eval_queries.jsonl"
    query_path.write_text(
        '{"qid":"Q1","query":"a","intent":"positive","must_include_docs":["doc1"],"must_exclude_docs":[]}\n'
        '{"qid":"Q2","query":"b","intent":"noise","must_include_docs":[],"must_exclude_docs":["doc2"]}\n',
        encoding="utf-8",
    )

    queries = load_queries(query_path)
    results = [
        {"qid": "Q1", "ranked_docs": [{"document_id": "doc1"}, {"document_id": "doc3"}]},
        {"qid": "Q2", "ranked_docs": []},
    ]

    summary = evaluate(queries, results)
    assert summary["total_queries"] == 2
    assert summary["Hit@5"] == 0.5
    assert summary["MRR@10"] == 0.5
    assert summary["Noise@5"] == 0.25
    assert summary["EmptyRate"] == 0.5
