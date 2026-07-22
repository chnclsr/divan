"""Divan Services — Unified search service.

Birden fazla mahkemede paralel arama yapar, sonuçları birleştirir.
CourtListener'ın multi-jurisdiction arama yaklaşımından esinlenilmiştir.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Optional

from ..core.enums import CourtType
from ..core.interfaces import ISearchService
from ..core.models import Decision, SearchQuery, SearchResult
from ..core.exceptions import DivanError
from ..clients.factory import CourtClientFactory

logger = logging.getLogger(__name__)


class UnifiedSearchService(ISearchService):
    """Tek arayüzden tüm kurumlarda arama.

    Features:
        - Paralel multi-court arama (asyncio.gather)
        - Per-court hata izolasyonu (bir kurum hata verse de diğerleri çalışır)
        - Sonuçları birleştirme
        - Cross-court dedup (aynı karar farklı kaynaklarda)
    """

    def __init__(self, factory: CourtClientFactory) -> None:
        self._factory = factory

    async def search(self, query: SearchQuery) -> SearchResult:
        """Birden fazla mahkemede paralel arama yap.

        Her court için ayrı bir task oluşturulur. Bir court başarısız
        olursa diğerleri etkilenmez; hata, sonuçtaki `errors` dict'ine
        eklenir.
        """

        # Hangi client'lar gerekiyor?
        court_client_map: dict[str, tuple[list[CourtType], any]] = {}

        for court_type in query.courts:
            try:
                client = self._factory.create(court_type)
                # Aynı client birden fazla CourtType'ı kapsayabilir (Bedesten)
                client_key = id(client)
                if client_key not in court_client_map:
                    court_client_map[client_key] = ([], client)
                court_client_map[client_key][0].append(court_type)
            except ValueError as e:
                logger.warning(f"Unsupported court type {court_type}: {e}")

        if not court_client_map:
            return SearchResult(
                page=query.page,
                page_size=query.page_size,
                errors={"general": "Desteklenen mahkeme türü bulunamadı"},
            )

        # Sorgu genişletme (recall) — bir kez hesapla; yalnızca Boolean-OR
        # destekleyen client'lara OR sorgusu gönder, diğerlerine düz sorgu.
        or_phrase = None
        if getattr(query, "expand", True) and query.query:
            from divan.services.semantic.expansion import expand_query, build_or_phrase
            terms = expand_query(query.query)
            if len(terms) > 1:
                or_phrase = build_or_phrase(terms)
                logger.info(f"Query expanded ({len(terms)} terms): {or_phrase}")

        # Paralel arama
        tasks = []
        task_labels = []
        for client_key, (court_types, client) in court_client_map.items():
            # Her client'a ilgili court type listesini gönder
            update = {"courts": court_types}
            if or_phrase and getattr(client, "supports_boolean_or", False):
                update["query"] = or_phrase
            sub_query = query.model_copy(update=update)
            tasks.append(self._safe_search(client, sub_query))
            task_labels.append(court_types[0].name)

        results = await asyncio.gather(*tasks)

        # Sonuçları birleştir
        merged_result = self._merge_results(results, task_labels, query)
        
        # Semantik Arama
        if getattr(query, 'semantic', False) and merged_result.decisions:
            merged_result = await self._apply_semantic_search(query.query, merged_result)
            
        return merged_result

    async def search_single(self, query: SearchQuery, court: CourtType) -> SearchResult:
        """Tek bir mahkemede arama yap."""
        single_query = query.model_copy(update={"courts": [court]})
        client = self._factory.create(court)
        return await client.search(single_query)

    # ── Internal ──────────────────────────────────────────────────────────

    async def _safe_search(self, client, query: SearchQuery) -> tuple[Optional[SearchResult], Optional[str]]:
        """Hata izolasyonlu arama wrapper'ı."""
        try:
            result = await client.search(query)
            return (result, None)
        except DivanError as e:
            logger.warning(f"Search error in {client.court_type.name}: {e}")
            return (None, str(e))
        except Exception as e:
            logger.error(f"Unexpected search error in {client.court_type.name}: {e}")
            return (None, f"Beklenmeyen hata: {e}")

    def _merge_results(
        self,
        results: list[tuple[Optional[SearchResult], Optional[str]]],
        labels: list[str],
        original_query: SearchQuery,
    ) -> SearchResult:
        """Birden fazla SearchResult'ı tek bir sonuçta birleştir."""
        all_decisions: list[Decision] = []
        total_records = 0
        errors: dict[str, str] = {}
        courts_searched: list[CourtType] = []

        for (result, error), label in zip(results, labels):
            if error:
                errors[label] = error
                continue
            if result:
                # Orijinal sıralamayı korumak için her sonuca kendi sırasını (rank) ekle
                for idx, d in enumerate(result.decisions):
                    if "_original_rank" not in d.raw_metadata:
                        d.raw_metadata["_original_rank"] = idx
                all_decisions.extend(result.decisions)
                total_records += result.total_records
                courts_searched.extend(result.courts_searched)

        # Sırala
        if original_query.query:
            # Metin araması varsa, kaynakların kendi alaka sıralamasını (rank) koru.
            # Eşit rank'ta en yeni karar önce gelir (tie-breaker).
            all_decisions.sort(
                key=lambda d: (
                    d.raw_metadata.get("_original_rank", 999),
                    -(d.decision_date.toordinal() if d.decision_date else 0)
                )
            )
        else:
            # Metin araması yoksa (sadece tarih veya daire filtresi varsa), kararları tarihe göre azalan şekilde sırala
            all_decisions.sort(
                key=lambda d: d.decision_date.isoformat() if d.decision_date else (d.fetched_at.isoformat() if d.fetched_at else ""),
                reverse=True,
            )

        # Dedup (aynı esas_no + karar_no)
        seen: set[str] = set()
        unique_decisions: list[Decision] = []
        for d in all_decisions:
            if d.esas_no or d.karar_no:
                dedup_key = f"{d.court_type}:{d.esas_no or ''}:{d.karar_no or ''}"
            else:
                dedup_key = f"{d.court_type}:id:{d.id}"
                
            if dedup_key not in seen:
                seen.add(dedup_key)
                unique_decisions.append(d)

        return SearchResult(
            decisions=unique_decisions,
            total_records=total_records,
            page=original_query.page,
            page_size=original_query.page_size,
            total_pages=(total_records + original_query.page_size - 1) // original_query.page_size
            if total_records > 0 else 0,
            courts_searched=list(set(courts_searched)),
            errors=errors,
        )

    async def _extract_snippets(self, query_text: str, decisions: list['Decision']) -> None:
        import asyncio
        
        decisions_to_process = decisions[:8]
        sem = asyncio.Semaphore(5)
        
        async def fetch_and_extract(d: 'Decision'):
            async with sem:
                try:
                    client = self._factory.create(d.court_type)
                    full_doc = await client.get_document(d.id)
                    content = full_doc.markdown_content or ""
                    
                    if not content:
                        d.snippet = d.summary
                        return
                        
                    d.snippet = self._best_snippet_window(content, query_text, window=400)
                except Exception as e:
                    logger.warning(f"Snippet extraction failed for {d.id}: {e}")
                    d.snippet = d.summary
                    
        await asyncio.gather(*(fetch_and_extract(d) for d in decisions_to_process))

    @staticmethod
    def _best_snippet_window(content: str, query: str, window: int = 400) -> str:
        """Sorgu kelimelerinin en yoğun geçtiği ~`window` karakterlik pencereyi bul.

        Naif tam-cümle eşleştirmesinin aksine, sorguyu kelimelere böler ve
        en çok FARKLI kelimenin geçtiği (eşitlikte en dar) pencereyi seçer.
        Hiç eşleşme yoksa metnin başını döndürür.
        """
        import re
        from collections import defaultdict

        content_lower = content.lower()
        tokens = [t for t in re.findall(r"\w+", query.lower(), flags=re.UNICODE) if len(t) >= 3]

        def _head() -> str:
            return content[:window].replace("\n", " ").strip() + ("..." if len(content) > window else "")

        if not tokens:
            return _head()

        # Her benzersiz token'ın tüm konumlarını topla
        hits: list[tuple[int, str]] = []
        for t in set(tokens):
            start = 0
            while True:
                i = content_lower.find(t, start)
                if i == -1:
                    break
                hits.append((i, t))
                start = i + len(t)

        if not hits:
            return _head()

        hits.sort()
        positions = [h[0] for h in hits]
        toks = [h[1] for h in hits]

        # İki-işaretçi: `window` genişliğindeki en çok farklı token kapsayan aralık
        counts: dict[str, int] = defaultdict(int)
        distinct = 0
        left = 0
        best_score = -1
        best_l = best_r = positions[0]
        for right in range(len(hits)):
            counts[toks[right]] += 1
            if counts[toks[right]] == 1:
                distinct += 1
            while positions[right] - positions[left] > window:
                counts[toks[left]] -= 1
                if counts[toks[left]] == 0:
                    distinct -= 1
                left += 1
            span = positions[right] - positions[left]
            score = distinct * 1_000_000 - span  # önce kapsam, sonra darlık
            if score > best_score:
                best_score = score
                best_l, best_r = positions[left], positions[right]

        center = (best_l + best_r) // 2
        start = max(0, center - window // 2)
        end = min(len(content), start + window)
        snippet = content[start:end].replace("\n", " ").strip()
        prefix = "..." if start > 0 else ""
        suffix = "..." if end < len(content) else ""
        return prefix + snippet + suffix

    async def _apply_semantic_search(self, query_text: str, result: SearchResult) -> SearchResult:
        """Adaylara bağlam (snippet) ekle; sıralamayı tüketici LLM'e (Claude) bırak.

        MCP felsefesi: muhakeme host'ta. Bu metot her aday için sorgunun geçtiği
        gerçek paragrafı (snippet) çıkarır, adayları OLDUĞU sırada döndürür.
        Claude snippet'leri okuyup kendi sıralamasını yapar — cross-encoder'dan
        daha iyi ve sıfır ek bağımlılık.

        Cross-encoder yeniden sıralama SADECE `DIVAN_ENABLE_RERANKER` açıkça
        set edildiğinde çalışır (opsiyonel güç-kullanıcı katmanı). Varsayılanda
        kapalı; ne API key ne torch gerektirir.
        """
        try:
            import os
            top_candidates = result.decisions[:8]
            if not top_candidates:
                return result

            # 1. Snippet Extraction (her zaman) — Claude'un okuyacağı bağlam
            await self._extract_snippets(query_text, top_candidates)

            # 2. Opsiyonel cross-encoder — yalnızca açıkça etkinleştirilirse
            if os.getenv("DIVAN_ENABLE_RERANKER", "").strip().lower() not in ("1", "true", "yes"):
                return result  # Varsayılan: sıralamayı Claude yapar

            from divan.services.semantic.reranker import RerankerFactory
            reranker = RerankerFactory.get_reranker()

            docs_to_rerank = []
            for d in top_candidates:
                content = []
                if d.title: content.append(d.title)
                if d.snippet: content.append(d.snippet)
                docs_to_rerank.append(" | ".join(content) if content else d.id)

            reranked_scores = await reranker.arerank(query_text, docs_to_rerank)

            new_top = []
            for original_idx, score in reranked_scores:
                doc = top_candidates[original_idx]
                doc.raw_metadata["_reranker_score"] = score
                new_top.append(doc)

            result.decisions = new_top + result.decisions[8:]
            return result

        except Exception as e:
            logger.error(f"Semantic search failed: {e}")
            result.errors["semantic"] = str(e)
            return result
