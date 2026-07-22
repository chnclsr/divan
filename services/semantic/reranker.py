"""Divan Semantic Services - Cross-Encoder Reranker.

Supports API-first (Cohere, Jina) or fallback to local FlagEmbedding.
"""

import os
import logging
from typing import List, Tuple
import asyncio

logger = logging.getLogger(__name__)

# Try to import FlagEmbedding if available
try:
    from FlagEmbedding import FlagReranker
    FLAG_AVAILABLE = True
except ImportError:
    FLAG_AVAILABLE = False


class RerankerFactory:
    """Creates a Reranker based on available API keys or local deps."""
    
    _local_model = None

    @classmethod
    def get_reranker(cls) -> "BaseReranker":
        if os.getenv("COHERE_API_KEY"):
            return CohereReranker(api_key=os.getenv("COHERE_API_KEY"))
        elif os.getenv("JINA_API_KEY"):
            return JinaReranker(api_key=os.getenv("JINA_API_KEY"))
        elif FLAG_AVAILABLE:
            if not cls._local_model:
                logger.info("Loading local BGE Reranker (this might take a while the first time)...")
                cls._local_model = FlagReranker('BAAI/bge-reranker-v2-m3', use_fp16=True)
            return LocalBGEReranker(cls._local_model)
        else:
            logger.warning("No Reranker API keys (Cohere/Jina) found and FlagEmbedding not installed. Using NoOpReranker.")
            return NoOpReranker()


class BaseReranker:
    def rerank(self, query: str, docs: List[str]) -> List[Tuple[int, float]]:
        """
        Reranks documents based on query.
        Returns a list of tuples: (original_index, score) sorted by score descending.
        """
        raise NotImplementedError
        
    async def arerank(self, query: str, docs: List[str]) -> List[Tuple[int, float]]:
        return await asyncio.to_thread(self.rerank, query, docs)


class CohereReranker(BaseReranker):
    def __init__(self, api_key: str):
        try:
            import cohere
            self.client = cohere.ClientV2(api_key=api_key)
        except ImportError:
            raise ImportError("cohere SDK required for CohereReranker. Run 'pip install cohere'")
            
    def rerank(self, query: str, docs: List[str]) -> List[Tuple[int, float]]:
        if not docs:
            return []
            
        try:
            response = self.client.rerank(
                model="rerank-multilingual-v3.0",
                query=query,
                documents=docs,
                top_n=len(docs)
            )
            # cohere response.results[i].index -> original doc index
            return [(res.index, res.relevance_score) for res in response.results]
        except Exception as e:
            logger.error(f"Cohere Rerank failed: {e}")
            return [(i, 0.0) for i in range(len(docs))]


class JinaReranker(BaseReranker):
    def __init__(self, api_key: str):
        self.api_key = api_key
        
    def rerank(self, query: str, docs: List[str]) -> List[Tuple[int, float]]:
        if not docs:
            return []
            
        import requests
        try:
            url = "https://api.jina.ai/v1/rerank"
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}"
            }
            data = {
                "model": "jina-reranker-v2-base-multilingual",
                "query": query,
                "documents": docs,
                "top_n": len(docs)
            }
            resp = requests.post(url, headers=headers, json=data)
            resp.raise_for_status()
            results = resp.json().get("results", [])
            # Jina returns sorted results with 'index'
            return [(r["index"], r["relevance_score"]) for r in results]
        except Exception as e:
            logger.error(f"Jina Rerank failed: {e}")
            return [(i, 0.0) for i in range(len(docs))]


class LocalBGEReranker(BaseReranker):
    def __init__(self, model):
        self.model = model
        
    def rerank(self, query: str, docs: List[str]) -> List[Tuple[int, float]]:
        if not docs:
            return []
        
        try:
            # Format for BGE reranker is list of [query, text]
            pairs = [[query, doc] for doc in docs]
            scores = self.model.compute_score(pairs, normalize=True)
            
            # If only 1 document, it returns a float instead of list
            if isinstance(scores, float):
                scores = [scores]
                
            indexed_scores = [(i, score) for i, score in enumerate(scores)]
            # Sort by score descending
            indexed_scores.sort(key=lambda x: x[1], reverse=True)
            return indexed_scores
        except Exception as e:
            logger.error(f"Local BGE Rerank failed: {e}")
            return [(i, 0.0) for i in range(len(docs))]


class NoOpReranker(BaseReranker):
    def rerank(self, query: str, docs: List[str]) -> List[Tuple[int, float]]:
        # Keep original order, score decreasing linearly
        return [(i, 1.0 - (i/len(docs))) for i in range(len(docs))]
