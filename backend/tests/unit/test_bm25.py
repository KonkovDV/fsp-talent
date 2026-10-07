from app.services.search.bm25 import bm25


def test_bm25_ranks_the_document_that_shares_the_query_terms():
    docs = [
        "React TypeScript вёрстка интерфейса",
        "SQL PostgreSQL индексы и запросы",
        "SQL PostgreSQL миграции",
    ]
    scores = bm25("PostgreSQL SQL", docs)
    assert scores[0] < scores[1]
    assert scores[2] > scores[0]
    assert bm25("SQL", []) == []
