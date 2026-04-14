from src.infrastructure.config.settings import Settings
from src.infrastructure.retrieval.tuning import RetrievalTuning


def test_retrieval_tuning_normalizes_weights() -> None:
    settings = Settings(
        rag_dense_weight=3.0,
        rag_sparse_weight=1.0,
    )
    tuning = RetrievalTuning.from_settings(settings)
    assert round(tuning.dense_weight, 3) == 0.75
    assert round(tuning.sparse_weight, 3) == 0.25


def test_retrieval_tuning_defaults_are_conservative() -> None:
    settings = Settings()
    tuning = RetrievalTuning.from_settings(settings)
    assert tuning.bm25_min_term_match == 1
    assert tuning.bm25_min_score == 0.05
    assert tuning.dense_top_k == 30
    assert tuning.sparse_top_k == 30
    assert tuning.max_document_filter_count == 20
