"""Divan Tests - Reranker Evaluation.

Bu test, BM25 sonuçları ile Reranker sonuçları arasındaki sıralama farkını
(Top-K Shift) görmek için kullanılır.
"""

import asyncio
import os
import sys

from divan.core.models import SearchQuery, CourtType
from divan.services.search import UnifiedSearchService
from divan.clients.factory import CourtClientFactory
from divan.config import AppConfig

# Force Reranker usage if keys are present
os.environ["DIVAN_LOG_LEVEL"] = "WARNING"


async def main():
    config = AppConfig()
    factory = CourtClientFactory(config)
    searcher = UnifiedSearchService(factory)

    queries = [
        "işçinin haklı nedenle feshi",
        "mesai ücreti hesaplama kıdem tazminatı"
    ]

    for q_str in queries:
        print(f"\n{'='*60}")
        print(f"Sorgu: '{q_str}'")
        print(f"{'='*60}")
        
        query = SearchQuery(
            query=q_str,
            courts=[CourtType.YARGITAY],
            semantic=True,
            page_size=8
        )
        
        result = await searcher.search(query)
        
        print("\n--- Reranked Top 8 ---")
        for i, d in enumerate(result.decisions):
            score_str = d.raw_metadata.get('_reranker_score', 'N/A')
            if isinstance(score_str, float):
                score_str = f"{score_str:.4f}"
            print(f"{i+1}. [Skor: {score_str}] - ID: {d.id} | snippet: {str(d.snippet)[:80]}...")
            
    await factory.close_all()


if __name__ == "__main__":
    asyncio.run(main())
